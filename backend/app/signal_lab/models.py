"""
Pydantic data models for the Signal Lab module.
Defines types for QPSK and 8PSK simulation, constellation data,
and I/Q sample analysis.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ModulationType(str, Enum):
    QPSK = "qpsk"
    PSK8 = "8psk"


class SampleFormat(str, Enum):
    FLOAT32_LE = "float32_le"  # 32-bit IEEE float, little-endian interleaved I/Q
    INT16_LE = "int16_le"      # 16-bit signed integer, little-endian interleaved I/Q
    UINT8 = "uint8"            # 8-bit unsigned integer, RTL-SDR format (127.5 offset)


class ConstellationPoint(BaseModel):
    i: float = Field(description="In-phase component")
    q: float = Field(description="Quadrature component")
    symbol_index: Optional[int] = None
    bit_pattern: Optional[str] = None


class SignalSimulationRequest(BaseModel):
    modulation: ModulationType = ModulationType.QPSK
    snr_db: float = Field(default=15.0, ge=-5.0, le=40.0, description="Signal-to-Noise Ratio in dB (Es/N0)")
    phase_offset_deg: float = Field(default=0.0, ge=-180.0, le=180.0, description="Carrier phase offset in degrees")
    freq_offset_norm: float = Field(default=0.0, ge=-0.1, le=0.1, description="Carrier frequency offset normalized to symbol rate")
    symbol_count: int = Field(default=1000, ge=100, le=10000, description="Number of symbols to simulate")
    seed: Optional[int] = Field(default=42, description="Random seed for reproducible results")


SimulationRequest = SignalSimulationRequest


class SimulationResult(BaseModel):
    modulation: ModulationType
    snr_db: float
    symbol_count: int
    bit_count: int
    bit_errors: int
    symbol_errors: int
    ber: float
    ser: float
    theoretical_ber: float
    theoretical_ser: float
    evm_rms_percent: float
    phase_offset_deg: float
    freq_offset_norm: float
    ideal_constellation: List[ConstellationPoint]
    tx_symbols: List[ConstellationPoint]
    rx_symbols: List[ConstellationPoint]
    is_simulated: bool = True
    disclaimer: str = "Simulated mathematical model (AWGN + carrier impairments) — not a physical satellite hardware measurement."

    model_config = ConfigDict(arbitrary_types_allowed=True)


class IQAnalysisResult(BaseModel):
    filename: str
    total_samples: int
    sample_format: SampleFormat
    estimated_modulation: str
    modulation_confidence: float
    estimated_snr_db: float
    estimated_evm_percent: float
    estimated_freq_offset_norm: float
    estimated_phase_offset_deg: float
    constellation_samples: List[ConstellationPoint]
    uncertainty_note: str
    is_estimate: bool = True

    model_config = ConfigDict(arbitrary_types_allowed=True)
