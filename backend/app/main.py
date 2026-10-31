
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.core.security import (
    get_current_user,
    AuthenticatedUser,
    get_authenticated_context,
    AuthenticatedContext,
)

app = FastAPI(
    title="PayFlow AI API",
    description="AI-powered invoice and payment automation platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to PayFlow AI",
        "status": "running",
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "application": "PayFlow AI",
        "version": "1.0.0",
    }


@app.get("/api/v1/me")
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    return {
        "authenticated": True,
        "user_id": current_user.id,
        "email": current_user.email,
    }


@app.get("/api/v1/me/profile")
async def get_my_profile(
    context: AuthenticatedContext = Depends(get_authenticated_context),
):
    response = (
        context.db
        .table("profiles")
        .select("id, full_name, business_name, currency")
        .eq("id", context.user.id)
        .maybe_single()
        .execute()
    )

    return {
        "user_id": context.user.id,
        "profile": response.data,
    }
