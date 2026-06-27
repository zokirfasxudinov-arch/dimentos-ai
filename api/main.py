"""
Dimentos AI Studio OS - FastAPI Application Entry Point
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from core.config import settings
from core.database import check_db_health, create_tables
from core.scheduler import scheduler, setup_scheduler
from api.routers import health, approvals, agents, tasks, projects, memory, github, finance, logs, ai as ai_router
from api.routers import leads as leads_router
from api.routers import opportunities as opp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info("Dimentos AI Studio OS starting up...")
    logger.info(f"Available AI providers: {settings.available_providers}")
    await create_tables()
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Dimentos AI Studio OS shutting down...")


app = FastAPI(
    title="Dimentos AI Studio OS",
    description="AI-powered studio operating system with human-in-the-loop approval flows",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - allow web panel and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.app_url,
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(approvals.router, prefix="/api", tags=["approvals"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(memory.router, prefix="/api", tags=["memory"])
app.include_router(github.router, prefix="/api", tags=["github"])
app.include_router(finance.router, prefix="/api", tags=["finance"])
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(ai_router.router, prefix="/api", tags=["ai"])
app.include_router(leads_router.router, prefix="/api", tags=["leads"])
app.include_router(opp_router.router, prefix="/api", tags=["crm"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Dimentos AI Studio OS",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
