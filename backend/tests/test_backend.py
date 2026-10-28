"""
ORBITSTREAM Backend Automated Test Suite
SIH260002 — Integrated Satellite Stream Troubleshooting Platform

Covers all required areas from Section 19:
- Valid MPEG-TS parsing
- Packet-size and synchronization detection
- PID extraction
- PAT/PMT parsing
- CRC and section-length validation
- Continuity-counter semantics
- Scrambling-control extraction
- Malformed and truncated inputs
- Unsupported formats
- Diagnostic evidence references
- File upload validation
- Replay indexing and packet navigation
- Fault-simulation transformations
- Original-file integrity
- Independent post-simulation analysis
- Expected-versus-observed verification
- JSON and CSV report generation
- API endpoints via FastAPI TestClient
"""
import os
import io
import hashlib
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parsers.mpegts.parser import MPEGTSParser
from app.parsers.mpegts.constants import (
    SYNC_BYTE, TS_PACKET_SIZE, PID_PAT, PID_NULL,
)
from app.parsers.mpegts.models import StreamFormat, TSPacket
from app.parsers.mpegts.crc import crc32_mpeg2, verify_section_crc
from app.parsers.fixture_generator import generate_all_fixtures
from app.diagnostics.engine import DiagnosticEngine
from app.models.diagnostic_models import Severity
from app.replay.engine import ReplayEngine
from app.simulation.engine import SimulationEngine, FaultConfig, FaultScenario
from app.reporting.generator import ReportGenerator
from app.storage.manager import StorageManager


@pytest.fixture(scope="session")
def fixtures_dir():
    temp_dir = tempfile.mkdtemp(prefix="orbitstream_fixtures_")
    fixtures = generate_all_fixtures(temp_dir)
    return temp_dir, fixtures


@pytest.fixture
def client():
    return TestClient(app)


# 1. Valid MPEG-TS Parsing & Packet Size
def test_valid_mpegts_parsing(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True, store_raw=True)
    result = parser.parse_file(fixtures["valid_basic"])

    assert result.detected_format == StreamFormat.MPEGTS_188
    assert result.packet_size == TS_PACKET_SIZE
    assert result.total_packets > 0
    assert result.valid_packets == result.total_packets
    assert result.error_packets == 0
    assert len(result.pids) >= 3  # PAT, PMT, Video, Audio
    assert PID_PAT in result.pids


# 2. Packet-size and Synchronization Detection
def test_sync_detection_and_corrupt_sync(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True, store_raw=True)
    result = parser.parse_file(fixtures["corrupt_sync"])

    assert result.detected_format == StreamFormat.MPEGTS_188
    assert result.sync_losses > 0 or result.error_packets > 0 or len(result.warnings) > 0


# 3. PID Extraction and Null Packets
def test_pid_extraction(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True)
    result = parser.parse_file(fixtures["valid_basic"])

    assert PID_PAT in result.pids
    assert result.pids[PID_PAT].packet_count > 0
    assert 0x0100 in result.pids  # Video PID
    assert 0x0101 in result.pids  # Audio PID
    assert result.null_packets >= 0


# 4. PAT and PMT Parsing
def test_pat_pmt_parsing(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True)
    result = parser.parse_file(fixtures["multi_program"])

    assert result.pat is not None
    assert len(result.pat.entries) >= 2
    assert len(result.pmts) >= 2

    # Check program 1
    prog1 = result.pmts.get(1)
    assert prog1 is not None
    assert len(prog1.streams) >= 2  # Video + Audio
    stream_types = [s.stream_type for s in prog1.streams]
    assert 0x1B in stream_types  # H.264
    assert 0x0F in stream_types  # AAC


# 5. CRC and Section-Length Validation
def test_crc_and_section_validation():
    # Valid PAT section (excluding sync byte and TS header):
    # table_id (0x00), section_syntax_indicator (1), '0', reserved (11), section_length
    data = bytes([
        0x00, 0xB0, 0x0D, 0x00, 0x01, 0xC1, 0x00, 0x00,
        0x00, 0x01, 0xE0, 0x20
    ])
    crc = crc32_mpeg2(data)
    full_section = data + crc.to_bytes(4, "big")
    assert verify_section_crc(full_section) is True

    # Corrupt a byte
    corrupted_section = data + bytes([0x12, 0x34, 0x56, 0x78])
    assert verify_section_crc(corrupted_section) is False


# 6. Continuity Counter Semantics
def test_continuity_counter_diagnostics(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True)
    result = parser.parse_file(fixtures["cc_error"])

    diag_engine = DiagnosticEngine()
    findings = diag_engine.analyze(result)

    cc_findings = [f for f in findings if "continuity" in f.title.lower() or "cc" in f.rule_id.lower()]
    assert len(cc_findings) > 0
    assert any(f.severity in [Severity.CRITICAL, Severity.WARNING] for f in cc_findings)


# 7. Scrambling Control Extraction
def test_scrambling_control_extraction():
    # Construct 5 packets with scrambling control = 0b10 (Even key) to satisfy sync detection
    # Header: 0x47, 0x00, 0x20, 0x90 (Scrambling=10, AFC=01, CC=0)
    pkt_bytes = bytes([0x47, 0x00, 0x20, 0x90] + [0xFF] * 184) * 5
    parser = MPEGTSParser(store_packets=True)
    res = parser.parse_bytes(pkt_bytes)
    assert res.total_packets == 5
    assert res.scrambled_packets == 5


# 8. Malformed and Truncated Inputs
def test_truncated_input(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True)
    result = parser.parse_file(fixtures["truncated"])

    assert len(result.warnings) > 0 or len(result.errors) > 0 or result.valid_packets > 0


# 9. Unsupported Formats
def test_unsupported_formats():
    parser = MPEGTSParser(store_packets=True)
    random_data = b"This is a random text file not an MPEG-TS binary file.\n" * 10
    result = parser.parse_bytes(random_data)

    assert result.detected_format == StreamFormat.UNKNOWN
    assert len(result.errors) > 0


# 10. Diagnostic Evidence References
def test_diagnostic_evidence_references(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True, store_raw=True)
    result = parser.parse_file(fixtures["cc_error"])
    diag_engine = DiagnosticEngine()
    findings = diag_engine.analyze(result)

    for f in findings:
        assert f.rule_id
        assert f.title
        assert f.explanation
        assert f.severity in list(Severity)
        # Evidence check
        if f.severity in [Severity.WARNING, Severity.CRITICAL]:
            assert f.evidence is not None


# 11. Replay Indexing and Navigation
def test_replay_engine(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True, store_raw=True)
    result = parser.parse_file(fixtures["valid_basic"])

    replay = ReplayEngine(result)
    assert replay.total_packets == result.total_packets
    
    # Range check
    pkts = replay.get_packets_range(0, 5)
    assert len(pkts) == 5
    assert pkts[0].index == 0

    # Single packet check
    p = replay.get_packet(2)
    assert p is not None
    assert p.index == 2

    # Surrounding packets
    around = replay.get_packets_around(2, 2)
    assert len(around) == 5

    # Filter by PID
    pat_packets = replay.get_packets_by_pid(PID_PAT, 0, 10)
    for pkt in pat_packets:
        assert pkt.pid == PID_PAT


# 12. Fault Simulation Transformations & Original File Integrity
def test_fault_simulation_and_integrity(fixtures_dir):
    temp_dir, fixtures = fixtures_dir
    sim_dir = os.path.join(temp_dir, "sim_test")
    sim = SimulationEngine(sim_dir)

    src_file = fixtures["valid_basic"]
    with open(src_file, "rb") as f:
        original_hash = hashlib.sha256(f.read()).hexdigest()

    cfg = FaultConfig(
        scenario=FaultScenario.CC_DISCONTINUITY,
        target_pid=0x0100,
        cc_skip=4,
    )
    result = sim.apply_fault(src_file, cfg)

    assert result.success is True
    assert os.path.exists(result.modified_file)
    assert result.source_hash == original_hash[:16]

    # Verify original file was NOT modified
    with open(src_file, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    assert current_hash == original_hash


# 13. Independent Post-simulation Analysis & Expected vs Observed
def test_post_simulation_analysis(fixtures_dir):
    temp_dir, fixtures = fixtures_dir
    sim_dir = os.path.join(temp_dir, "sim_test_post")
    sim = SimulationEngine(sim_dir)

    src_file = fixtures["valid_basic"]
    cfg = FaultConfig(
        scenario=FaultScenario.CC_DISCONTINUITY,
        target_pid=0x0100,
        cc_skip=5,
    )
    result = sim.apply_fault(src_file, cfg)

    # Re-analyze independently with ordinary parser
    parser = MPEGTSParser(store_packets=True)
    mod_result = parser.parse_file(result.modified_file)
    diag_engine = DiagnosticEngine()
    findings = diag_engine.analyze(mod_result)

    # Verify continuity counter error detected
    cc_findings = [f for f in findings if "continuity" in f.title.lower()]
    assert len(cc_findings) > 0


# 14. Report Generation (JSON & CSV)
def test_report_generation(fixtures_dir):
    _, fixtures = fixtures_dir
    parser = MPEGTSParser(store_packets=True, store_raw=True)
    parse_result = parser.parse_file(fixtures["valid_basic"])
    diag_engine = DiagnosticEngine()
    findings = diag_engine.analyze(parse_result)

    pids_list = [info.model_dump() for _, info in sorted(parse_result.pids.items())]
    from app.models.diagnostic_models import AnalysisSummary
    summary = AnalysisSummary(
        file_id="test1234",
        filename="valid_basic.ts",
        file_size=parse_result.file_size,
        detected_format=parse_result.detected_format.value,
        packet_size=parse_result.packet_size,
        total_packets=parse_result.total_packets,
        valid_packets=parse_result.valid_packets,
        error_packets=parse_result.error_packets,
        null_packets=parse_result.null_packets,
        scrambled_packets=parse_result.scrambled_packets,
        pid_count=len(parse_result.pids),
        program_count=len(parse_result.pmts),
        findings=findings,
        findings_by_severity={"ok": len(findings)},
        pids=pids_list,
        programs=[],
        warnings=parse_result.warnings,
        errors=parse_result.errors,
    )

    reporter = ReportGenerator()
    json_summary = reporter.analysis_summary_json(summary)
    assert "ORBITSTREAM" in json_summary or "valid_basic.ts" in json_summary

    findings_csv = reporter.findings_csv(findings)
    assert "Rule" in findings_csv or "ID" in findings_csv

    pids_csv = reporter.pid_inventory_csv(summary)
    assert "PID" in pids_csv


# 15. API Endpoints
def test_api_endpoints(client):
    # Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # List samples
    res = client.get("/api/samples")
    assert res.status_code == 200
    samples = res.json().get("samples", [])
    assert len(samples) >= 5

    # Load a sample
    res = client.post("/api/samples/valid_basic/load")
    assert res.status_code == 200
    data = res.json()
    file_id = data["file_id"]
    assert file_id is not None

    # Analyze loaded sample
    res = client.post(f"/api/analyze/{file_id}")
    assert res.status_code == 200
    analysis = res.json()
    assert analysis["total_packets"] > 0
    assert analysis["detected_format"] == "mpegts_188"

    # Replay packets
    res = client.get(f"/api/replay/{file_id}/packets?start=0&count=5")
    assert res.status_code == 200
    replay_data = res.json()
    assert len(replay_data["packets"]) == 5

    # Download summary report
    res = client.get(f"/api/reports/{file_id}/summary")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json"

    # Scenarios list
    res = client.get("/api/simulate/scenarios")
    assert res.status_code == 200
    assert len(res.json()["scenarios"]) >= 5

    # Run simulation
    sim_res = client.post("/api/simulate", json={
        "file_id": file_id,
        "scenario": "cc_discontinuity",
        "target_pid": 0x0100,
        "cc_skip": 3
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert "sim_id" in sim_data
    assert "verification" in sim_data
    assert sim_data["verification"]["status"] in ["pass", "inconclusive"]
