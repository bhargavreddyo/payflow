
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PayFlow AI API",
    description="AI-powered invoice and payment automation platform",
    version="1.0.0"
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
        "status": "running"
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "application": "PayFlow AI",
        "version": "1.0.0"
    }
