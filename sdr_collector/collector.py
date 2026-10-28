"""
Main RTL-SDR Collector Service for ORBITSTREAM.
Gathers I/Q physical layer measurements from the connected SDR device every 10 seconds
and transmits authenticated telemetry to the deployed ORBITSTREAM backend.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import requests

from .config import CollectorConfig
from .device import BaseSdrDevice, SdrDeviceError, create_sdr_device
from .metrics import calculate_metrics

# Configure logging with secret masking
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orbitstream.collector")


def mask_secret(secret: str) -> str:
    """Mask secret token for safe logging."""
    if not secret:
        return "<none>"
    if len(secret) <= 6:
        return "***"
    return secret[:3] + "..." + secret[-3:]


class SDRCollector:
    """Orchestrates periodic sample acquisition, metric computation, and HTTP transmission."""

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self.device: Optional[BaseSdrDevice] = None
        self._is_running = False
        self._session = requests.Session()

    def initialize_device(self) -> bool:
        """Attempt to open and tune the configured SDR device."""
        logger.info(
            f"Initializing SDR device (Mode: {self.config.mode.upper()}, Freq: {self.config.frequency_hz / 1e6:.3f} MHz, "
            f"Rate: {self.config.sample_rate_hz / 1e6:.3f} MS/s, Gain: {self.config.gain})..."
        )

        try:
            self.device = create_sdr_device(
                frequency_hz=self.config.frequency_hz,
                sample_rate_hz=self.config.sample_rate_hz,
                gain=self.config.gain,
                device_index=self.config.device_index,
                device_id=self.config.device_id,
                mode=self.config.mode,
            )
            self.device.open()
            info = self.device.get_device_info()
            logger.info(f"SDR device successfully opened: {info.get('device_type')} (Serial: {info.get('serial')})")
            return True
        except Exception as exc:
            logger.error(f"Could not open SDR device in {self.config.mode} mode: {exc}")
            self.device = None
            return False

    def collect_single_measurement(self) -> Dict[str, Any]:
        """
        Acquire samples, compute metrics, and structure the telemetry payload.
        In hardware mode, if device is not opened, marks measurement as invalid with error notes.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        base_payload = {
            "timestamp": now_utc,
            "device_id": self.config.device_id,
            "mode": self.config.mode,
            "center_frequency_hz": self.config.frequency_hz,
            "sample_rate_hz": self.config.sample_rate_hz,
            "gain": str(self.config.gain),
        }

        # If hardware device is missing or uninitialized, attempt re-opening
        if self.device is None:
            reopened = self.initialize_device()
            if not reopened:
                # Device could not be opened
                return {
                    **base_payload,
                    "is_valid": False,
                    "validation_notes": "SDR hardware device is not connected or accessible.",
                    "sample_count": 0,
                    "relative_power_dbfs": -120.0,
                    "peak_power_dbfs": -120.0,
                    "papr_db": 0.0,
                    "snr_estimate_db": 0.0,
                    "noise_floor_dbfs": -120.0,
                    "dc_i": 0.0,
                    "dc_q": 0.0,
                    "clipping_ratio": 0.0,
                    "spectrum_bins": [round(-100.0, 2)] * self.config.spectrum_bins,
                    "device_info": {
                        "device_id": self.config.device_id,
                        "device_type": "Disconnected / Unavailable",
                        "is_synthetic": (self.config.mode == "demo"),
                    },
                }

        # Device is available: acquire actual samples
        try:
            samples = self.device.read_samples(self.config.sample_count)
            metrics = calculate_metrics(
                samples=samples,
                sample_rate_hz=self.config.sample_rate_hz,
                center_frequency_hz=self.config.frequency_hz,
                num_spectrum_bins=self.config.spectrum_bins,
            )
            device_info = self.device.get_device_info()

            payload = {
                **base_payload,
                **metrics,
                "device_info": device_info,
            }
            logger.info(
                f"[RF Reading] Power: {payload.get('relative_power_dbfs'):.1f} dBFS | "
                f"Peak: {payload.get('peak_power_dbfs'):.1f} dBFS | "
                f"SNR: {payload.get('snr_estimate_db'):.1f} dB | "
                f"Noise: {payload.get('noise_floor_dbfs'):.1f} dBFS | "
                f"PAPR: {payload.get('papr_db'):.1f} dB"
            )
            return payload

        except Exception as exc:
            logger.warning(f"Error during sample acquisition: {exc}")
            # Hardware error during read: close so we can retry cleanly next time
            if self.device:
                try:
                    self.device.close()
                except Exception:
                    pass
                self.device = None

            return {
                **base_payload,
                "is_valid": False,
                "validation_notes": f"Hardware read error: {exc}",
                "sample_count": 0,
                "relative_power_dbfs": -120.0,
                "peak_power_dbfs": -120.0,
                "papr_db": 0.0,
                "snr_estimate_db": 0.0,
                "noise_floor_dbfs": -120.0,
                "dc_i": 0.0,
                "dc_q": 0.0,
                "clipping_ratio": 0.0,
                "spectrum_bins": [round(-100.0, 2)] * self.config.spectrum_bins,
                "device_info": {
                    "device_id": self.config.device_id,
                    "device_type": "Hardware Read Failure",
                    "is_synthetic": (self.config.mode == "demo"),
                },
            }

    def transmit_measurement(self, payload: Dict[str, Any]) -> bool:
        """Send payload to the backend ingestion endpoint over HTTPS."""
        ingest_url = f"{self.config.backend_url}/api/sdr/ingest"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.config.api_key,
        }

        try:
            response = self._session.post(
                ingest_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            if response.status_code in (200, 201):
                logger.info(
                    f"[Telemetry Sent] Power: {payload.get('relative_power_dbfs')} dBFS | "
                    f"SNR: {payload.get('snr_estimate_db')} dB | Valid: {payload.get('is_valid')} | "
                    f"Mode: {payload.get('mode')} -> {ingest_url}"
                )
                return True
            elif response.status_code == 401:
                logger.error(f"[Auth Error] Backend rejected API key (HTTP 401 Unauthorized). Verify ORBITSTREAM_COLLECTOR_API_KEY.")
                return False
            else:
                logger.warning(f"[Telemetry Warning] Backend returned HTTP {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as exc:
            logger.warning(f"[Network] Failed to reach backend at {ingest_url}: {exc}")
            return False

    def run_loop(self) -> None:
        """Run continuous collection loop every interval_seconds."""
        logger.info("=============================================================")
        logger.info("       ORBITSTREAM RTL-SDR Collector Service Starting        ")
        logger.info("=============================================================")
        logger.info(f" Backend Endpoint : {self.config.backend_url}/api/sdr/ingest")
        logger.info(f" Collector API Key: {mask_secret(self.config.api_key)}")
        logger.info(f" Target Interval  : {self.config.interval_seconds:.1f} seconds")
        logger.info(f" Operating Mode   : {self.config.mode.upper()}")
        logger.info(f" Center Frequency : {self.config.frequency_hz / 1e6:.3f} MHz")
        logger.info(f" Sample Rate      : {self.config.sample_rate_hz / 1e6:.3f} MS/s")
        logger.info("=============================================================")

        self.initialize_device()
        self._is_running = True

        try:
            while self._is_running:
                start_time = time.time()

                payload = self.collect_single_measurement()
                self.transmit_measurement(payload)

                elapsed = time.time() - start_time
                sleep_duration = max(0.5, self.config.interval_seconds - elapsed)
                time.sleep(sleep_duration)

        except KeyboardInterrupt:
            logger.info("Collector stopped by user (Ctrl+C).")
        finally:
            self.stop()

    def stop(self) -> None:
        """Clean shutdown of device and resources."""
        self._is_running = False
        if self.device:
            self.device.close()
            self.device = None
        logger.info("RTL-SDR Collector stopped cleanly.")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="ORBITSTREAM RTL-SDR Physical Layer Collector")
    parser.add_argument("--backend-url", type=str, help="Backend URL (e.g. https://orbitstream.onrender.com)")
    parser.add_argument("--api-key", type=str, help="Collector API key secret")
    parser.add_argument("--frequency", type=int, help="Center frequency in Hz (e.g. 100000000)")
    parser.add_argument("--sample-rate", type=int, help="Sampling rate in Hz (e.g. 1024000)")
    parser.add_argument("--gain", type=str, help="Tuner gain in dB or 'auto'")
    parser.add_argument("--interval", type=float, help="Collection interval in seconds (default 10.0)")
    parser.add_argument("--mode", choices=["hardware", "demo"], help="Collector mode: 'hardware' or 'demo'")
    parser.add_argument("--device-id", type=str, help="Device identifier label")
    parser.add_argument("--once", action="store_true", help="Acquire a single measurement and exit")
    parser.add_argument("--config", type=str, help="Path to JSON configuration file")

    args = parser.parse_args()

    cfg = CollectorConfig.from_env(args.config)
    if args.backend_url:
        cfg.backend_url = args.backend_url.rstrip("/")
    if args.api_key:
        cfg.api_key = args.api_key
    if args.frequency:
        cfg.frequency_hz = args.frequency
    if args.sample_rate:
        cfg.sample_rate_hz = args.sample_rate
    if args.gain:
        cfg.gain = "auto" if args.gain.lower() == "auto" else float(args.gain)
    if args.interval:
        cfg.interval_seconds = args.interval
    if args.mode:
        cfg.mode = args.mode
    if args.device_id:
        cfg.device_id = args.device_id

    collector = SDRCollector(cfg)

    if args.once:
        collector.initialize_device()
        measurement = collector.collect_single_measurement()
        print(json.dumps(measurement, indent=2))
        collector.transmit_measurement(measurement)
        collector.stop()
    else:
        collector.run_loop()


if __name__ == "__main__":
    main()

