
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client, create_client
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthInvalidJwtError,
    AuthRetryableError,
)

from app.core.config import settings
from app.integrations.supabase import create_user_supabase_client

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    id: str
    email: Optional[str] = None


@dataclass
class AuthenticatedContext:
    user: AuthenticatedUser
    db: Client


def get_authenticated_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        bearer_scheme
    ),
) -> AuthenticatedContext:

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not token or len(token) > 8192:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Isolated authentication client using the publishable key.
        auth_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
        )

        # Verify JWT signature and expiration.
        claims_response = auth_client.auth.get_claims(jwt=token)

        if not claims_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        if isinstance(claims_response, dict):
            claims = claims_response.get("claims", claims_response)
        else:
            claims = getattr(claims_response, "claims", None)

        if not isinstance(claims, dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        verified_sub = claims.get("sub")

        if not verified_sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        # Confirm the user still exists in Supabase Auth.
        user_response = auth_client.auth.get_user(jwt=token)

        if isinstance(user_response, dict):
            user = user_response.get("user")
        else:
            user = getattr(user_response, "user", None)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            )

        if isinstance(user, dict):
            user_id = user.get("id")
            user_email = user.get("email")
        else:
            user_id = getattr(user, "id", None)
            user_email = getattr(user, "email", None)

        if not user_id or str(user_id) != str(verified_sub):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        # Create a fresh database client for this user's JWT.
        user_db = create_user_supabase_client(token)

        return AuthenticatedContext(
            user=AuthenticatedUser(
                id=str(user_id),
                email=user_email,
            ),
            db=user_db,
        )

    except HTTPException:
        raise

    except (
        AuthInvalidJwtError,
        AuthInvalidCredentialsError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except AuthApiError as exc:
        if getattr(exc, "status", None) in (400, 401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.exception("Supabase authentication service error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )

    except (AuthRetryableError, httpx.HTTPError):
        logger.exception("Supabase authentication connection failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )


def get_current_user(
    context: AuthenticatedContext = Depends(get_authenticated_context),
) -> AuthenticatedUser:
    return context.user
