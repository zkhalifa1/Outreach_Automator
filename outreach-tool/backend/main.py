"""FastAPI application entry point.

Outreach Automation Tool — Backend API
Run with: uvicorn main:app --host 127.0.0.1 --port 8000 --reload
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from models.database import init_database
from services.scheduler import start_scheduler, stop_scheduler
from routes.dashboard import router as dashboard_router
from routes.outreach import router as outreach_router
from routes.logs import router as logs_router
from routes.auth_routes import router as auth_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting Outreach Automation Tool...")
    init_database()
    start_scheduler()
    logger.info(f"Server running at http://{settings.app_host}:{settings.app_port}")
    yield
    # Shutdown
    stop_scheduler()
    logger.info("Outreach Automation Tool shut down.")


app = FastAPI(
    title="Outreach Automation Tool",
    description="Automated email outreach for architecture firm business development.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend (dev server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(outreach_router)
app.include_router(logs_router)


# Serve the single-file React dashboard
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def root():
    """Serve the dashboard UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    from auth.msal_auth import auth

    return {
        "status": "healthy",
        "authenticated": auth.is_authenticated(),
        "onedrive_path": settings.onedrive_file_path or "Not configured",
        "follow_up_days": settings.follow_up_days,
        "max_follow_ups": settings.max_follow_ups,
    }
