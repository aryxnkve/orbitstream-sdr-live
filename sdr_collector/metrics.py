"""
Signal metric calculations for RTL-SDR I/Q complex samples.
Calculates relative power (dBFS), peak power, PAPR, DC offsets, FFT power spectrum,
and estimated SNR.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List
import numpy as np


def calculate_metrics(
    samples: np.ndarray,
    sample_rate_hz: int,
    center_frequency_hz: int,
    num_spectrum_bins: int = 64,
) -> Dict[str, Any]:
    """
    Compute rigorous physical and spectral metrics from complex I/Q samples.
    
    Args:
        samples: 1D NumPy complex array representing I/Q baseband samples.
        sample_rate_hz: Sampling rate in Hz.
        center_frequency_hz: Tuner center frequency in Hz.
        num_spectrum_bins: Number of bins for the downsampled FFT spectrum payload.

    Returns:
        Dictionary containing relative power, spectral bins, and health metrics.
    """
    if samples is None or len(samples) == 0:
        return {
            "is_valid": False,
            "validation_notes": "No samples received from SDR device.",
            "sample_count": 0,
            "relative_power_dbfs": -120.0,
            "peak_power_dbfs": -120.0,
            "papr_db": 0.0,
            "snr_estimate_db": 0.0,
            "noise_floor_dbfs": -120.0,
            "dc_i": 0.0,
            "dc_q": 0.0,
            "clipping_ratio": 0.0,
            "spectrum_bins": [round(-100.0, 2)] * num_spectrum_bins,
            "freq_start_hz": center_frequency_hz - (sample_rate_hz / 2.0),
            "freq_end_hz": center_frequency_hz + (sample_rate_hz / 2.0),
        }

    # Ensure 1D array
    samples = np.asarray(samples).flatten()
    sample_count = int(samples.size)

    # Validity check for non-finite values (NaN / Inf)
    if not np.isfinite(samples).all():
        return {
            "is_valid": False,
            "validation_notes": "Non-finite values (NaN/Inf) detected in sample buffer.",
            "sample_count": sample_count,
            "relative_power_dbfs": -120.0,
            "peak_power_dbfs": -120.0,
            "papr_db": 0.0,
            "snr_estimate_db": 0.0,
            "noise_floor_dbfs": -120.0,
            "dc_i": 0.0,
            "dc_q": 0.0,
            "clipping_ratio": 0.0,
            "spectrum_bins": [round(-100.0, 2)] * num_spectrum_bins,
            "freq_start_hz": center_frequency_hz - (sample_rate_hz / 2.0),
            "freq_end_hz": center_frequency_hz + (sample_rate_hz / 2.0),
        }

    # 1. Power Metrics (relative to Full Scale 1.0 peak)
    i_vals = np.real(samples)
    q_vals = np.imag(samples)
    mags_sq = (i_vals ** 2) + (q_vals ** 2)

    mean_power = float(np.mean(mags_sq))
    # Safeguard against log(0) with 1e-15 floor (-150 dBFS)
    relative_power_dbfs = float(10.0 * np.log10(max(mean_power, 1e-15)))

    peak_power = float(np.max(mags_sq)) if sample_count > 0 else 0.0
    peak_power_dbfs = float(10.0 * np.log10(max(peak_power, 1e-15)))

    # Peak-to-Average Power Ratio (PAPR)
    papr_ratio = peak_power / max(mean_power, 1e-15)
    papr_db = float(10.0 * np.log10(max(papr_ratio, 1.0)))

    # 2. DC Imbalance / Offset
    dc_i = float(np.mean(i_vals))
    dc_q = float(np.mean(q_vals))

    # 3. ADC Clipping Ratio (RTL-SDR samples normalized to [-1.0, 1.0])
    # Values close to +/- 1.0 on I or Q rails indicate ADC saturation
    clipped_i = int(np.sum(np.abs(i_vals) >= 0.99))
    clipped_q = int(np.sum(np.abs(q_vals) >= 0.99))
    clipping_ratio = float((clipped_i + clipped_q) / max(1, sample_count * 2))

    # 4. FFT Power Spectrum Analysis
    # Use power-of-two subset or windowed FFT
    fft_size = min(sample_count, 16384)
    # If sample count is large, select a representative center slice for FFT
    if sample_count > fft_size:
        start_idx = (sample_count - fft_size) // 2
        fft_subset = samples[start_idx : start_idx + fft_size]
    else:
        fft_subset = samples

    window = np.hanning(len(fft_subset))
    windowed = fft_subset * window
    window_norm = np.sum(window ** 2) or 1.0

    fft_result = np.fft.fftshift(np.fft.fft(windowed))
    psd = (np.abs(fft_result) ** 2) / window_norm
    psd_dbfs = 10.0 * np.log10(np.maximum(psd, 1e-15))

    # Downsample PSD to num_spectrum_bins
    spectrum_bins: List[float] = []
    chunk_size = len(psd_dbfs) // num_spectrum_bins
    if chunk_size > 0:
        for b in range(num_spectrum_bins):
            chunk = psd_dbfs[b * chunk_size : (b + 1) * chunk_size]
            spectrum_bins.append(round(float(np.mean(chunk)), 2))
    else:
        spectrum_bins = [round(float(v), 2) for v in psd_dbfs[:num_spectrum_bins]]

    # 5. Noise Floor & SNR Estimation
    # Noise floor estimated from the lower 25th percentile of spectral power
    noise_floor_dbfs = float(np.percentile(psd_dbfs, 25))
    peak_spectrum_dbfs = float(np.max(psd_dbfs))
    snr_estimate_db = float(max(0.0, peak_spectrum_dbfs - noise_floor_dbfs))

    freq_start_hz = center_frequency_hz - (sample_rate_hz / 2.0)
    freq_end_hz = center_frequency_hz + (sample_rate_hz / 2.0)

    return {
        "is_valid": True,
        "validation_notes": "Valid I/Q measurement acquired.",
        "sample_count": sample_count,
        "relative_power_dbfs": round(relative_power_dbfs, 2),
        "peak_power_dbfs": round(peak_power_dbfs, 2),
        "papr_db": round(papr_db, 2),
        "snr_estimate_db": round(snr_estimate_db, 2),
        "noise_floor_dbfs": round(noise_floor_dbfs, 2),
        "dc_i": round(dc_i, 4),
        "dc_q": round(dc_q, 4),
        "clipping_ratio": round(clipping_ratio, 4),
        "spectrum_bins": spectrum_bins,
        "freq_start_hz": freq_start_hz,
        "freq_end_hz": freq_end_hz,
    }
