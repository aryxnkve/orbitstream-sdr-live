"""
ORBITSTREAM — Satellite Stream Analysis Platform
FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import get_config
from .api.routes import router
from .api.sdr_routes import router as sdr_router, db

config = get_config()

# Path to built frontend distribution files
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
)


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

# CORS for frontend dev server & deployed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(router, prefix="/api")
app.include_router(sdr_router, prefix="/api")

# Mount frontend assets if compiled
assets_dir = os.path.join(FRONTEND_DIST, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
async def root(request: Request):
    """
    Root endpoint:
    - If accessed from a web browser (Accept: text/html) and frontend is built, serves index.html.
    - Otherwise returns JSON API discovery metadata.
    """
    accept = request.headers.get("accept", "")
    index_file = os.path.join(FRONTEND_DIST, "index.html")

    if "text/html" in accept and os.path.isfile(index_file):
        return FileResponse(index_file)

    return {
        "name": "ORBITSTREAM",
        "description": "Satellite stream analysis and physical SDR monitoring API",
        "version": "0.1.0",
        "docs": "/docs",
        "sdr_ingest_endpoint": "/api/sdr/ingest",
        "frontend_available": os.path.isfile(index_file),
    }


@app.get("/{full_path:path}")
async def serve_spa_routes(request: Request, full_path: str):
    """Catch-all handler to support SPA client routing for built frontend."""
    if full_path.startswith("api") or full_path in ("docs", "openapi.json"):
        raise HTTPException(status_code=404, detail="API route not found")

    target = os.path.join(FRONTEND_DIST, full_path)
    if os.path.isfile(target):
        return FileResponse(target)

    index_file = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Resource not found")
