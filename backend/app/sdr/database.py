"""
Asynchronous database manager for persistent RTL-SDR measurements and anomalies.
Supports PostgreSQL (via asyncpg, standard on Render) and SQLite (via aiosqlite for local/offline dev).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import (
    Base,
    SDRAnomalyModel,
    SDRCollectorKeyModel,
    SDRMeasurementModel,
    SDRMeasurementPayload,
)

logger = logging.getLogger("orbitstream.sdr_db")


def hash_key(key: str) -> str:
    """Compute SHA-256 hash of API key for safe storage and verification."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class SDRDatabase:
    """Async database abstraction for PostgreSQL and SQLite."""

    def __init__(self, db_url: str = "", storage_dir: str = "data") -> None:
        self.storage_dir = storage_dir
        self.raw_url = db_url

        # Format URL for SQLAlchemy async drivers
        if db_url.startswith("postgres://"):
            # Render PostgreSQL URL compatibility
            self.db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
            self.db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("sqlite"):
            self.db_url = db_url
        elif db_url:
            self.db_url = db_url
        else:
            # Default local SQLite file
            os.makedirs(storage_dir, exist_ok=True)
            db_path = os.path.join(storage_dir, "orbitstream_sdr.db")
            # Convert backslashes for Windows sqlite URI
            clean_path = os.path.abspath(db_path).replace("\\", "/")
            self.db_url = f"sqlite+aiosqlite:///{clean_path}"

        self.engine = create_async_engine(
            self.db_url,
            echo=False,
            future=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        self._initialized = False

    async def initialize(self, default_api_key: str = "orbitstream-collector-key-2026") -> None:
        """Create database tables and ensure default API key registration."""
        if self._initialized:
            return

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Register default API key if not already present
        async with self.session_factory() as session:
            key_h = hash_key(default_api_key)
            result = await session.execute(
                select(SDRCollectorKeyModel).where(SDRCollectorKeyModel.key_hash == key_h)
            )
            existing = result.scalars().first()
            if not existing:
                default_key = SDRCollectorKeyModel(
                    key_hash=key_h,
                    key_prefix=default_api_key[:6] if len(default_api_key) >= 6 else default_api_key,
                    label="Default Environment Collector Credential",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    is_revoked=False,
                )
                session.add(default_key)
                await session.commit()

        self._initialized = True
        logger.info(f"SDR Database initialized successfully with target: {self.db_url.split('@')[-1]}")

    async def validate_api_key(self, provided_key: str, env_default_key: str) -> bool:
        """
        Validate whether the provided collector API key is valid and not revoked.
        Checks both database records and environment default.
        """
        if not provided_key:
            return False

        await self.initialize()
        h = hash_key(provided_key)
        async with self.session_factory() as session:
            result = await session.execute(
                select(SDRCollectorKeyModel).where(SDRCollectorKeyModel.key_hash == h)
            )
            key_record = result.scalars().first()

            if key_record:
                # Key explicitly found in database
                return not key_record.is_revoked

            # If not in DB, check against env default
            if provided_key == env_default_key:
                return True

            return False

    async def revoke_api_key(self, key_string: str) -> bool:
        """Revoke a collector credential by key or hash."""
        await self.initialize()
        h = hash_key(key_string)
        now_utc = datetime.now(timezone.utc).isoformat()
        async with self.session_factory() as session:
            result = await session.execute(
                select(SDRCollectorKeyModel).where(SDRCollectorKeyModel.key_hash == h)
            )
            key_record = result.scalars().first()
            if key_record:
                key_record.is_revoked = True
                key_record.revoked_at = now_utc
            else:
                # Add as revoked
                revoked_key = SDRCollectorKeyModel(
                    key_hash=h,
                    key_prefix=key_string[:6] if len(key_string) >= 6 else key_string,
                    label="Revoked Credential",
                    created_at=now_utc,
                    is_revoked=True,
                    revoked_at=now_utc,
                )
                session.add(revoked_key)
            await session.commit()
            return True

    async def insert_measurement(self, payload: SDRMeasurementPayload) -> SDRMeasurementModel:
        """Persist a new telemetry measurement in the database."""
        await self.initialize()

        dev_info = payload.device_info or {}
        dev_type = dev_info.get("device_type", "RTL-SDR (Hardware)")
        serial = dev_info.get("serial", "Unknown")
        is_synth = dev_info.get("is_synthetic", payload.mode == "demo")

        record = SDRMeasurementModel(
            device_id=payload.device_id,
            timestamp=payload.timestamp,
            center_frequency_hz=payload.center_frequency_hz,
            sample_rate_hz=payload.sample_rate_hz,
            gain=str(payload.gain),
            relative_power_dbfs=payload.relative_power_dbfs,
            peak_power_dbfs=payload.peak_power_dbfs,
            papr_db=payload.papr_db,
            snr_estimate_db=payload.snr_estimate_db,
            noise_floor_dbfs=payload.noise_floor_dbfs,
            dc_i=payload.dc_i,
            dc_q=payload.dc_q,
            clipping_ratio=payload.clipping_ratio,
            spectrum_bins=json.dumps(payload.spectrum_bins),
            sample_count=payload.sample_count,
            is_valid=payload.is_valid,
            validation_notes=payload.validation_notes,
            mode=payload.mode,
            device_type=dev_type,
            serial=serial,
            is_synthetic=is_synth,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        async with self.session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_latest_measurement(self, device_id: Optional[str] = None) -> Optional[SDRMeasurementModel]:
        """Retrieve the most recent measurement."""
        await self.initialize()
        async with self.session_factory() as session:
            query = select(SDRMeasurementModel).order_by(desc(SDRMeasurementModel.id))
            if device_id:
                query = query.where(SDRMeasurementModel.device_id == device_id)
            result = await session.execute(query.limit(1))
            return result.scalars().first()

    async def get_measurements_history(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        device_id: Optional[str] = None,
    ) -> List[SDRMeasurementModel]:
        """Query historical measurements with time-range filtering and limit."""
        await self.initialize()
        async with self.session_factory() as session:
            query = select(SDRMeasurementModel).order_by(desc(SDRMeasurementModel.id))
            if device_id:
                query = query.where(SDRMeasurementModel.device_id == device_id)
            if start_time:
                query = query.where(SDRMeasurementModel.timestamp >= start_time)
            if end_time:
                query = query.where(SDRMeasurementModel.timestamp <= end_time)

            capped_limit = max(1, min(limit, 2000))
            result = await session.execute(query.limit(capped_limit))
            records = list(result.scalars().all())
            # Return in chronological order
            records.reverse()
            return records

    async def upsert_anomaly(
        self,
        device_id: str,
        rule_id: str,
        severity: str,
        title: str,
        explanation: str,
        metric_name: str,
        threshold_value: float,
        observed_value: float,
        timestamp: str,
    ) -> SDRAnomalyModel:
        """
        Deduplicating anomaly recorder:
        If an open (unresolved) anomaly for this (device_id, rule_id) exists, update its last_seen
        and increment occurrence_count rather than creating a duplicate row.
        If none exists, create a new anomaly event.
        """
        await self.initialize()
        async with self.session_factory() as session:
            query = select(SDRAnomalyModel).where(
                SDRAnomalyModel.device_id == device_id,
                SDRAnomalyModel.rule_id == rule_id,
                SDRAnomalyModel.resolved == False,
            )
            result = await session.execute(query)
            existing = result.scalars().first()

            if existing:
                existing.last_seen = timestamp
                existing.occurrence_count += 1
                existing.observed_value = observed_value
                existing.severity = severity
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                new_anomaly = SDRAnomalyModel(
                    device_id=device_id,
                    rule_id=rule_id,
                    severity=severity,
                    title=title,
                    explanation=explanation,
                    metric_name=metric_name,
                    threshold_value=threshold_value,
                    observed_value=observed_value,
                    timestamp=timestamp,
                    last_seen=timestamp,
                    occurrence_count=1,
                    resolved=False,
                )
                session.add(new_anomaly)
                await session.commit()
                await session.refresh(new_anomaly)
                return new_anomaly

    async def resolve_anomaly(
        self,
        device_id: str,
        rule_id: str,
        resolved_at: str,
        recovery_note: str,
    ) -> Optional[SDRAnomalyModel]:
        """
        Mark an active anomaly as resolved when metrics return to nominal threshold.
        """
        await self.initialize()
        async with self.session_factory() as session:
            query = select(SDRAnomalyModel).where(
                SDRAnomalyModel.device_id == device_id,
                SDRAnomalyModel.rule_id == rule_id,
                SDRAnomalyModel.resolved == False,
            )
            result = await session.execute(query)
            existing = result.scalars().first()

            if existing:
                existing.resolved = True
                existing.resolved_at = resolved_at
                existing.recovery_note = recovery_note
                await session.commit()
                await session.refresh(existing)
                return existing
            return None

    async def get_active_anomalies(self, device_id: Optional[str] = None) -> List[SDRAnomalyModel]:
        """Fetch all currently open/active anomalies."""
        await self.initialize()
        async with self.session_factory() as session:
            query = select(SDRAnomalyModel).where(SDRAnomalyModel.resolved == False).order_by(desc(SDRAnomalyModel.id))
            if device_id:
                query = query.where(SDRAnomalyModel.device_id == device_id)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_anomalies_history(
        self,
        resolved: Optional[bool] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        device_id: Optional[str] = None,
    ) -> List[SDRAnomalyModel]:
        """Fetch anomaly history with optional filters."""
        await self.initialize()
        async with self.session_factory() as session:
            query = select(SDRAnomalyModel).order_by(desc(SDRAnomalyModel.id))
            if device_id:
                query = query.where(SDRAnomalyModel.device_id == device_id)
            if resolved is not None:
                query = query.where(SDRAnomalyModel.resolved == resolved)
            if severity:
                query = query.where(SDRAnomalyModel.severity == severity.upper())

            capped_limit = max(1, min(limit, 1000))
            result = await session.execute(query.limit(capped_limit))
            return list(result.scalars().all())

    async def close(self) -> None:
        """Close database engine."""
        await self.engine.dispose()
