"""
Hardware abstraction layer for RTL-SDR and explicit Demo SDR.
Strictly separates physical hardware acquisition from demonstration mode.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger("orbitstream.sdr_device")


class SdrDeviceError(Exception):
    """Base exception for SDR device operations."""
    pass


class HardwareNotFoundError(SdrDeviceError):
    """Raised when the physical RTL-SDR USB dongle is not detected."""
    pass


class HardwareAccessError(SdrDeviceError):
    """Raised when the physical RTL-SDR is busy or lacks permissions."""
    pass


class BaseSdrDevice(ABC):
    """Abstract SDR device interface."""

    @abstractmethod
    def open(self) -> None:
        """Initialize and tune the hardware device."""
        pass

    @abstractmethod
    def read_samples(self, count: int) -> np.ndarray:
        """Read count complex I/Q samples from the device."""
        pass

    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """Return hardware metadata and identification."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Release the device resources cleanly."""
        pass

    @property
    @abstractmethod
    def is_synthetic(self) -> bool:
        """True if the device generates demonstration data; False for real hardware."""
        pass


class RtlSdrHardwareDevice(BaseSdrDevice):
    """
    Physical RTL-SDR USB hardware receiver.
    Requires pyrtlsdr and native librtlsdr / WinUSB driver.
    NEVER generates synthetic measurements.
    """

    def __init__(
        self,
        frequency_hz: int = 100_000_000,
        sample_rate_hz: int = 1_024_000,
        gain: Any = "auto",
        device_index: int = 0,
        device_id: str = "rtlsdr-win-01",
    ) -> None:
        self.frequency_hz = frequency_hz
        self.sample_rate_hz = sample_rate_hz
        self.gain = gain
        self.device_index = device_index
        self.device_id = device_id
        self._sdr = None
        self._serial = ""
        self._tuner_type = ""
        self._actual_gain_db = 0.0

    @property
    def is_synthetic(self) -> bool:
        return False

    def open(self) -> None:
        """Open and configure the physical RTL-SDR device."""
        try:
            from rtlsdr import RtlSdr
        except ImportError as exc:
            raise SdrDeviceError(
                "pyrtlsdr is not installed or librtlsdr.dll could not be loaded. "
                "Ensure pyrtlsdr and pyrtlsdrlib are installed."
            ) from exc

        try:
            self._sdr = RtlSdr(device_index=self.device_index)
            self._sdr.sample_rate = self.sample_rate_hz
            self._sdr.center_freq = self.frequency_hz
            self._sdr.gain = self.gain

            # Read actual configured gain
            try:
                self._actual_gain_db = float(self._sdr.gain)
            except Exception:
                self._actual_gain_db = 0.0

            # Gather device serial / addresses
            try:
                serials = self._sdr.get_device_serial_addresses()
                if serials and len(serials) > self.device_index:
                    self._serial = str(serials[self.device_index]).strip()
            except Exception:
                self._serial = "RTL2838U"

            # Tuner type if available
            try:
                self._tuner_type = getattr(self._sdr, "get_tuner_type", lambda: "RTL2832U")()
            except Exception:
                self._tuner_type = "RTL2832U"

            logger.info(
                f"[RTL-SDR Hardware] Opened device index {self.device_index} (Serial: {self._serial}, "
                f"Freq: {self.frequency_hz / 1e6:.3f} MHz, Rate: {self.sample_rate_hz / 1e6:.3f} MS/s, "
                f"Gain: {self.gain})"
            )

        except Exception as exc:
            err_str = str(exc)
            if "LIBUSB_ERROR_ACCESS" in err_str or "Access denied" in err_str:
                raise HardwareAccessError(
                    f"RTL-SDR access denied: Another program (such as SDR#) may be using the dongle, "
                    f"or WinUSB driver is missing. Close conflicting software and verify Zadig WinUSB driver."
                ) from exc
            elif "LIBUSB_ERROR_NOT_FOUND" in err_str or "LIBUSB_ERROR_NO_DEVICE" in err_str or "index" in err_str:
                raise HardwareNotFoundError(
                    f"No RTL-SDR hardware found at device index {self.device_index}. "
                    f"Ensure the USB dongle is connected to this computer."
                ) from exc
            else:
                raise SdrDeviceError(f"Failed to open RTL-SDR: {err_str}") from exc

    def read_samples(self, count: int) -> np.ndarray:
        """Read actual I/Q samples from the hardware receiver."""
        if self._sdr is None:
            raise SdrDeviceError("RTL-SDR device is not open. Call open() first.")

        try:
            raw = self._sdr.read_samples(count)
            samples = np.asarray(raw, dtype=np.complex64)
            if samples.size == 0:
                raise SdrDeviceError("Hardware returned 0 samples.")
            return samples
        except Exception as exc:
            raise SdrDeviceError(f"Failed to read samples from RTL-SDR hardware: {exc}") from exc

    def get_device_info(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": "RTL-SDR (Real Hardware)",
            "device_index": self.device_index,
            "serial": self._serial or "Unknown",
            "tuner_type": self._tuner_type or "RTL2832U",
            "actual_gain_db": self._actual_gain_db,
            "is_synthetic": False,
            "driver": "pyrtlsdr / librtlsdr",
        }

    def close(self) -> None:
        if self._sdr is not None:
            try:
                self._sdr.close()
                logger.info("[RTL-SDR Hardware] Device closed cleanly.")
            except Exception as exc:
                logger.warning(f"Error closing RTL-SDR: {exc}")
            finally:
                self._sdr = None


class DemoSdrDevice(BaseSdrDevice):
    """
    Demonstration / Mock SDR device for offline simulation or testing.
    Clearly marked as synthetic data.
    """

    def __init__(
        self,
        frequency_hz: int = 100_000_000,
        sample_rate_hz: int = 1_024_000,
        gain: Any = "auto",
        device_id: str = "demo-sdr-synthetic",
    ) -> None:
        self.frequency_hz = frequency_hz
        self.sample_rate_hz = sample_rate_hz
        self.gain = gain
        self.device_id = device_id
        self._is_open = False
        self._t = 0.0

    @property
    def is_synthetic(self) -> bool:
        return True

    def open(self) -> None:
        self._is_open = True
        logger.info(f"[Demo SDR] Opened synthetic demo receiver (Freq: {self.frequency_hz / 1e6:.3f} MHz)")

    def read_samples(self, count: int) -> np.ndarray:
        if not self._is_open:
            raise SdrDeviceError("Demo SDR is not open.")

        # Generate realistic satellite-like baseband test signal
        # Center carrier + weak sideband + AWGN
        t = np.linspace(self._t, self._t + (count / self.sample_rate_hz), count, endpoint=False)
        self._t += count / self.sample_rate_hz

        # Carrier at +50 kHz offset
        carrier_freq = 50_000.0
        carrier = 0.25 * np.exp(1j * (2.0 * np.pi * carrier_freq * t))

        # Secondary tone at -120 kHz
        tone = 0.08 * np.exp(1j * (2.0 * np.pi * -120_000.0 * t))

        # Noise floor (AWGN)
        noise_std = 0.03
        noise = (np.random.normal(0, noise_std, count) + 1j * np.random.normal(0, noise_std, count)).astype(np.complex64)

        samples = (carrier + tone + noise).astype(np.complex64)
        return samples

    def get_device_info(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": "Synthetic Demonstration SDR",
            "device_index": -1,
            "serial": "DEMO-SYNTHETIC-NO-HARDWARE",
            "tuner_type": "Software Emulator",
            "actual_gain_db": 29.7,
            "is_synthetic": True,
            "driver": "Synthetic NumPy Signal Generator",
        }

    def close(self) -> None:
        self._is_open = False
        logger.info("[Demo SDR] Closed.")


def create_sdr_device(
    frequency_hz: int = 100_000_000,
    sample_rate_hz: int = 1_024_000,
    gain: Any = "auto",
    device_index: int = 0,
    device_id: str = "rtlsdr-win-01",
    mode: str = "hardware",
) -> BaseSdrDevice:
    """
    Factory function returning either a physical RtlSdrHardwareDevice or a DemoSdrDevice.
    Hardware mode strictly enforces physical dongle usage.
    """
    if mode.lower() == "demo":
        return DemoSdrDevice(
            frequency_hz=frequency_hz,
            sample_rate_hz=sample_rate_hz,
            gain=gain,
            device_id=f"{device_id}-demo",
        )
    return RtlSdrHardwareDevice(
        frequency_hz=frequency_hz,
        sample_rate_hz=sample_rate_hz,
        gain=gain,
        device_index=device_index,
        device_id=device_id,
    )

