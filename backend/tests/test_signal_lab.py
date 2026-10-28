"""
Unit tests for the Signal Lab module (QPSK and 8PSK).
Verifies modulation simulation, AWGN channel statistics,
carrier impairments, EVM calculation, and I/Q binary file parsing.
"""
import struct
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.signal_lab.models import (
    ModulationType,
    SampleFormat,
    SimulationRequest,
)
from app.signal_lab.simulator import ModulationSimulator
from app.signal_lab.analyzer import IQSignalAnalyzer


@pytest.fixture
def client():
    return TestClient(app)


def test_qpsk_simulation_high_snr():
    sim = ModulationSimulator()
    req = SimulationRequest(
        modulation=ModulationType.QPSK,
        snr_db=25.0,
        symbol_count=1000,
        seed=42,
    )
    res = sim.simulate(req)

    assert res.modulation == ModulationType.QPSK
    assert res.symbol_count == 1000
    assert res.bit_count == 2000
    assert len(res.ideal_constellation) == 4
    assert res.is_simulated is True
    # At 25 dB SNR in AWGN, BER should be 0 or near 0
    assert res.ber == 0.0
    assert res.ser == 0.0
    assert res.evm_rms_percent < 10.0


def test_qpsk_simulation_low_snr():
    sim = ModulationSimulator()
    req = SimulationRequest(
        modulation=ModulationType.QPSK,
        snr_db=2.0,
        symbol_count=2000,
        seed=42,
    )
    res = sim.simulate(req)

    assert res.ber > 0.01  # Should have measurable errors at 2 dB SNR
    assert res.ser >= res.ber
    assert res.evm_rms_percent > 30.0


def test_8psk_simulation():
    sim = ModulationSimulator()
    req = SimulationRequest(
        modulation=ModulationType.PSK8,
        snr_db=20.0,
        symbol_count=1000,
        seed=123,
    )
    res = sim.simulate(req)

    assert res.modulation == ModulationType.PSK8
    assert res.symbol_count == 1000
    assert res.bit_count == 3000
    assert len(res.ideal_constellation) == 8
    assert res.ser < 0.05


def test_simulation_reproducibility():
    sim = ModulationSimulator()
    req1 = SimulationRequest(modulation=ModulationType.QPSK, snr_db=15.0, symbol_count=500, seed=99)
    req2 = SimulationRequest(modulation=ModulationType.QPSK, snr_db=15.0, symbol_count=500, seed=99)

    res1 = sim.simulate(req1)
    res2 = sim.simulate(req2)

    assert res1.ber == res2.ber
    assert res1.evm_rms_percent == res2.evm_rms_percent
    assert res1.rx_symbols[0].i == res2.rx_symbols[0].i
    assert res1.rx_symbols[0].q == res2.rx_symbols[0].q


def test_carrier_phase_offset():
    sim = ModulationSimulator()
    req = SimulationRequest(
        modulation=ModulationType.QPSK,
        snr_db=30.0,
        phase_offset_deg=45.0,
        symbol_count=500,
        seed=42,
    )
    res = sim.simulate(req)

    assert res.phase_offset_deg == 45.0
    # A 45° rotation on QPSK moves points directly to the decision boundary, increasing EVM
    assert res.evm_rms_percent > 50.0


def test_iq_analyzer_float32():
    analyzer = IQSignalAnalyzer()
    sim = ModulationSimulator()

    # Generate synthetic clean QPSK
    req = SimulationRequest(modulation=ModulationType.QPSK, snr_db=22.0, symbol_count=500, seed=77)
    res = sim.simulate(req)

    data = bytearray()
    for pt in res.rx_symbols:
        data.extend(struct.pack("<ff", pt.i, pt.q))

    analysis = analyzer.analyze_bytes(bytes(data), SampleFormat.FLOAT32_LE, "test_qpsk.iq")

    assert "QPSK" in analysis.estimated_modulation
    assert analysis.modulation_confidence >= 60.0
    assert analysis.total_samples == 500
    assert analysis.is_estimate is True
    assert len(analysis.constellation_samples) > 0


def test_iq_analyzer_unaligned_buffer():
    analyzer = IQSignalAnalyzer()
    bad_data = b"\x00" * 7  # Float32 needs multiple of 8 bytes

    with pytest.raises(ValueError, match="not aligned"):
        analyzer.analyze_bytes(bad_data, SampleFormat.FLOAT32_LE)


def test_signal_api_endpoints(client):
    # Simulation endpoint
    sim_res = client.post("/api/signal/simulate", json={
        "modulation": "qpsk",
        "snr_db": 18.0,
        "symbol_count": 500,
        "seed": 42
    })
    assert sim_res.status_code == 200
    data = sim_res.json()
    assert data["modulation"] == "qpsk"
    assert "evm_rms_percent" in data
    assert "theoretical_ber" in data
    assert len(data["ideal_constellation"]) == 4

    # Sample fixtures list
    samples_res = client.get("/api/signal/samples")
    assert samples_res.status_code == 200
    samples = samples_res.json().get("samples", [])
    assert len(samples) >= 3

    # Analyze sample fixture
    analyze_sample = client.post("/api/signal/samples/qpsk_clean_20db/analyze")
    assert analyze_sample.status_code == 200
    iq_data = analyze_sample.json()
    assert "QPSK" in iq_data["estimated_modulation"]
    assert iq_data["estimated_snr_db"] > 10.0
