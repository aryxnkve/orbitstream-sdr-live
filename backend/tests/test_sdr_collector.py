"""
Automated test suite for RTL-SDR collector integration, metric calculations,
authentication, invalid payload validation, persistence, time-range filtering,
anomaly deduplication, recovery tracking, and reporting consistency.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_config
from sdr_collector.metrics import calculate_metrics

client = TestClient(app)
config = get_config()
VALID_API_KEY = config.collector_api_key


# ── 1. Metric Calculations Tests ──────────────────────────────────────

def test_metrics_calculation_clean_carrier():
    """Verify relative power, PAPR, SNR, and FFT bins for a pure complex carrier."""
    fs = 1_024_000
    fc = 100_000_000
    n = 16384
    t = np.arange(n) / fs

    # Complex tone with amplitude 0.5 (-6 dBFS peak, -6 dBFS mean power)
    tone = 0.5 * np.exp(1j * 2 * np.pi * 50_000 * t)
    # Add low AWGN noise
    noise = (np.random.normal(0, 0.01, n) + 1j * np.random.normal(0, 0.01, n))
    samples = (tone + noise).astype(np.complex64)

    metrics = calculate_metrics(samples, sample_rate_hz=fs, center_frequency_hz=fc, num_spectrum_bins=64)

    assert metrics["is_valid"] is True
    # Expected relative power ~ 10*log10(0.5^2) = -6 dBFS
    assert -9.0 <= metrics["relative_power_dbfs"] <= -4.0
    assert len(metrics["spectrum_bins"]) == 64
    assert metrics["snr_estimate_db"] > 10.0
    assert abs(metrics["dc_i"]) < 0.05
    assert abs(metrics["dc_q"]) < 0.05
    assert metrics["sample_count"] == n


def test_metrics_calculation_invalid_and_empty():
    """Verify robust rejection of non-finite or empty samples."""
    # Empty
    res_empty = calculate_metrics(np.array([], dtype=np.complex64), 1024000, 100000000)
    assert res_empty["is_valid"] is False
    assert res_empty["sample_count"] == 0

    # Non-finite (NaN / Inf)
    bad_samples = np.array([1.0 + 0j, np.nan + 1j, np.inf + 0j], dtype=np.complex64)
    res_nan = calculate_metrics(bad_samples, 1024000, 100000000)
    assert res_nan["is_valid"] is False
    assert "Non-finite" in res_nan["validation_notes"]


def test_metrics_clipping_detection():
    """Verify ADC clipping ratio calculation on saturated samples."""
    fs = 1_024_000
    fc = 100_000_000
    n = 1000
    # Create saturated samples (+/- 1.0)
    saturated = (1.0 + 1.0j) * np.ones(n, dtype=np.complex64)
    res = calculate_metrics(saturated, fs, fc)
    assert res["is_valid"] is True
    assert res["clipping_ratio"] >= 0.90


# ── 2. Ingestion & Authentication Tests ───────────────────────────────

def test_ingest_authentication():
    """Verify authentication enforcement: 401 on missing or invalid key; 201 on valid key."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_id": "test-device-auth",
        "mode": "hardware",
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "gain": "auto",
        "relative_power_dbfs": -25.5,
        "peak_power_dbfs": -18.2,
        "papr_db": 7.3,
        "snr_estimate_db": 18.0,
        "noise_floor_dbfs": -43.5,
        "dc_i": 0.001,
        "dc_q": 0.002,
        "clipping_ratio": 0.0,
        "spectrum_bins": [-40.0] * 64,
        "sample_count": 262144,
        "is_valid": True,
        "validation_notes": "Valid test samples",
    }

    # Missing API key -> 401
    resp_no_auth = client.post("/api/sdr/ingest", json=payload)
    assert resp_no_auth.status_code == 401

    # Invalid API key -> 401
    resp_bad_auth = client.post(
        "/api/sdr/ingest",
        json=payload,
        headers={"X-API-Key": "completely-invalid-key-xyz"},
    )
    assert resp_bad_auth.status_code == 401

    # Valid X-API-Key header -> 201
    resp_valid = client.post(
        "/api/sdr/ingest",
        json=payload,
        headers={"X-API-Key": VALID_API_KEY},
    )
    assert resp_valid.status_code == 201
    data = resp_valid.json()
    assert data["status"] == "accepted"
    assert data["device_id"] == "test-device-auth"

    # Valid Bearer token Authorization header -> 201
    resp_bearer = client.post(
        "/api/sdr/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {VALID_API_KEY}"},
    )
    assert resp_bearer.status_code == 201


def test_ingest_invalid_payload_validation():
    """Verify strict Pydantic validation rejects out-of-bounds or malformed requests."""
    headers = {"X-API-Key": VALID_API_KEY}

    # Negative center frequency
    bad_freq = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_id": "test-dev",
        "center_frequency_hz": -100,  # Invalid
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -20.0,
    }
    resp = client.post("/api/sdr/ingest", json=bad_freq, headers=headers)
    assert resp.status_code == 422

    # Negative sample rate
    bad_rate = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_id": "test-dev",
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": -500,  # Invalid
        "relative_power_dbfs": -20.0,
    }
    resp = client.post("/api/sdr/ingest", json=bad_rate, headers=headers)
    assert resp.status_code == 422

    # Invalid timestamp format
    bad_ts = {
        "timestamp": "not-a-valid-iso-date",
        "device_id": "test-dev",
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -20.0,
    }
    resp = client.post("/api/sdr/ingest", json=bad_ts, headers=headers)
    assert resp.status_code == 422


# ── 3. Persistence & Querying Tests ───────────────────────────────────

def test_persistence_and_latest_status():
    """Verify ingested measurement is saved in persistent storage and queried via /latest."""
    import uuid
    headers = {"X-API-Key": VALID_API_KEY}
    now_ts = datetime.now(timezone.utc).isoformat()
    dev_id = f"test-persist-{uuid.uuid4().hex[:6]}"

    payload = {
        "timestamp": now_ts,
        "device_id": dev_id,
        "mode": "hardware",
        "center_frequency_hz": 137_500_000,
        "sample_rate_hz": 2_048_000,
        "gain": "38.6",
        "relative_power_dbfs": -18.4,
        "peak_power_dbfs": -10.1,
        "papr_db": 8.3,
        "snr_estimate_db": 22.5,
        "noise_floor_dbfs": -40.9,
        "dc_i": 0.005,
        "dc_q": -0.003,
        "clipping_ratio": 0.0001,
        "spectrum_bins": [-35.0] * 64,
        "sample_count": 262144,
        "is_valid": True,
        "validation_notes": "Clean NOAA signal",
        "device_info": {
            "device_id": dev_id,
            "device_type": "RTL-SDR Blog V4",
            "serial": "00000001",
            "is_synthetic": False,
        },
    }

    # Ingest
    res_ingest = client.post("/api/sdr/ingest", json=payload, headers=headers)
    assert res_ingest.status_code == 201

    # Query latest status
    res_latest = client.get(f"/api/sdr/latest?device_id={dev_id}")
    assert res_latest.status_code == 200
    status_data = res_latest.json()

    assert status_data["device_id"] == dev_id
    assert status_data["device_type"] == "RTL-SDR Blog V4"
    assert status_data["frequency_mhz"] == 137.5
    assert status_data["sample_rate_msps"] == 2.048
    assert status_data["relative_power_dbfs"] == -18.4
    assert status_data["snr_estimate_db"] == 22.5
    assert status_data["is_synthetic"] is False
    assert status_data["latest_measurement"]["serial"] == "00000001"


def test_time_range_filtering():
    """Verify start_time and end_time filtering in historical queries."""
    import uuid
    headers = {"X-API-Key": VALID_API_KEY}
    base_time = datetime(2026, 10, 28, 10, 0, 0, tzinfo=timezone.utc)
    dev_id = f"test-time-range-{uuid.uuid4().hex[:6]}"

    # Insert 3 records spaced by 10 minutes: 10:00, 10:10, 10:20
    for i in range(3):
        ts = (base_time + timedelta(minutes=10 * i)).isoformat()
        payload = {
            "timestamp": ts,
            "device_id": dev_id,
            "center_frequency_hz": 100_000_000,
            "sample_rate_hz": 1_024_000,
            "relative_power_dbfs": -20.0 + i,
            "is_valid": True,
        }
        res = client.post("/api/sdr/ingest", json=payload, headers=headers)
        assert res.status_code == 201

    # Query range covering only the second record (10:05 to 10:15)
    t_start = (base_time + timedelta(minutes=5)).isoformat()
    t_end = (base_time + timedelta(minutes=15)).isoformat()

    history_resp = client.get(
        f"/api/sdr/history?device_id={dev_id}&start_time={t_start}&end_time={t_end}"
    )
    assert history_resp.status_code == 200
    items = history_resp.json()["measurements"]
    assert len(items) == 1
    assert items[0]["timestamp"] == (base_time + timedelta(minutes=10)).isoformat()


# ── 4. Anomaly Detection, Deduplication & Recovery Tests ─────────────

def test_anomaly_detection_power_drop_and_recovery():
    """
    Test scenario:
    1. Normal signal (-15 dBFS)
    2. Sudden drop to -60 dBFS -> Anomaly triggered (CRITICAL/WARNING)
    3. Continued low signal -> Deduplication (count increases, no second event)
    4. Recovery to -15 dBFS -> Recovery tracking (resolved=True, recovery_note set)
    """
    import uuid
    headers = {"X-API-Key": VALID_API_KEY}
    dev_id = f"test-anomaly-{uuid.uuid4().hex[:6]}"
    t0 = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Normal measurement
    p1 = {
        "timestamp": t0.isoformat(),
        "device_id": dev_id,
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -15.0,
        "snr_estimate_db": 25.0,
        "is_valid": True,
    }
    client.post("/api/sdr/ingest", json=p1, headers=headers)

    # 2. Sudden power drop to -60.0 dBFS (drop of 45 dB)
    p2 = {
        "timestamp": (t0 + timedelta(seconds=10)).isoformat(),
        "device_id": dev_id,
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -60.0,
        "snr_estimate_db": 2.0,
        "is_valid": True,
    }
    res2 = client.post("/api/sdr/ingest", json=p2, headers=headers)
    assert res2.status_code == 201

    # Check that anomaly is present
    anom_resp = client.get(f"/api/sdr/anomalies?device_id={dev_id}&resolved=false")
    active = anom_resp.json()["anomalies"]
    power_drop_anoms = [a for a in active if a["rule_id"] == "SDR_RULE_SIGNAL_POWER_DROP"]
    assert len(power_drop_anoms) == 1
    assert power_drop_anoms[0]["occurrence_count"] == 1
    assert power_drop_anoms[0]["severity"] in ("CRITICAL", "WARNING")

    # 3. Continued low signal at t + 20s (Deduplication check)
    p3 = {
        "timestamp": (t0 + timedelta(seconds=20)).isoformat(),
        "device_id": dev_id,
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -62.0,
        "snr_estimate_db": 1.5,
        "is_valid": True,
    }
    client.post("/api/sdr/ingest", json=p3, headers=headers)

    anom_resp2 = client.get(f"/api/sdr/anomalies?device_id={dev_id}&resolved=false")
    active2 = anom_resp2.json()["anomalies"]
    power_drop_anoms2 = [a for a in active2 if a["rule_id"] == "SDR_RULE_SIGNAL_POWER_DROP"]
    # Still only 1 active record, but occurrence_count incremented to 2!
    assert len(power_drop_anoms2) == 1
    assert power_drop_anoms2[0]["occurrence_count"] == 2

    # 4. Signal recovers to -14.0 dBFS at t + 30s
    p4 = {
        "timestamp": (t0 + timedelta(seconds=30)).isoformat(),
        "device_id": dev_id,
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -14.0,
        "snr_estimate_db": 22.0,
        "is_valid": True,
    }
    client.post("/api/sdr/ingest", json=p4, headers=headers)

    # Anomaly should now be marked resolved
    anom_resolved = client.get(f"/api/sdr/anomalies?device_id={dev_id}&resolved=true")
    resolved_list = anom_resolved.json()["anomalies"]
    resolved_power = [a for a in resolved_list if a["rule_id"] == "SDR_RULE_SIGNAL_POWER_DROP"]
    assert len(resolved_power) >= 1
    assert resolved_power[0]["resolved"] is True
    assert "restored" in resolved_power[0]["recovery_note"].lower()


# ── 5. Reports & Exports Consistency Tests ────────────────────────────

def test_reports_export_consistency():
    """Verify JSON, CSV, and printable HTML report consistency."""
    import uuid
    headers = {"X-API-Key": VALID_API_KEY}
    dev_id = f"test-reports-{uuid.uuid4().hex[:6]}"

    # Ingest a measurement to guarantee content
    client.post(
        "/api/sdr/ingest",
        json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": dev_id,
            "center_frequency_hz": 100_000_000,
            "sample_rate_hz": 1_024_000,
            "relative_power_dbfs": -21.0,
            "snr_estimate_db": 15.0,
            "is_valid": True,
        },
        headers=headers,
    )

    # 1. JSON measurements export
    res_json = client.get(f"/api/sdr/reports/export?format=json&device_id={dev_id}")
    assert res_json.status_code == 200
    assert res_json.headers["content-type"] == "application/json"
    data = res_json.json()
    assert data["report_type"] == "sdr_measurements_export"
    assert len(data["measurements"]) >= 1

    # 2. CSV measurements export
    res_csv = client.get(f"/api/sdr/reports/export?format=csv&device_id={dev_id}")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    csv_text = res_csv.text
    assert "Center Frequency (Hz)" in csv_text
    assert dev_id in csv_text

    # 3. Anomalies CSV & JSON
    res_anom_json = client.get("/api/sdr/reports/anomalies?format=json")
    assert res_anom_json.status_code == 200

    res_anom_csv = client.get("/api/sdr/reports/anomalies?format=csv")
    assert res_anom_csv.status_code == 200

    # 4. Printable HTML / PDF Diagnostic report
    res_pdf = client.get(f"/api/sdr/reports/pdf?device_id={dev_id}")
    assert res_pdf.status_code == 200
    assert "text/html" in res_pdf.headers["content-type"]
    assert "ORBITSTREAM RTL-SDR Physical Layer Diagnostic Report" in res_pdf.text


# ── 6. Credential Revocation Test ─────────────────────────────────────

def test_credential_revocation():
    """Verify that a revoked collector credential immediately returns 401."""
    import uuid
    revoking_key = f"temp-revoked-{uuid.uuid4().hex}"

    # Step 1: Revoke the key
    res_revoke = client.post(
        f"/api/sdr/keys/revoke?key_string={revoking_key}",
        headers={"X-API-Key": VALID_API_KEY},
    )
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "revoked"

    # Step 2: Attempt to ingest with the revoked key
    res_ingest = client.post(
        "/api/sdr/ingest",
        json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": "revoked-test-dev",
            "center_frequency_hz": 100_000_000,
            "sample_rate_hz": 1_024_000,
            "relative_power_dbfs": -20.0,
            "is_valid": True,
        },
        headers={"X-API-Key": revoking_key},
    )
    assert res_ingest.status_code == 401
    assert "revoked" in res_ingest.json()["detail"].lower()


# ── 7. Hardware Mode vs Demo Mode Integrity Test ──────────────────────

def test_demo_mode_separation_and_hardware_integrity():
    """
    Verify that:
    1. Hardware mode strictly flags is_synthetic=False.
    2. Demo mode strictly flags is_synthetic=True and mode='demo'.
    3. Status endpoint accurately reports both distinct modes.
    """
    import uuid
    headers = {"X-API-Key": VALID_API_KEY}
    now_ts = datetime.now(timezone.utc).isoformat()

    # Hardware device payload
    hw_id = f"rtlsdr-hw-{uuid.uuid4().hex[:6]}"
    hw_payload = {
        "timestamp": now_ts,
        "device_id": hw_id,
        "mode": "hardware",
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -18.0,
        "is_valid": True,
        "device_info": {
            "device_id": hw_id,
            "device_type": "RTL-SDR (Real Hardware)",
            "serial": "REAL-HW-001",
            "is_synthetic": False,
        },
    }
    res_hw = client.post("/api/sdr/ingest", json=hw_payload, headers=headers)
    assert res_hw.status_code == 201

    status_hw = client.get(f"/api/sdr/latest?device_id={hw_id}").json()
    assert status_hw["mode"] == "hardware"
    assert status_hw["is_synthetic"] is False

    # Demo device payload
    demo_id = f"rtlsdr-demo-{uuid.uuid4().hex[:6]}"
    demo_payload = {
        "timestamp": now_ts,
        "device_id": demo_id,
        "mode": "demo",
        "center_frequency_hz": 100_000_000,
        "sample_rate_hz": 1_024_000,
        "relative_power_dbfs": -12.5,
        "is_valid": True,
        "device_info": {
            "device_id": demo_id,
            "device_type": "Synthetic Demonstration SDR",
            "serial": "DEMO-SYNTHETIC-NO-HARDWARE",
            "is_synthetic": True,
        },
    }
    res_demo = client.post("/api/sdr/ingest", json=demo_payload, headers=headers)
    assert res_demo.status_code == 201

    status_demo = client.get(f"/api/sdr/latest?device_id={demo_id}").json()
    assert status_demo["mode"] == "demo"
    assert status_demo["is_synthetic"] is True
    assert status_demo["status"] == "demo"

