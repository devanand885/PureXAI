"""
main.py — PureXAI FastAPI application entry point.

Responsibilities:
  - Configure FastAPI app with metadata, CORS, logging
  - Register all routers
  - Initialize DB on startup
  - Start APScheduler background jobs (sensor health + disconnection check)
  - Provide root health-check endpoint
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from config import settings, HEALTH_CHECK_INTERVAL_SECONDS
from database import init_db
from routers import esp32, dashboard, alerts
from services.sensor_health import run_sensor_health_check
from services.disconnection import run_disconnection_check

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("purexai.main")

# ---------------------------------------------------------------------------
# APScheduler
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler(timezone="UTC")


def _start_scheduler():
    scheduler.add_job(
        run_sensor_health_check,
        trigger="interval",
        seconds=HEALTH_CHECK_INTERVAL_SECONDS,
        id="sensor_health_check",
        replace_existing=True,
    )
    scheduler.add_job(
        run_disconnection_check,
        trigger="interval",
        seconds=HEALTH_CHECK_INTERVAL_SECONDS,
        id="disconnection_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"⏰ Background scheduler started "
        f"(interval: {HEALTH_CHECK_INTERVAL_SECONDS}s)"
    )


# ---------------------------------------------------------------------------
# Lifespan (startup + shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("🚀 PureXAI backend starting up...")
    init_db()
    logger.info("✅ Database initialised")
    _start_scheduler()

    yield   # app is running

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("🛑 PureXAI backend shutting down...")
    scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend API for PureXAI Water Quality Monitoring System.\n\n"
        "Receives data from ESP32 sensors, stores it, checks water quality "
        "thresholds, monitors sensor health, and exposes dashboard APIs."
    ),
    contact={
        "name": "PureXAI Team — Devanand",
    },
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow Streamlit dashboard and development tools
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(esp32.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)


# ---------------------------------------------------------------------------
# Root / health-check
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"], summary="Root health check")
async def root():
    return {
        "service":    settings.APP_NAME,
        "version":    settings.APP_VERSION,
        "status":     "running",
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "docs":       "/docs",
        "redoc":      "/redoc",
    }


@app.get("/health", tags=["Health"], summary="Detailed health check")
async def health_check():
    """Returns service health. Used by load balancers / monitoring tools."""
    return {
        "status":    "healthy",
        "scheduler": "running" if scheduler.running else "stopped",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
