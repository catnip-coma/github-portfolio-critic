import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import router as api_router
from app.services.github_client import GitHubClientError

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="GitGauge - Recruiter-grade GitHub Portfolio Critic & Auditor",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local development and demos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for GitHubClientError
@app.exception_handler(GitHubClientError)
async def github_client_exception_handler(request: Request, exc: GitHubClientError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "detail": exc.message, "status_code": exc.status_code}
    )

# Include API routes
app.include_router(api_router, prefix="/api")

# Ensure static & templates directories exist
os.makedirs("app/static", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    """Temporary root endpoint for Hour 1 status verification."""
    return {
        "message": "Welcome to GitGauge API",
        "status": "ready",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "github_profile": "/api/raw/{username}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
