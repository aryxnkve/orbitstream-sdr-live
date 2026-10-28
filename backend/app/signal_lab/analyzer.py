"""
I/Q Signal Analyzer for raw capture files.
Validates supported binary sample formats (Float32, Int16, UInt8),
normalizes signal power, performs phase/frequency offset estimation,
evaluates M-th power modulation clustering (QPSK vs 8PSK), and calculates
EVM with explicit uncertainty reporting.
"""
from __future__ import annotations
import math
import struct
from typing import List, Tuple
from .models import (
    SampleFormat,
    IQAnalysisResult,
    ConstellationPoint,
)


class IQSignalAnalyzer:
    """
    Analyzes raw interleaved I/Q binary recordings.
    Enforces strict sample alignment and format validation.
    """

    FORMAT_SPECS = {
        SampleFormat.FLOAT32_LE: {
            "bytes_per_sample": 8,  # 4 bytes I + 4 bytes Q
            "struct_char": "<ff",
            "name": "32-bit Float LE",
        },
        SampleFormat.INT16_LE: {
            "bytes_per_sample": 4,  # 2 bytes I + 2 bytes Q
            "struct_char": "<hh",
            "name": "16-bit Signed Integer LE",
        },
        SampleFormat.UINT8: {
            "bytes_per_sample": 2,  # 1 byte I + 1 byte Q
            "struct_char": "BB",
            "name": "8-bit Unsigned Integer (RTL-SDR)",
        },
    }

    def analyze_bytes(
        self,
        data: bytes,
        sample_format: SampleFormat,
        filename: str = "capture.iq",
        max_analyze_samples: int = 5000,
    ) -> IQAnalysisResult:
        """Parse raw I/Q bytes and perform statistical signal analysis."""
        spec = self.FORMAT_SPECS.get(sample_format)
        if not spec:
            raise ValueError(f"Unsupported sample format: {sample_format}")

        bytes_per_sample = spec["bytes_per_sample"]
        if len(data) == 0:
            raise ValueError("I/Q sample buffer is empty.")

        if len(data) % bytes_per_sample != 0:
            raise ValueError(
                f"File size ({len(data)} bytes) is not aligned to {sample_format.value} "
                f"sample boundary ({bytes_per_sample} bytes per I/Q pair)."
            )

        total_samples = len(data) // bytes_per_sample
        if total_samples < 32:
            raise ValueError("Insufficient sample count for signal analysis (minimum 32 samples required).")

        # Parse complex samples
        samples_to_read = min(total_samples, max_analyze_samples)
        raw_samples: List[Tuple[float, float]] = []

        struct_fmt = spec["struct_char"]
        step = bytes_per_sample

        for i in range(0, samples_to_read * step, step):
            chunk = data[i : i + step]
            val_i, val_q = struct.unpack(struct_fmt, chunk)

            # Normalization to unit nominal amplitude
            if sample_format == SampleFormat.INT16_LE:
                val_i /= 32768.0
                val_q /= 32768.0
            elif sample_format == SampleFormat.UINT8:
                val_i = (val_i - 127.5) / 127.5
                val_q = (val_q - 127.5) / 127.5

            raw_samples.append((float(val_i), float(val_q)))

        # Power normalization (AGC)
        p_sum = sum(i * i + q * q for i, q in raw_samples)
        rms_power = math.sqrt(p_sum / len(raw_samples)) if p_sum > 0 else 1.0

        if rms_power <= 1e-9:
            raise ValueError("Signal power is zero or below noise floor.")

        norm_samples = [(i / rms_power, q / rms_power) for i, q in raw_samples]

        # 1. Frequency Offset Estimation via 4th power phase rotation
        # E[s[k]^4 * conj(s[k-1]^4)] = exp(j * 4 * 2*pi * Delta_f)
        sum_delta_phase = 0.0
        phase_pairs = 0
        for k in range(1, len(norm_samples)):
            i1, q1 = norm_samples[k - 1]
            i2, q2 = norm_samples[k]

            # 4th power: (i + j*q)^4
            # (i + j*q)^2 = (i^2 - q^2) + j*(2*i*q) = a + j*b
            a1 = i1 * i1 - q1 * q1
            b1 = 2.0 * i1 * q1
            p4_1_i = a1 * a1 - b1 * b1
            p4_1_q = 2.0 * a1 * b1

            a2 = i2 * i2 - q2 * q2
            b2 = 2.0 * i2 * q2
            p4_2_i = a2 * a2 - b2 * b2
            p4_2_q = 2.0 * a2 * b2

            # product p4_2 * conj(p4_1)
            prod_i = p4_2_i * p4_1_i + p4_2_q * p4_1_q
            prod_q = p4_2_q * p4_1_i - p4_2_i * p4_1_q

            d_phase = math.atan2(prod_q, prod_i)
            sum_delta_phase += d_phase
            phase_pairs += 1

        avg_d_phase = (sum_delta_phase / phase_pairs) if phase_pairs > 0 else 0.0
        # Delta_f_norm = avg_d_phase / (4 * 2 * pi)
        est_freq_offset_norm = avg_d_phase / (8.0 * math.pi)

        # 2. Modulation Classification via Circular Moments
        # R_4 = |1/N sum exp(j * 4 * theta)|
        # R_8 = |1/N sum exp(j * 8 * theta)|
        sum_4_i, sum_4_q = 0.0, 0.0
        sum_8_i, sum_8_q = 0.0, 0.0

        for i, q in norm_samples:
            theta = math.atan2(q, i)
            sum_4_i += math.cos(4.0 * theta)
            sum_4_q += math.sin(4.0 * theta)
            sum_8_i += math.cos(8.0 * theta)
            sum_8_q += math.sin(8.0 * theta)

        n_s = len(norm_samples)
        r4 = math.sqrt(sum_4_i * sum_4_i + sum_4_q * sum_4_q) / n_s
        r8 = math.sqrt(sum_8_i * sum_8_i + sum_8_q * sum_8_q) / n_s

        # Classification heuristics
        # In QPSK, 4*theta is aligned, so R4 is high (~1.0). R8 is also high because 8*theta = 2*4*theta.
        # In 8PSK, 4*theta cancels out across the 8 symmetric phases (R4 < 0.3), while R8 is high (~1.0).
        if r4 > 0.35:
            est_mod = "QPSK"
            confidence = min(98.0, max(50.0, r4 * 100.0))
            # For QPSK, nominal 4*theta is pi, so exp(j*(4*theta - pi)) = -exp(j*4*theta)
            est_phase_rad = math.atan2(-sum_4_q, -sum_4_i) / 4.0
        elif r8 > 0.30:
            est_mod = "8PSK"
            confidence = min(95.0, max(45.0, r8 * 110.0))
            # For 8PSK, nominal 8*theta is 0
            est_phase_rad = math.atan2(sum_8_q, sum_8_i) / 8.0
        else:
            est_mod = "QPSK (Low Confidence / Unlocked)"
            confidence = max(20.0, r4 * 60.0)
            est_phase_rad = 0.0

        est_phase_deg = math.degrees(est_phase_rad)

        # 3. EVM estimation against nearest M-PSK nominal point
        points_per_circle = 4 if "QPSK" in est_mod else 8
        step_angle = (2.0 * math.pi) / points_per_circle
        base_phase = (math.pi / 4.0 if "QPSK" in est_mod else 0.0) + est_phase_rad

        total_err_sq = 0.0
        for i, q in norm_samples:
            theta = math.atan2(q, i)
            rel_angle = theta - base_phase
            k_idx = round(rel_angle / step_angle)
            quantized_angle = base_phase + k_idx * step_angle
            ideal_i = math.cos(quantized_angle)
            ideal_q = math.sin(quantized_angle)
            err_sq = (i - ideal_i) ** 2 + (q - ideal_q) ** 2
            total_err_sq += err_sq

        evm_rms = math.sqrt(total_err_sq / len(norm_samples)) * 100.0
        evm_clamped = max(1.0, min(100.0, evm_rms))

        # Approximate SNR from EVM: SNR_dB ~= -20 * log10(EVM / 100)
        est_snr_db = -20.0 * math.log10(evm_clamped / 100.0)

        # Output points (up to 600 for clean visualization)
        display_pts = [
            ConstellationPoint(i=norm_samples[k][0], q=norm_samples[k][1], symbol_index=k)
            for k in range(min(600, len(norm_samples)))
        ]

        uncertainty_statement = (
            f"Estimated {est_mod} based on statistical phase clustering (R4={r4:.2f}, R8={r8:.2f}). "
            "Note: Exact modulation validation requires symbol timing synchronisation, matched filtering (RRC), "
            "and successful FEC / frame sync. I/Q measurements alone indicate signal characteristics, "
            "not verified satellite transmission validity."
        )

        return IQAnalysisResult(
            filename=filename,
            total_samples=total_samples,
            sample_format=sample_format,
            estimated_modulation=est_mod,
            modulation_confidence=round(confidence, 1),
            estimated_snr_db=round(est_snr_db, 1),
            estimated_evm_percent=round(evm_rms, 1),
            estimated_freq_offset_norm=round(est_freq_offset_norm, 5),
            estimated_phase_offset_deg=round(est_phase_deg, 1),
            constellation_samples=display_pts,
            uncertainty_note=uncertainty_statement,
            is_estimate=True,
        )
