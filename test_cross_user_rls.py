
import sys
import getpass
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from supabase import create_client
from app.core.config import settings  # type: ignore[reportMissingImports]
import app.integrations.supabase  # type: ignore[reportMissingImports]


if not settings.TEST_USER_A_ID or not settings.TEST_USER_B_ID:
    raise RuntimeError(
        "TEST_USER_A_ID and TEST_USER_B_ID must be configured in .env"
    )


TEST_USERS = {
    "1": {
        "name": "User A",
        "id": settings.TEST_USER_A_ID,
        "invoice_number": "TEST-INV-A001",
    },
    "2": {
        "name": "User B",
        "id": settings.TEST_USER_B_ID,
        "invoice_number": "TEST-INV-B001",
    },
}


def expect_denied(label, operation):
    try:
        result = operation()

        # An empty result means no rows were affected.
        # It does not, by itself, prove that RLS blocked the operation.
        if result.data:
            print(f"FAIL: {label} unexpectedly affected rows.")
            return False

        print(f"PASS: {label} did not modify any records.")
        return True

    except Exception as exc:
        error_code = getattr(exc, "code", None)

        if error_code == "42501":
            print(f"PASS: {label} was rejected by database permissions/RLS.")
            return True

        print(f"ERROR: {label} failed for another reason.")
        print("       Database response:", str(exc)[:250])
        return False


print("\n--- PAYMENT WRITE-PROTECTION TEST ---")
print("1. User A")
print("2. User B")

choice = input("\nSelect account (1 or 2): ").strip()

if choice not in TEST_USERS:
    raise ValueError("Invalid selection.")

selected = TEST_USERS[choice]

email = input(f"\n{selected['name']} email: ")
password = getpass.getpass(f"{selected['name']} password: ")

auth_client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ANON_KEY,
)

try:
    # Authenticate selected user.
    login = auth_client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })

    if not login.session:
        raise RuntimeError("Login failed.")

    if str(login.user.id) != selected["id"]:
        raise RuntimeError(
            f"Wrong account. Please sign in as {selected['name']}."
        )

    # Create authenticated user-scoped client.
    user_db = app.integrations.supabase.create_user_supabase_client(
        login.session.access_token
    )

    # Retrieve a real invoice ID for the insert attempt.
    invoice_result = (
        user_db.table("invoices")
        .select("id")
        .eq("invoice_number", selected["invoice_number"])
        .execute()
    )

    invoices = invoice_result.data or []

    if len(invoices) != 1:
        raise RuntimeError("Own test invoice not found.")

    invoice_id = invoices[0]["id"]

    # Use a random ID for the UPDATE and DELETE attempts.
    fake_payment_id = str(uuid.uuid4())

    print("\n--- TEST RESULTS ---")

    # Test 1: Attempt payment insertion.
    insert_passed = expect_denied(
        "Direct payment INSERT",
        lambda: user_db.table("payments").insert({
            "user_id": selected["id"],
            "invoice_id": invoice_id,
            "provider": "paypal",
            "paypal_order_id": f"SECURITY-TEST-{uuid.uuid4()}",
            "amount": 1,
            "currency": "USD",
            "status": "pending",
            "payment_method": "paypal",
        }).execute(),
    )

    # Test 2: Attempt payment update on a nonexistent ID.
    update_passed = expect_denied(
        "Direct payment UPDATE",
        lambda: user_db.table("payments")
        .update({"status": "failed"})
        .eq("id", fake_payment_id)
        .execute(),
    )

    # Test 3: Attempt payment deletion on a nonexistent ID.
    delete_passed = expect_denied(
        "Direct payment DELETE",
        lambda: user_db.table("payments")
        .delete()
        .eq("id", fake_payment_id)
        .execute(),
    )

    print("\n--- SUMMARY ---")

    if insert_passed and update_passed and delete_passed:
        print("PASS: All three checks completed without modifying records.")
        print(
            "NOTE: UPDATE and DELETE used a nonexistent ID; "
            "they do not independently prove RLS protection."
        )
    else:
        print("FAIL: At least one check needs investigation.")

finally:
    try:
        auth_client.auth.sign_out()
    except Exception:
        pass
