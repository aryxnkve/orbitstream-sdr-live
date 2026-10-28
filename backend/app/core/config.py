"""
Application configuration.
"""
import os
from pydantic import BaseModel


class AppConfig(BaseModel):
    """Application-level configuration."""
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://orbitstream.onrender.com",
    ]
    max_upload_size: int = 500 * 1024 * 1024  # 500 MB
    storage_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    fixtures_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fixtures")
    database_url: str = ""
    collector_api_key: str = "orbitstream-collector-key-2026"
    debug: bool = False


def get_config() -> AppConfig:
    """Get application configuration."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("ORBITSTREAM_DATABASE_URL") or ""
    api_key = os.environ.get("ORBITSTREAM_COLLECTOR_API_KEY") or os.environ.get("SDR_API_KEY") or "orbitstream-collector-key-2026"
    custom_origins = os.environ.get("CORS_ORIGINS")
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://orbitstream.onrender.com",
    ]
    if custom_origins:
        origins.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

    return AppConfig(
        host=os.environ.get("ORBITSTREAM_HOST", "127.0.0.1"),
        port=int(os.environ.get("ORBITSTREAM_PORT", "8000")),
        cors_origins=origins,
        database_url=db_url,
        collector_api_key=api_key,
        debug=os.environ.get("ORBITSTREAM_DEBUG", "").lower() in ("1", "true"),
    )
