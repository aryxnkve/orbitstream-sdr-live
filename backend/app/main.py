"""
ORBITSTREAM — Satellite Stream Analysis Platform
FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_config
from .api.routes import router
from .api.sdr_routes import router as sdr_router, db

config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: initialize database tables and clean shutdown."""
    try:
        await db.initialize(config.collector_api_key)
    except Exception as exc:
        print(f"[Warning] Could not initialize SDR database on startup: {exc}")
    yield
    try:
        await db.close()
    except Exception:
        pass


app = FastAPI(
    title="ORBITSTREAM",
    description="Satellite stream analysis and physical SDR monitoring API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(sdr_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "ORBITSTREAM",
        "description": "Satellite stream analysis and physical SDR monitoring API",
        "version": "0.1.0",
        "docs": "/docs",
        "sdr_ingest_endpoint": "/api/sdr/ingest",
    }
