"""
Configuration manager for the RTL-SDR collector.
Supports loading from environment variables, .env files, or JSON config files.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

# Attempt to load dotenv if available
try:
    from dotenv import load_dotenv
    # Look for .env in current working directory and collector directory
    load_dotenv(Path(__file__).parent / ".env")
    load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass


@dataclass
class CollectorConfig:
    """RTL-SDR Collector configuration parameters."""

    backend_url: str = "https://orbitstream-hl80.onrender.com"
    api_key: str = "orbitstream-collector-key-2026"
    frequency_hz: int = 100_000_000  # 100 MHz default
    sample_rate_hz: int = 1_024_000   # 1.024 MS/s
    gain: Union[str, float] = "auto"  # 'auto' or numeric dB (e.g. 29.7)
    interval_seconds: float = 10.0   # Default 10 seconds
    sample_count: int = 262_144       # 2^18 complex samples
    device_index: int = 0
    device_id: str = "rtlsdr-win-01"
    mode: str = "hardware"           # 'hardware' or 'demo'
    spectrum_bins: int = 64          # FFT bins to send in summary payload
    timeout_seconds: float = 10.0     # HTTP request timeout

    @classmethod
    def from_env(cls, config_path: str | None = None) -> CollectorConfig:
        """Create configuration from file and environment variables."""
        cfg = cls()

        # If a JSON config file exists, load it first
        json_file = config_path or os.environ.get("SDR_CONFIG_FILE")
        if json_file and os.path.exists(json_file):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data: dict[str, Any] = json.load(f)
                    for key, val in data.items():
                        if hasattr(cfg, key):
                            setattr(cfg, key, val)
            except Exception as exc:
                print(f"[Warning] Failed to read config file {json_file}: {exc}")

        # Override with environment variables
        backend = os.environ.get("ORBITSTREAM_BACKEND_URL") or os.environ.get("BACKEND_URL")
        if backend:
            backend_clean = backend.rstrip("/")
            if backend_clean.endswith("/api/sdr/ingest"):
                backend_clean = backend_clean[:-len("/api/sdr/ingest")].rstrip("/")
            cfg.backend_url = backend_clean

        api_key = os.environ.get("ORBITSTREAM_COLLECTOR_API_KEY") or os.environ.get("ORBITSTREAM_API_KEY") or os.environ.get("SDR_API_KEY")
        if api_key:
            cfg.api_key = api_key

        freq = os.environ.get("SDR_FREQUENCY_HZ") or os.environ.get("SDR_CENTER_FREQ_HZ")
        if freq:
            try:
                cfg.frequency_hz = int(float(freq))
            except ValueError:
                pass

        rate = os.environ.get("SDR_SAMPLE_RATE_HZ")
        if rate:
            try:
                cfg.sample_rate_hz = int(float(rate))
            except ValueError:
                pass

        gain_val = os.environ.get("SDR_GAIN")
        if gain_val:
            if gain_val.strip().lower() == "auto":
                cfg.gain = "auto"
            else:
                try:
                    cfg.gain = float(gain_val)
                except ValueError:
                    cfg.gain = "auto"

        interval = os.environ.get("SDR_INTERVAL_SECONDS") or os.environ.get("SDR_INTERVAL")
        if interval:
            try:
                cfg.interval_seconds = max(1.0, float(interval))
            except ValueError:
                pass

        samples = os.environ.get("SDR_SAMPLE_COUNT")
        if samples:
            try:
                cfg.sample_count = max(1024, int(samples))
            except ValueError:
                pass

        dev_idx = os.environ.get("SDR_DEVICE_INDEX")
        if dev_idx:
            try:
                cfg.device_index = int(dev_idx)
            except ValueError:
                pass

        dev_id = os.environ.get("SDR_DEVICE_ID")
        if dev_id:
            cfg.device_id = dev_id.strip()

        mode = os.environ.get("SDR_MODE")
        if mode:
            cfg.mode = mode.strip().lower()

        bins = os.environ.get("SDR_SPECTRUM_BINS")
        if bins:
            try:
                cfg.spectrum_bins = max(16, min(512, int(bins)))
            except ValueError:
                pass

        return cfg

