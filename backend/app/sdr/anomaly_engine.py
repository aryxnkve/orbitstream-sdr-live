"""
Configurable signal anomaly detection, event deduplication, severity classification,
and recovery tracking for RTL-SDR measurements.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from .database import SDRDatabase
from .models import SDRAnomalyModel, SDRMeasurementModel, SDRMeasurementPayload

logger = logging.getLogger("orbitstream.sdr_anomaly")


class SDRAnomalyEngine:
    """
    Evaluates incoming measurements against diagnostic thresholds,
    deduplicates persistent conditions, and records recovery events.
    """

    def __init__(self, db: SDRDatabase) -> None:
        self.db = db

    async def evaluate(
        self,
        payload: SDRMeasurementPayload,
        previous_measurement: Optional[SDRMeasurementModel] = None,
    ) -> List[SDRAnomalyModel]:
        """
        Evaluate payload against anomaly rules.
        Returns a list of updated or created anomaly records.
        """
        active_anomalies: List[SDRAnomalyModel] = []
        now_ts = payload.timestamp
        device_id = payload.device_id

        # ── 1. Device / Hardware Validity Rule ─────────────────────────────
        rule_invalid = "SDR_RULE_INVALID_SAMPLES"
        if not payload.is_valid:
            sev = "CRITICAL" if payload.mode == "hardware" else "WARNING"
            anom = await self.db.upsert_anomaly(
                device_id=device_id,
                rule_id=rule_invalid,
                severity=sev,
                title="SDR Measurement Acquisition Failure",
                explanation=payload.validation_notes or "Hardware receiver returned invalid or empty samples.",
                metric_name="is_valid",
                threshold_value=1.0,
                observed_value=0.0,
                timestamp=now_ts,
            )
            active_anomalies.append(anom)
        else:
            # Recovery tracking
            resolved = await self.db.resolve_anomaly(
                device_id=device_id,
                rule_id=rule_invalid,
                resolved_at=now_ts,
                recovery_note="Hardware receiver re-established valid sample acquisition.",
            )
            if resolved:
                logger.info(f"[Recovery] {rule_invalid} resolved on device {device_id}.")

        # If measurement is invalid, skip physical RF metric checks
        if not payload.is_valid:
            return active_anomalies

        # ── 2. Signal Power Drop / Loss of Signal (LOS) ────────────────────
        rule_power = "SDR_RULE_SIGNAL_POWER_DROP"
        power = payload.relative_power_dbfs
        power_drop_triggered = False
        drop_magnitude = 0.0

        if previous_measurement and previous_measurement.is_valid:
            prev_power = previous_measurement.relative_power_dbfs
            drop_magnitude = prev_power - power
            if drop_magnitude >= 15.0:
                power_drop_triggered = True

        if power <= -55.0 or power_drop_triggered:
            sev = "CRITICAL" if (power <= -65.0 or drop_magnitude >= 25.0) else "WARNING"
            expl = (
                f"Sudden signal power drop of {drop_magnitude:.1f} dB detected."
                if power_drop_triggered
                else f"Severe signal attenuation: relative power at {power:.2f} dBFS (threshold: -55.0 dBFS)."
            )
            anom = await self.db.upsert_anomaly(
                device_id=device_id,
                rule_id=rule_power,
                severity=sev,
                title="Signal Power Drop / Severe Attenuation",
                explanation=expl,
                metric_name="relative_power_dbfs",
                threshold_value=-55.0,
                observed_value=power,
                timestamp=now_ts,
            )
            active_anomalies.append(anom)
        elif power >= -45.0:
            resolved = await self.db.resolve_anomaly(
                device_id=device_id,
                rule_id=rule_power,
                resolved_at=now_ts,
                recovery_note=f"Signal power restored to nominal level ({power:.2f} dBFS).",
            )
            if resolved:
                logger.info(f"[Recovery] {rule_power} resolved on device {device_id}.")

        # ── 3. Low SNR / Link Margin Degradation ───────────────────────────
        rule_snr = "SDR_RULE_LOW_SNR"
        snr = payload.snr_estimate_db

        if snr < 3.0:
            sev = "CRITICAL" if snr < 1.5 else "WARNING"
            anom = await self.db.upsert_anomaly(
                device_id=device_id,
                rule_id=rule_snr,
                severity=sev,
                title="Low In-Band Signal-to-Noise Ratio (SNR)",
                explanation=f"Estimated in-band SNR is {snr:.2f} dB, indicating severe noise degradation.",
                metric_name="snr_estimate_db",
                threshold_value=3.0,
                observed_value=snr,
                timestamp=now_ts,
            )
            active_anomalies.append(anom)
        elif snr >= 5.0:
            resolved = await self.db.resolve_anomaly(
                device_id=device_id,
                rule_id=rule_snr,
                resolved_at=now_ts,
                recovery_note=f"Signal-to-noise ratio restored to {snr:.2f} dB (healthy margin).",
            )
            if resolved:
                logger.info(f"[Recovery] {rule_snr} resolved on device {device_id}.")

        # ── 4. ADC Saturation / Frontend Clipping ──────────────────────────
        rule_sat = "SDR_RULE_ADC_SATURATION"
        clipping = payload.clipping_ratio

        if power > -1.0 or clipping > 0.05:
            anom = await self.db.upsert_anomaly(
                device_id=device_id,
                rule_id=rule_sat,
                severity="ERROR",
                title="ADC Frontend Saturation / Clipping",
                explanation=f"Receiver ADC is overloading (Power: {power:.2f} dBFS, Clipping: {clipping * 100:.1f}%). Reduce tuner gain.",
                metric_name="clipping_ratio",
                threshold_value=0.05,
                observed_value=clipping,
                timestamp=now_ts,
            )
            active_anomalies.append(anom)
        elif power <= -3.0 and clipping <= 0.01:
            resolved = await self.db.resolve_anomaly(
                device_id=device_id,
                rule_id=rule_sat,
                resolved_at=now_ts,
                recovery_note=f"ADC saturation cleared (Power: {power:.2f} dBFS, Clipping: {clipping * 100:.2f}%).",
            )
            if resolved:
                logger.info(f"[Recovery] {rule_sat} resolved on device {device_id}.")

        # ── 5. DC Offset / IQ Imbalance ────────────────────────────────────
        rule_dc = "SDR_RULE_DC_IMBALANCE"
        max_dc = max(abs(payload.dc_i), abs(payload.dc_q))

        if max_dc > 0.15:
            anom = await self.db.upsert_anomaly(
                device_id=device_id,
                rule_id=rule_dc,
                severity="WARNING",
                title="Significant DC Offset / LO Leakage",
                explanation=f"Excessive baseband DC offset detected (I: {payload.dc_i:.4f}, Q: {payload.dc_q:.4f}).",
                metric_name="dc_offset",
                threshold_value=0.15,
                observed_value=max_dc,
                timestamp=now_ts,
            )
            active_anomalies.append(anom)
        elif max_dc <= 0.08:
            resolved = await self.db.resolve_anomaly(
                device_id=device_id,
                rule_id=rule_dc,
                resolved_at=now_ts,
                recovery_note=f"Baseband DC offsets stabilized (max: {max_dc:.4f}).",
            )
            if resolved:
                logger.info(f"[Recovery] {rule_dc} resolved on device {device_id}.")

        return active_anomalies

