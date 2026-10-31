import sys
import getpass
import uuid
import types
import importlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, "backend")

from supabase import create_client


app = types.SimpleNamespace(
    core=types.SimpleNamespace(
        config=importlib.import_module("app.core.config"),
    ),
    integrations=types.SimpleNamespace(
        supabase=importlib.import_module("app.integrations.supabase"),
    ),
)

settings = app.core.config.settings
service_supabase = app.integrations.supabase.service_supabase


if not settings.TEST_USER_A_ID or not settings.TEST_USER_B_ID:
    raise RuntimeError(
        "Set TEST_USER_A_ID and TEST_USER_B_ID in your .env file."
    )


USERS = {
    "1": {
        "name": "User A",
        "id": settings.TEST_USER_A_ID,
        "customer": "customer-a@test.example",
        "invoice": "TEST-INV-A001",
        "payment": "TEST-ORDER-A001",
        "approval": "security-test-approval-a",
        "audit": "Security isolation test for User A",
    },
    "2": {
        "name": "User B",
        "id": settings.TEST_USER_B_ID,
        "customer": "customer-b@test.example",
        "invoice": "TEST-INV-B001",
        "payment": "TEST-ORDER-B001",
        "approval": "security-test-approval-b",
        "audit": "Security isolation test for User B",
    },
}

results = []


def record(label, passed, details=""):
    results.append((label, passed))
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")

    if details:
        print(f"       {details}")


def fetch_one(client, table, filters, columns="id"):
    query = client.table(table).select(columns)

    for column, value in filters.items():
        query = query.eq(column, value)

    response = query.execute()
    rows = response.data or []

    if len(rows) != 1:
        raise RuntimeError(
            f"{table}: expected one test record, found {len(rows)}"
        )

    return rows[0]


def fetch_by_id(client, table, record_id):
    response = (
        client.table(table)
        .select("*")
        .eq("id", record_id)
        .execute()
    )

    rows = response.data or []
    return rows[0] if rows else None


def check_read_isolation(user_db, table, own_id, other_id):
    own = (
        user_db.table(table)
        .select("id")
        .eq("id", own_id)
        .execute()
    )

    other = (
        user_db.table(table)
        .select("id")
        .eq("id", other_id)
        .execute()
    )

    return (
        len(own.data or []) == 1
        and len(other.data or []) == 0
    )


def run_read_tests(user_db, selected, other):
    print("\n--- CROSS-USER READ ISOLATION ---")

    records = {}

    # Profiles
    records["profiles"] = {
        "own": {"id": selected["id"]},
        "other": {"id": other["id"]},
    }

    # Customers
    records["customers"] = {
        "own": fetch_one(
            service_supabase,
            "customers",
            {
                "user_id": selected["id"],
                "email": selected["customer"],
            },
            columns="id, user_id",
        ),
        "other": fetch_one(
            service_supabase,
            "customers",
            {
                "user_id": other["id"],
                "email": other["customer"],
            },
            columns="id, user_id",
        ),
    }

    # Invoices
    records["invoices"] = {
        "own": fetch_one(
            service_supabase,
            "invoices",
            {
                "user_id": selected["id"],
                "invoice_number": selected["invoice"],
            },
            columns="id, user_id, customer_id",
        ),
        "other": fetch_one(
            service_supabase,
            "invoices",
            {
                "user_id": other["id"],
                "invoice_number": other["invoice"],
            },
            columns="id, user_id, customer_id",
        ),
    }

    # Invoice items
    records["invoice_items"] = {
        "own": fetch_one(
            service_supabase,
            "invoice_items",
            {"invoice_id": records["invoices"]["own"]["id"]},
        ),
        "other": fetch_one(
            service_supabase,
            "invoice_items",
            {"invoice_id": records["invoices"]["other"]["id"]},
        ),
    }

    # Payments
    records["payments"] = {
        "own": fetch_one(
            service_supabase,
            "payments",
            {
                "user_id": selected["id"],
                "paypal_order_id": selected["payment"],
            },
        ),
        "other": fetch_one(
            service_supabase,
            "payments",
            {
                "user_id": other["id"],
                "paypal_order_id": other["payment"],
            },
        ),
    }

    # Reminders
    records["reminders"] = {
        "own": fetch_one(
            service_supabase,
            "reminders",
            {
                "user_id": selected["id"],
                "message": (
                    "Security isolation test reminder for "
                    f"{selected['name']}"
                ),
            },
        ),
        "other": fetch_one(
            service_supabase,
            "reminders",
            {
                "user_id": other["id"],
                "message": (
                    "Security isolation test reminder for "
                    f"{other['name']}"
                ),
            },
        ),
    }

    # AI approvals
    records["ai_action_approvals"] = {
        "own": fetch_one(
            service_supabase,
            "ai_action_approvals",
            {"idempotency_key": selected["approval"]},
        ),
        "other": fetch_one(
            service_supabase,
            "ai_action_approvals",
            {"idempotency_key": other["approval"]},
        ),
    }

    # Audit logs
    records["audit_logs"] = {
        "own": fetch_one(
            service_supabase,
            "audit_logs",
            {
                "user_id": selected["id"],
                "action": "security_test",
                "description": selected["audit"],
            },
        ),
        "other": fetch_one(
            service_supabase,
            "audit_logs",
            {
                "user_id": other["id"],
                "action": "security_test",
                "description": other["audit"],
            },
        ),
    }

    for table, table_records in records.items():
        passed = check_read_isolation(
            user_db,
            table,
            table_records["own"]["id"],
            table_records["other"]["id"],
        )

        record(
            f"{table}: cross-user read isolation",
            passed,
        )

    return records


def check_insert_denied(label, table, payload):
    inserted_id = None

    try:
        response = (
            user_db_for_insert.table(table)
            .insert(payload)
            .execute()
        )

        rows = response.data or []

        if rows:
            inserted_id = rows[0].get("id")

        if inserted_id:
            service_supabase.table(table).delete().eq(
                "id", inserted_id
            ).execute()

        record(
            label,
            False,
            "Insert was not rejected by RLS.",
        )

    except Exception as exc:
        code = getattr(exc, "code", None)

        record(
            label,
            code == "42501",
            f"Database error: {code or 'unknown'}",
        )


def run_insert_tests(user_db, selected, records):
    global user_db_for_insert
    user_db_for_insert = user_db

    print("\n--- DIRECT INSERT PERMISSION TESTS ---")

    invoice_id = records["invoices"]["own"]["id"]
    customer_id = records["customers"]["own"]["id"]

    unique = uuid.uuid4().hex
    due_date = (date.today() + timedelta(days=7)).isoformat()
    scheduled_at = datetime.now(timezone.utc).isoformat()

    tests = [
        (
            "invoices",
            {
                "user_id": selected["id"],
                "customer_id": customer_id,
                "invoice_number": f"SECURITY-TEST-{unique}",
                "due_date": due_date,
                "subtotal": 1,
                "tax_amount": 0,
                "total_amount": 1,
            },
        ),
        (
            "invoice_items",
            {
                "invoice_id": invoice_id,
                "description": f"Security test {unique}",
                "quantity": 1,
                "unit_price": 1,
            },
        ),
        (
            "payments",
            {
                "user_id": selected["id"],
                "invoice_id": invoice_id,
                "amount": 1,
                "provider": "paypal",
                "status": "pending",
                "currency": "USD",
            },
        ),
        (
            "reminders",
            {
                "user_id": selected["id"],
                "invoice_id": invoice_id,
                "reminder_type": "custom",
                "channel": "email",
                "status": "scheduled",
                "scheduled_at": scheduled_at,
                "message": f"Security test {unique}",
            },
        ),
        (
            "ai_action_approvals",
            {
                "user_id": selected["id"],
                "invoice_id": invoice_id,
                "action_type": "security_test",
                "description": f"Security test {unique}",
                "idempotency_key": f"security-test-{unique}",
            },
        ),
        (
            "audit_logs",
            {
                "user_id": selected["id"],
                "actor_type": "user",
                "action": "security_test",
                "description": f"Security test {unique}",
            },
        ),
    ]

    for table, payload in tests:
        check_insert_denied(
            f"{table}: INSERT",
            table,
            payload,
        )


def run_update_tests(user_db, records):
    print("\n--- DIRECT UPDATE PERMISSION TESTS ---")

    update_fields = {
        "invoices": ("notes", "RLS-SECURITY-UPDATE-TEST"),
        "invoice_items": ("description", "RLS-SECURITY-UPDATE-TEST"),
        "payments": ("amount", "999999.99"),
        "reminders": ("message", "RLS-SECURITY-UPDATE-TEST"),
        "ai_action_approvals": (
            "description",
            "RLS-SECURITY-UPDATE-TEST",
        ),
        "audit_logs": ("description", "RLS-SECURITY-UPDATE-TEST"),
    }

    for table, (column, test_value) in update_fields.items():
        record_id = records[table]["own"]["id"]
        original = fetch_by_id(service_supabase, table, record_id)

        if not original:
            record(f"{table}: UPDATE", False, "Fixture record missing.")
            continue

        if column == "amount":
            test_value = str(Decimal(str(original[column])) + Decimal("0.01"))

        try:
            user_db.table(table).update({
                column: test_value
            }).eq("id", record_id).execute()

            current = fetch_by_id(service_supabase, table, record_id)

            unchanged = (
                current is not None
                and current.get(column) == original.get(column)
            )

            if not unchanged and current is not None:
                service_supabase.table(table).update({
                    column: original[column]
                }).eq("id", record_id).execute()

            record(
                f"{table}: UPDATE",
                unchanged,
                (
                    "Existing fixture remained unchanged."
                    if unchanged
                    else "Update changed the record or the record disappeared."
                ),
            )

        except Exception as exc:
            code = getattr(exc, "code", None)

            record(
                f"{table}: UPDATE",
                code == "42501",
                f"Database error: {code or 'unknown'}",
            )


def run_delete_tests(user_db, records):
    print("\n--- DIRECT DELETE PERMISSION TESTS ---")

    restricted_tables = [
        "invoices",
        "invoice_items",
        "payments",
        "reminders",
        "ai_action_approvals",
        "audit_logs",
    ]

    for table in restricted_tables:
        record_id = records[table]["own"]["id"]
        original = fetch_by_id(service_supabase, table, record_id)

        if not original:
            record(f"{table}: DELETE", False, "Fixture record missing.")
            continue

        try:
            user_db.table(table).delete().eq(
                "id", record_id
            ).execute()

            current = fetch_by_id(service_supabase, table, record_id)

            if current is not None:
                record(
                    f"{table}: DELETE",
                    True,
                    "Existing fixture remained present.",
                )
            else:
                # Restore the deleted fixture if RLS unexpectedly allowed it.
                service_supabase.table(table).insert(original).execute()

                record(
                    f"{table}: DELETE",
                    False,
                    "Delete succeeded; original fixture was restored.",
                )

        except Exception as exc:
            code = getattr(exc, "code", None)

            record(
                f"{table}: DELETE",
                code == "42501",
                f"Database error: {code or 'unknown'}",
            )


def run_write_tests(user_db, selected, records):
    run_insert_tests(user_db, selected, records)
    run_update_tests(user_db, records)
    run_delete_tests(user_db, records)


def run_customer_ownership_tests(user_db, selected, other):
    print("\n--- CUSTOMER OWNERSHIP-SPOOFING TESTS ---")

    unique_email = (
        f"security-test-{uuid.uuid4().hex}@test.example"
    )

    # Test 1: Insert a customer claiming another user's ownership.
    inserted_customer_id = None

    try:
        response = (
            user_db.table("customers")
            .insert({
                "user_id": other["id"],
                "name": "Unauthorized Ownership Test",
                "email": unique_email,
            })
            .execute()
        )

        rows = response.data or []

        if rows:
            inserted_customer_id = rows[0]["id"]

        if inserted_customer_id:
            service_supabase.table("customers").delete().eq(
                "id", inserted_customer_id
            ).execute()

        record(
            "Customer INSERT with another user's user_id",
            False,
            "Insert was not rejected by RLS.",
        )

    except Exception as exc:
        code = getattr(exc, "code", None)

        record(
            "Customer INSERT with another user's user_id",
            code == "42501",
            f"Database error: {code or 'unknown'}",
        )

    # Test 2: Attempt to transfer an existing customer's ownership.
    own_customer = fetch_one(
        service_supabase,
        "customers",
        {
            "user_id": selected["id"],
            "email": selected["customer"],
        },
        columns="id, user_id",
    )

    customer_id = own_customer["id"]

    try:
        user_db.table("customers").update({
            "user_id": other["id"]
        }).eq("id", customer_id).execute()

        current_owner = fetch_one(
            service_supabase,
            "customers",
            {"id": customer_id},
            columns="id, user_id",
        )

        unchanged = current_owner["user_id"] == selected["id"]

        if not unchanged:
            service_supabase.table("customers").update({
                "user_id": selected["id"]
            }).eq("id", customer_id).execute()

        record(
            "Customer UPDATE changing user_id",
            unchanged,
            (
                "Ownership remained unchanged."
                if unchanged
                else "Ownership changed unexpectedly and was restored."
            ),
        )

    except Exception as exc:
        code = getattr(exc, "code", None)

        record(
            "Customer UPDATE changing user_id",
            code == "42501",
            f"Database error: {code or 'unknown'}",
        )


def run_user_suite(choice):
    selected = USERS[choice]
    other = USERS["2" if choice == "1" else "1"]

    print(f"\n{'=' * 55}")
    print(f"TESTING: {selected['name']}")
    print("=" * 55)

    email = input(f"{selected['name']} email: ")
    password = getpass.getpass(
        f"{selected['name']} password: "
    )

    auth_client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )

    try:
        login = auth_client.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        if not login.session:
            raise RuntimeError("Authentication failed.")

        if str(login.user.id) != selected["id"]:
            raise RuntimeError("Incorrect test account.")

        user_db = app.integrations.supabase.create_user_supabase_client(
            login.session.access_token
        )

        records = run_read_tests(user_db, selected, other)

        run_write_tests(user_db, selected, records)

        run_customer_ownership_tests(
            user_db,
            selected,
            other,
        )

    finally:
        try:
            auth_client.auth.sign_out()
        except Exception:
            pass


def main():
    print("\n========================================")
    print("       PAYFLOW AI SECURITY SUITE")
    print("========================================")

    for choice in ("1", "2"):
        run_user_suite(choice)

    print("\n========================================")
    print("           FINAL TEST REPORT")
    print("========================================")

    passed = sum(1 for _, status in results if status)
    failed = len(results) - passed

    for label, status in results:
        print(f"[{'PASS' if status else 'FAIL'}] {label}")

    print("\nTotal tests:", len(results))
    print("Passed:", passed)
    print("Failed:", failed)

    if failed == 0:
        print("\nALL TESTS PASSED.")
    else:
        print("\nSECURITY TEST FAILURES DETECTED.")
        sys.exit(1)


if __name__ == "__main__":
    main()