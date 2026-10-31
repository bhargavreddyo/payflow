
import sys
import getpass
import httpx

sys.path.insert(0, "backend")

from supabase import create_client
from app.core.config import settings

email = input("Supabase test account email: ")
password = getpass.getpass("Supabase password: ")

client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ANON_KEY,
)

try:
    login = client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })

    if not login.session:
        print("Login failed: no session returned.")
        raise SystemExit(1)

    access_token = login.session.access_token

    response = httpx.get(
        "http://127.0.0.1:8000/api/v1/me/profile",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=20,
    )

    print("\nAPI status:", response.status_code)
    print("API response:", response.text)

finally:
    try:
        client.auth.sign_out()
    except Exception:
        pass
