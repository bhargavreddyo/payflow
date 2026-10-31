
from supabase import Client, create_client

from app.core.config import settings


# --------------------------------------------------
# Trusted backend client
# --------------------------------------------------
# Uses the secret/service-role key.
# Bypasses RLS. Only use for trusted backend operations
# with explicit ownership and authorization checks.

service_supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY,
)


# --------------------------------------------------
# User-scoped client factory
# --------------------------------------------------
# Creates a fresh client for each authenticated request.
# Uses the publishable key + user's verified access token.
# Database operations are subject to Supabase RLS.

def create_user_supabase_client(access_token: str) -> Client:
    if not access_token:
        raise ValueError("A valid access token is required")

    client: Client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )

    # Attach the user's JWT to PostgREST requests.
    client.postgrest.auth(access_token)

    return client
