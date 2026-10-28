"""
Sample I/Q test fixture generator.
Creates reproducible, synthetic binary I/Q vectors for testing and demonstration.
"""
from __future__ import annotations
import os
import struct
from .models import ModulationType, SampleFormat, SimulationRequest
from .simulator import ModulationSimulator


def generate_iq_fixtures(output_dir: str) -> dict[str, str]:
    """Generate sample raw I/Q binary files for Signal Lab evaluation."""
    os.makedirs(output_dir, exist_ok=True)
    simulator = ModulationSimulator()

    fixtures = {}

    # 1. Clean QPSK (Float32 LE, 20 dB SNR)
    qpsk_req = SimulationRequest(
        modulation=ModulationType.QPSK,
        snr_db=20.0,
        symbol_count=1000,
        seed=101,
    )
    qpsk_res = simulator.simulate(qpsk_req)
    qpsk_path = os.path.join(output_dir, "qpsk_clean_20db.iq")
    with open(qpsk_path, "wb") as f:
        for pt in qpsk_res.rx_symbols:
            f.write(struct.pack("<ff", pt.i, pt.q))
    fixtures["qpsk_clean_20db"] = qpsk_path

    # 2. 8PSK (Float32 LE, 18 dB SNR)
    psk8_req = SimulationRequest(
        modulation=ModulationType.PSK8,
        snr_db=18.0,
        symbol_count=1000,
        seed=202,
    )
    psk8_res = simulator.simulate(psk8_req)
    psk8_path = os.path.join(output_dir, "8psk_snr_18db.iq")
    with open(psk8_path, "wb") as f:
        for pt in psk8_res.rx_symbols:
            f.write(struct.pack("<ff", pt.i, pt.q))
    fixtures["8psk_snr_18db"] = psk8_path

    # 3. Noisy QPSK with Int16 format (Int16 LE, 8 dB SNR, 15 deg phase offset)
    qpsk_noisy_req = SimulationRequest(
        modulation=ModulationType.QPSK,
        snr_db=8.0,
        phase_offset_deg=15.0,
        symbol_count=1000,
        seed=303,
    )
    qpsk_noisy_res = simulator.simulate(qpsk_noisy_req)
    int16_path = os.path.join(output_dir, "qpsk_int16_noisy.iq")
    with open(int16_path, "wb") as f:
        for pt in qpsk_noisy_res.rx_symbols:
            # Scale to int16 range [-32767, 32767]
            scaled_i = int(max(-32767, min(32767, pt.i * 16384)))
            scaled_q = int(max(-32767, min(32767, pt.q * 16384)))
            f.write(struct.pack("<hh", scaled_i, scaled_q))
    fixtures["qpsk_int16_noisy"] = int16_path

    return fixtures
