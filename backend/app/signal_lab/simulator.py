"""
Modulation Simulator for QPSK and 8PSK.
Implements symbol generation, Gray mapping, AWGN channel simulation,
carrier phase and frequency offsets, hard-decision demodulation,
EVM calculation, and theoretical vs measured BER/SER.
"""
from __future__ import annotations
import math
import random
from typing import List, Tuple
from .models import (
    ModulationType,
    SimulationRequest,
    SimulationResult,
    ConstellationPoint,
)


def _q_func(x: float) -> float:
    """Gaussian Q-function Q(x) = 0.5 * erfc(x / sqrt(2))."""
    if x < 0:
        return 1.0 - _q_func(-x)
    return 0.5 * math.erfc(x / math.sqrt(2.0))


class ModulationSimulator:
    """
    Simulates digital modulation schemes over an AWGN impaired channel.
    Fully deterministic and reproducible when a seed is provided.
    """

    # QPSK Gray constellation (2 bits/symbol)
    # 00: 45°, 01: 135°, 11: 225°, 10: 315°
    QPSK_MAP = {
        (0, 0): (math.cos(math.pi / 4), math.sin(math.pi / 4)),
        (0, 1): (math.cos(3 * math.pi / 4), math.sin(3 * math.pi / 4)),
        (1, 1): (math.cos(5 * math.pi / 4), math.sin(5 * math.pi / 4)),
        (1, 0): (math.cos(7 * math.pi / 4), math.sin(7 * math.pi / 4)),
    }

    # 8PSK Gray constellation (3 bits/symbol) per DVB-S2 standard
    PSK8_MAP = {
        (0, 0, 0): (math.cos(0.0), math.sin(0.0)),
        (0, 0, 1): (math.cos(math.pi / 4), math.sin(math.pi / 4)),
        (0, 1, 1): (math.cos(math.pi / 2), math.sin(math.pi / 2)),
        (0, 1, 0): (math.cos(3 * math.pi / 4), math.sin(3 * math.pi / 4)),
        (1, 1, 0): (math.cos(math.pi), math.sin(math.pi)),
        (1, 1, 1): (math.cos(5 * math.pi / 4), math.sin(5 * math.pi / 4)),
        (1, 0, 1): (math.cos(3 * math.pi / 2), math.sin(3 * math.pi / 2)),
        (1, 0, 0): (math.cos(7 * math.pi / 4), math.sin(7 * math.pi / 4)),
    }

    def simulate(self, req: SimulationRequest) -> SimulationResult:
        """Run modulation and channel impairment simulation."""
        rng = random.Random(req.seed if req.seed is not None else 42)

        bits_per_symbol = 2 if req.modulation == ModulationType.QPSK else 3
        constellation_map = self.QPSK_MAP if req.modulation == ModulationType.QPSK else self.PSK8_MAP

        # Ideal constellation points for reference
        ideal_points = []
        for bit_tuple, (i_val, q_val) in constellation_map.items():
            pattern = "".join(str(b) for b in bit_tuple)
            ideal_points.append(ConstellationPoint(i=i_val, q=q_val, bit_pattern=pattern))

        # Generate random bits
        total_bits = req.symbol_count * bits_per_symbol
        tx_bits = [rng.randint(0, 1) for _ in range(total_bits)]

        # Map to transmitted symbols
        tx_symbols: List[Tuple[float, float]] = []
        tx_patterns: List[str] = []
        for i in range(0, total_bits, bits_per_symbol):
            chunk = tuple(tx_bits[i : i + bits_per_symbol])
            coord = constellation_map[chunk]
            tx_symbols.append(coord)
            tx_patterns.append("".join(str(b) for b in chunk))

        # Channel parameters
        # Es/N0 linear: Es = 1.0 (unit circle points)
        es_n0_linear = 10.0 ** (req.snr_db / 10.0)
        # Noise variance per dimension (I and Q): sigma = sqrt(1 / (2 * Es/N0))
        noise_sigma = math.sqrt(1.0 / (2.0 * es_n0_linear))

        phase_offset_rad = math.radians(req.phase_offset_deg)
        freq_offset_rad = 2.0 * math.pi * req.freq_offset_norm

        rx_symbols: List[Tuple[float, float]] = []
        squared_error_sum = 0.0

        for k, (tx_i, tx_q) in enumerate(tx_symbols):
            # Apply carrier frequency and phase rotation
            total_phase = phase_offset_rad + freq_offset_rad * k
            cos_p = math.cos(total_phase)
            sin_p = math.sin(total_phase)

            rot_i = tx_i * cos_p - tx_q * sin_p
            rot_q = tx_i * sin_p + tx_q * cos_p

            # Add AWGN
            noise_i = rng.gauss(0.0, noise_sigma)
            noise_q = rng.gauss(0.0, noise_sigma)

            rx_i = rot_i + noise_i
            rx_q = rot_q + noise_q

            rx_symbols.append((rx_i, rx_q))

            # EVM accumulated relative to ideal unrotated transmitted symbol
            err_i = rx_i - tx_i
            err_q = rx_q - tx_q
            squared_error_sum += (err_i * err_i + err_q * err_q)

        # RMS EVM in percent
        evm_rms = math.sqrt(squared_error_sum / req.symbol_count) * 100.0

        # Slicer / Demodulation (Minimum Euclidean distance decision)
        rx_bits: List[int] = []
        symbol_errors = 0

        for k, (rx_i, rx_q) in enumerate(rx_symbols):
            best_bit_tuple = None
            min_dist_sq = float("inf")

            for bit_tuple, (c_i, c_q) in constellation_map.items():
                dist_sq = (rx_i - c_i) ** 2 + (rx_q - c_q) ** 2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    best_bit_tuple = bit_tuple

            rx_bits.extend(best_bit_tuple)

            tx_chunk = tuple(tx_bits[k * bits_per_symbol : (k + 1) * bits_per_symbol])
            if best_bit_tuple != tx_chunk:
                symbol_errors += 1

        # Calculate Bit Errors
        bit_errors = sum(1 for t_b, r_b in zip(tx_bits, rx_bits) if t_b != r_b)

        ber = bit_errors / total_bits
        ser = symbol_errors / req.symbol_count

        # Theoretical AWGN BER & SER (assuming zero carrier offsets)
        if req.modulation == ModulationType.QPSK:
            # QPSK: Eb/N0 = Es / 2
            # BER = Q(sqrt(2 * Eb/N0)) = Q(sqrt(Es/N0))
            q_val = _q_func(math.sqrt(es_n0_linear))
            theo_ber = q_val
            theo_ser = 2.0 * q_val - (q_val ** 2)
        else:
            # 8PSK: SER approx 2 * Q(sqrt(2 * Es/N0) * sin(pi/8))
            sin_term = math.sin(math.pi / 8.0)
            arg = math.sqrt(2.0 * es_n0_linear) * sin_term
            theo_ser = 2.0 * _q_func(arg)
            theo_ber = theo_ser / 3.0  # With Gray coding at high SNR

        # Limit points sent to client for responsive rendering (max 600 points)
        display_count = min(600, req.symbol_count)
        tx_points_out = [
            ConstellationPoint(i=tx_symbols[i][0], q=tx_symbols[i][1], symbol_index=i, bit_pattern=tx_patterns[i])
            for i in range(display_count)
        ]
        rx_points_out = [
            ConstellationPoint(i=rx_symbols[i][0], q=rx_symbols[i][1], symbol_index=i)
            for i in range(display_count)
        ]

        return SimulationResult(
            modulation=req.modulation,
            snr_db=req.snr_db,
            symbol_count=req.symbol_count,
            bit_count=total_bits,
            bit_errors=bit_errors,
            symbol_errors=symbol_errors,
            ber=ber,
            ser=ser,
            theoretical_ber=theo_ber,
            theoretical_ser=theo_ser,
            evm_rms_percent=evm_rms,
            phase_offset_deg=req.phase_offset_deg,
            freq_offset_norm=req.freq_offset_norm,
            ideal_constellation=ideal_points,
            tx_symbols=tx_points_out,
            rx_symbols=rx_points_out,
            is_simulated=True,
        )
