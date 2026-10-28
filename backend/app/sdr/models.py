"""
Data models and schemas for RTL-SDR measurements, anomalies, and collector credentials.
Includes both SQLAlchemy ORM models (supporting PostgreSQL & SQLite) and Pydantic v2 schemas.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ── SQLAlchemy Database Tables ──────────────────────────────────────────

class SDRMeasurementModel(Base):
    """Persistent storage for RTL-SDR physical layer telemetry records."""
    __tablename__ = "sdr_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(100), index=True, nullable=False)
    timestamp = Column(String(50), index=True, nullable=False)  # ISO 8601 UTC
    center_frequency_hz = Column(Float, nullable=False)
    sample_rate_hz = Column(Float, nullable=False)
    gain = Column(String(50), default="auto")
    relative_power_dbfs = Column(Float, nullable=False)
    peak_power_dbfs = Column(Float, default=-120.0)
    papr_db = Column(Float, default=0.0)
    snr_estimate_db = Column(Float, default=0.0)
    noise_floor_dbfs = Column(Float, default=-120.0)
    dc_i = Column(Float, default=0.0)
    dc_q = Column(Float, default=0.0)
    clipping_ratio = Column(Float, default=0.0)
    spectrum_bins = Column(Text, default="[]")  # JSON-encoded array of floats
    sample_count = Column(Integer, default=0)
    is_valid = Column(Boolean, default=True)
    validation_notes = Column(Text, default="")
    mode = Column(String(20), default="hardware")  # 'hardware' or 'demo'
    device_type = Column(String(100), default="RTL-SDR")
    serial = Column(String(100), default="Unknown")
    is_synthetic = Column(Boolean, default=False)
    created_at = Column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert database record to Python dictionary."""
        try:
            bins = json.loads(self.spectrum_bins) if self.spectrum_bins else []
        except Exception:
            bins = []

        return {
            "id": self.id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "center_frequency_hz": self.center_frequency_hz,
            "sample_rate_hz": self.sample_rate_hz,
            "gain": self.gain,
            "relative_power_dbfs": self.relative_power_dbfs,
            "peak_power_dbfs": self.peak_power_dbfs,
            "papr_db": self.papr_db,
            "snr_estimate_db": self.snr_estimate_db,
            "noise_floor_dbfs": self.noise_floor_dbfs,
            "dc_i": self.dc_i,
            "dc_q": self.dc_q,
            "clipping_ratio": self.clipping_ratio,
            "spectrum_bins": bins,
            "sample_count": self.sample_count,
            "is_valid": self.is_valid,
            "validation_notes": self.validation_notes,
            "mode": self.mode,
            "device_type": self.device_type,
            "serial": self.serial,
            "is_synthetic": self.is_synthetic,
            "created_at": self.created_at,
        }


class SDRAnomalyModel(Base):
    """Persistent storage for signal anomaly events, deduplication, and recovery tracking."""
    __tablename__ = "sdr_anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(100), index=True, nullable=False)
    rule_id = Column(String(100), index=True, nullable=False)
    severity = Column(String(20), nullable=False)  # 'CRITICAL', 'ERROR', 'WARNING', 'INFO'
    title = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=False)
    metric_name = Column(String(100), nullable=False)
    threshold_value = Column(Float, nullable=False)
    observed_value = Column(Float, nullable=False)
    timestamp = Column(String(50), nullable=False)  # First detected ISO 8601 UTC
    last_seen = Column(String(50), nullable=False)   # Most recent occurrence ISO 8601 UTC
    occurrence_count = Column(Integer, default=1)
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(String(50), nullable=True)
    recovery_note = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "explanation": self.explanation,
            "metric_name": self.metric_name,
            "threshold_value": self.threshold_value,
            "observed_value": self.observed_value,
            "timestamp": self.timestamp,
            "last_seen": self.last_seen,
            "occurrence_count": self.occurrence_count,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "recovery_note": self.recovery_note,
        }


class SDRCollectorKeyModel(Base):
    """Storage for revocable collector API authentication credentials."""
    __tablename__ = "sdr_collector_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(128), unique=True, index=True, nullable=False)
    key_prefix = Column(String(20), nullable=False)  # First 6 characters for recognition
    label = Column(String(100), default="Collector Credential")
    created_at = Column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(String(50), nullable=True)


# ── Pydantic Request & Response Schemas ─────────────────────────────────

class SDRMeasurementPayload(BaseModel):
    """Schema for authenticated collector ingestion requests."""
    timestamp: str = Field(description="ISO 8601 UTC timestamp of measurement")
    device_id: str = Field(min_length=1, max_length=100, description="Station or device identity")
    mode: str = Field(default="hardware", description="'hardware' or 'demo'")
    center_frequency_hz: float = Field(gt=0, le=30e9, description="Center frequency in Hz")
    sample_rate_hz: float = Field(gt=0, le=100e6, description="Sampling rate in Hz")
    gain: str = Field(default="auto", description="Tuner gain string or dB value")
    relative_power_dbfs: float = Field(ge=-250.0, le=50.0, description="Relative complex power in dBFS")
    peak_power_dbfs: float = Field(default=-120.0, ge=-250.0, le=50.0)
    papr_db: float = Field(default=0.0, ge=0.0, le=60.0)
    snr_estimate_db: float = Field(default=0.0, ge=0.0, le=150.0)
    noise_floor_dbfs: float = Field(default=-120.0, ge=-250.0, le=50.0)
    dc_i: float = Field(default=0.0, ge=-5.0, le=5.0)
    dc_q: float = Field(default=0.0, ge=-5.0, le=5.0)
    clipping_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    spectrum_bins: List[float] = Field(default_factory=list, description="Downsampled FFT bins (dBFS)")
    sample_count: int = Field(default=0, ge=0)
    is_valid: bool = Field(default=True, description="Whether measurement was successfully acquired from hardware")
    validation_notes: str = Field(default="", description="Diagnostic notes if sample acquisition failed")
    device_info: Optional[Dict[str, Any]] = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_format(cls, v: str) -> str:
        # Validate ISO 8601 string
        try:
            # Handle Z or +00:00
            iso_str = v.replace("Z", "+00:00")
            datetime.fromisoformat(iso_str)
            return v
        except Exception:
            raise ValueError(f"Invalid timestamp '{v}'. Expected ISO 8601 UTC format.")


class SDRMeasurementResponse(BaseModel):
    """Schema for individual measurement response."""
    id: int
    device_id: str
    timestamp: str
    center_frequency_hz: float
    sample_rate_hz: float
    gain: str
    relative_power_dbfs: float
    peak_power_dbfs: float
    papr_db: float
    snr_estimate_db: float
    noise_floor_dbfs: float
    dc_i: float
    dc_q: float
    clipping_ratio: float
    spectrum_bins: List[float]
    sample_count: int
    is_valid: bool
    validation_notes: str
    mode: str
    device_type: str
    serial: str
    is_synthetic: bool
    created_at: str


class SDRAnomalyResponse(BaseModel):
    """Schema for anomaly event response."""
    id: int
    device_id: str
    rule_id: str
    severity: str
    title: str
    explanation: str
    metric_name: str
    threshold_value: float
    observed_value: float
    timestamp: str
    last_seen: str
    occurrence_count: int
    resolved: bool
    resolved_at: Optional[str] = None
    recovery_note: Optional[str] = None


class SDRStatusResponse(BaseModel):
    """Summary status of collector device, latest telemetry, and active anomalies."""
    status: str  # 'active', 'degraded', 'offline', 'demo'
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    is_synthetic: bool = False
    mode: str = "hardware"
    last_seen: Optional[str] = None
    frequency_mhz: Optional[float] = None
    sample_rate_msps: Optional[float] = None
    relative_power_dbfs: Optional[float] = None
    snr_estimate_db: Optional[float] = None
    active_anomaly_count: int = 0
    active_anomalies: List[SDRAnomalyResponse] = Field(default_factory=list)
    latest_measurement: Optional[SDRMeasurementResponse] = None

