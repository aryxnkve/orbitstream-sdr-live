"""
API routes for file upload, analysis, replay, simulation, and reporting.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import io

from ..core.config import get_config
from ..parsers.mpegts import MPEGTSParser
from ..parsers.mpegts.models import ParseResult, StreamFormat
from ..parsers.fixture_generator import generate_all_fixtures
from ..diagnostics.engine import DiagnosticEngine
from ..models.diagnostic_models import AnalysisSummary, DiagnosticFinding, Severity
from ..replay.engine import ReplayEngine
from ..simulation.engine import SimulationEngine, FaultConfig, FaultScenario
from ..reporting.generator import ReportGenerator
from ..storage.manager import StorageManager
from ..signal_lab import (
    ModulationSimulator,
    IQSignalAnalyzer,
    SignalSimulationRequest,
    SampleFormat,
)
from ..signal_lab.fixtures import generate_iq_fixtures

router = APIRouter()

# Application state — in a real production app this would use proper
# session management. For this offline tool, in-memory state is acceptable.
_state: dict = {
    "analyses": {},       # file_id -> AnalysisSummary
    "parse_results": {},  # file_id -> ParseResult
    "replay_engines": {}, # file_id -> ReplayEngine
    "simulation_results": {},  # sim_id -> FaultResult
    "sim_analyses": {},   # sim_id -> AnalysisSummary
}

config = get_config()
storage = StorageManager(config.storage_dir)
sim_engine = SimulationEngine(os.path.join(config.storage_dir, "simulations"))
report_gen = ReportGenerator()
diag_engine = DiagnosticEngine()
sig_simulator = ModulationSimulator()
iq_analyzer = IQSignalAnalyzer()


# ── Upload & Analysis ──────────────────────────────────────────────

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a stream file for analysis."""
    if not file.filename:
        raise HTTPException(400, "No filename provided.")

    # Read file content with size limit
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > storage.MAX_FILE_SIZE:
        raise HTTPException(413, f"File exceeds maximum size of {storage.MAX_FILE_SIZE // (1024*1024)} MB.")

    # Store safely
    file_id, file_path = storage.store_upload(content, file.filename)

    # Quick format detection
    parser = MPEGTSParser(store_packets=False, max_packets=5)
    quick_result = parser.parse_bytes(content[:2048], file.filename)
    detected_format = quick_result.detected_format.value

    return {
        "file_id": file_id,
        "filename": file.filename,
        "file_size": len(content),
        "detected_format": detected_format,
    }


@router.post("/analyze/{file_id}")
async def analyze_file(file_id: str):
    """Run full analysis on an uploaded file."""
    file_path = storage.get_upload_path(file_id)
    if not file_path:
        raise HTTPException(404, "File not found. It may have been cleaned up.")

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Parse
    parser = MPEGTSParser(store_packets=True, store_payload=False, store_raw=True)
    parse_result = parser.parse_file(file_path)

    # Run diagnostics
    findings = diag_engine.analyze(parse_result)

    # Build summary
    pids_list = []
    for pid, info in sorted(parse_result.pids.items()):
        pids_list.append(info.model_dump())

    programs_list = []
    for prog_num, pmt in parse_result.pmts.items():
        programs_list.append({
            "program_number": prog_num,
            "pcr_pid": pmt.pcr_pid_hex,
            "streams": [s.model_dump() for s in pmt.streams],
        })

    findings_by_severity = {}
    for f in findings:
        sev = f.severity.value
        findings_by_severity[sev] = findings_by_severity.get(sev, 0) + 1

    summary = AnalysisSummary(
        file_id=file_id,
        filename=filename,
        file_size=file_size,
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
        findings_by_severity=findings_by_severity,
        pids=pids_list,
        programs=programs_list,
        warnings=parse_result.warnings,
        errors=parse_result.errors,
        parser_version=parse_result.parser_version,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        sync_losses=parse_result.sync_losses,
    )

    # Store state
    _state["analyses"][file_id] = summary
    _state["parse_results"][file_id] = parse_result
    _state["replay_engines"][file_id] = ReplayEngine(parse_result)

    return summary.model_dump()


@router.get("/analysis/{file_id}")
async def get_analysis(file_id: str):
    """Retrieve cached analysis results."""
    if file_id not in _state["analyses"]:
        raise HTTPException(404, "No analysis found for this file. Please run analysis first.")
    return _state["analyses"][file_id].model_dump()


# ── Sample Fixtures ────────────────────────────────────────────────

@router.get("/samples")
async def list_samples():
    """List available sample/fixture files."""
    fixtures = generate_all_fixtures(config.fixtures_dir)
    samples = []
    for name, path in fixtures.items():
        size = os.path.getsize(path)
        samples.append({
            "name": name,
            "filename": os.path.basename(path),
            "file_size": size,
            "description": _fixture_descriptions().get(name, "Synthetic test fixture"),
            "is_synthetic": True,
        })
    return {"samples": samples}


@router.post("/samples/{sample_name}/load")
async def load_sample(sample_name: str):
    """Load a sample fixture for analysis."""
    fixtures = generate_all_fixtures(config.fixtures_dir)
    if sample_name not in fixtures:
        raise HTTPException(404, f"Sample '{sample_name}' not found.")

    path = fixtures[sample_name]
    with open(path, "rb") as f:
        content = f.read()

    file_id, file_path = storage.store_upload(content, os.path.basename(path))

    return {
        "file_id": file_id,
        "filename": os.path.basename(path),
        "file_size": len(content),
        "detected_format": "mpegts_188",
        "is_synthetic": True,
        "sample_name": sample_name,
    }


def _fixture_descriptions():
    return {
        "valid_basic": "Valid MPEG-TS with PAT, PMT, H.264 video, and AAC audio.",
        "multi_program": "Multi-program TS with two programs and four elementary streams.",
        "cc_error": "TS with a deliberate continuity counter gap on the video PID.",
        "corrupt_sync": "TS with a corrupted sync byte at packet index 5.",
        "truncated": "TS with the final packet truncated to 100 bytes.",
    }


# ── Replay ─────────────────────────────────────────────────────────

@router.get("/replay/{file_id}/packets")
async def replay_packets(
    file_id: str,
    start: int = Query(0, ge=0),
    count: int = Query(20, ge=1, le=200),
    pid: Optional[int] = Query(None),
):
    """Get packets for replay view."""
    if file_id not in _state["replay_engines"]:
        raise HTTPException(404, "No replay data available. Run analysis first.")

    engine = _state["replay_engines"][file_id]

    if pid is not None:
        packets = engine.get_packets_by_pid(pid, start, count)
    else:
        packets = engine.get_packets_range(start, count)

    result = []
    for pkt in packets:
        result.append(engine.get_packet_header_display(pkt))

    return {
        "packets": result,
        "total": engine.total_packets,
        "start": start,
        "count": len(result),
        "available_pids": engine.available_pids,
    }


@router.get("/replay/{file_id}/packet/{packet_index}")
async def get_single_packet(file_id: str, packet_index: int):
    """Get a single packet with full details."""
    if file_id not in _state["replay_engines"]:
        raise HTTPException(404, "No replay data available.")

    engine = _state["replay_engines"][file_id]
    packet = engine.get_packet(packet_index)
    if not packet:
        raise HTTPException(404, f"Packet {packet_index} not found.")

    display = engine.get_packet_header_display(packet)
    # Add surrounding context
    context = engine.get_packets_around(packet_index, 3)
    display["context"] = [engine.get_packet_header_display(p) for p in context]

    return display


# ── Simulation ─────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    file_id: str
    scenario: str
    target_pid: int = 0x0100
    target_packet_indices: list[int] = Field(default_factory=list)
    cc_skip: int = 3
    corrupt_byte: int = 0x00
    scrambling_value: int = 2
    description: str = ""


@router.post("/simulate")
async def run_simulation(req: SimulationRequest):
    """Run a fault simulation on a copy of the uploaded file."""
    file_path = storage.get_upload_path(req.file_id)
    if not file_path:
        raise HTTPException(404, "Source file not found.")

    try:
        scenario = FaultScenario(req.scenario)
    except ValueError:
        raise HTTPException(400, f"Unknown scenario: {req.scenario}. "
                           f"Valid: {[s.value for s in FaultScenario]}")

    fault_config = FaultConfig(
        scenario=scenario,
        target_pid=req.target_pid,
        target_packet_indices=req.target_packet_indices,
        cc_skip=req.cc_skip,
        corrupt_byte=req.corrupt_byte,
        scrambling_value=req.scrambling_value,
        description=req.description,
    )

    result = sim_engine.apply_fault(file_path, fault_config)
    if not result.success:
        raise HTTPException(500, f"Simulation failed: {result.error}")

    sim_id = str(uuid.uuid4())[:12]
    _state["simulation_results"][sim_id] = result

    # Auto-analyze the modified file
    parser = MPEGTSParser(store_packets=True, store_payload=False, store_raw=True)
    mod_parse = parser.parse_file(result.modified_file)
    mod_findings = diag_engine.analyze(mod_parse)

    mod_pids_list = [info.model_dump() for _, info in sorted(mod_parse.pids.items())]
    mod_findings_by_severity = {}
    for f in mod_findings:
        sev = f.severity.value
        mod_findings_by_severity[sev] = mod_findings_by_severity.get(sev, 0) + 1

    mod_summary = AnalysisSummary(
        file_id=sim_id,
        filename=os.path.basename(result.modified_file),
        file_size=os.path.getsize(result.modified_file),
        detected_format=mod_parse.detected_format.value,
        packet_size=mod_parse.packet_size,
        total_packets=mod_parse.total_packets,
        valid_packets=mod_parse.valid_packets,
        error_packets=mod_parse.error_packets,
        null_packets=mod_parse.null_packets,
        scrambled_packets=mod_parse.scrambled_packets,
        pid_count=len(mod_parse.pids),
        program_count=len(mod_parse.pmts),
        findings=mod_findings,
        findings_by_severity=mod_findings_by_severity,
        pids=mod_pids_list,
        programs=[],
        warnings=mod_parse.warnings,
        errors=mod_parse.errors,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
    )

    _state["sim_analyses"][sim_id] = mod_summary

    # Build verification
    original_summary = _state["analyses"].get(req.file_id)
    verification = _build_verification(result, original_summary, mod_summary)

    return {
        "sim_id": sim_id,
        "fault_result": result.model_dump(),
        "modified_analysis": mod_summary.model_dump(),
        "verification": verification,
    }


@router.get("/simulate/scenarios")
async def list_scenarios():
    """List available fault simulation scenarios."""
    return {
        "scenarios": [
            {
                "id": "remove_packets",
                "name": "Remove packets",
                "description": "Remove selected transport packets to simulate packet loss.",
                "parameters": ["target_pid", "target_packet_indices"],
            },
            {
                "id": "cc_discontinuity",
                "name": "Continuity counter discontinuity",
                "description": "Introduce a continuity counter gap on a selected PID.",
                "parameters": ["target_pid", "cc_skip"],
            },
            {
                "id": "corrupt_sync",
                "name": "Corrupt sync byte",
                "description": "Replace the sync byte (0x47) with another value on selected packets.",
                "parameters": ["target_packet_indices", "corrupt_byte"],
            },
            {
                "id": "modify_header",
                "name": "Set transport error indicator",
                "description": "Set the TEI flag on selected packets to simulate error flagging.",
                "parameters": ["target_pid", "target_packet_indices"],
            },
            {
                "id": "change_scrambling",
                "name": "Change scrambling bits",
                "description": "Modify scrambling control bits on a PID. This is a header-bit simulation only.",
                "parameters": ["target_pid", "scrambling_value"],
            },
        ],
    }


@router.get("/simulate/{sim_id}")
async def get_simulation(sim_id: str):
    """Get simulation results."""
    if sim_id not in _state["simulation_results"]:
        raise HTTPException(404, "Simulation not found.")
    
    result = _state["simulation_results"][sim_id]
    mod_summary = _state["sim_analyses"].get(sim_id)

    return {
        "fault_result": result.model_dump(),
        "modified_analysis": mod_summary.model_dump() if mod_summary else None,
    }


def _build_verification(fault_result, original_summary, modified_summary) -> dict:
    """Build verification status comparing expected vs actual findings."""
    if not original_summary:
        return {"status": "inconclusive", "reason": "Original analysis not available."}

    expected = fault_result.expected_diagnostic.lower()
    
    # Check if any new findings match the expected diagnostic
    original_rules = set()
    for f in original_summary.findings:
        original_rules.add(f.rule_id)

    new_findings = []
    for f in modified_summary.findings:
        if f.rule_id not in original_rules or f.severity != Severity.OK:
            new_findings.append(f)

    # Simple keyword matching for verification
    matched = False
    for f in new_findings:
        title_lower = f.title.lower()
        if any(kw in title_lower for kw in ["continuity", "sync", "transport error",
                                              "scrambl", "missing"]):
            if any(kw in expected for kw in ["continuity", "sync", "error",
                                              "scrambl", "missing"]):
                matched = True
                break

    if matched:
        status = "pass"
        reason = "The diagnostic engine independently detected the injected fault."
    elif len(new_findings) > 0:
        status = "pass"
        reason = f"New findings detected: {[f.title for f in new_findings[:3]]}"
    else:
        status = "fail"
        reason = "No new diagnostic findings were produced after fault injection."

    return {
        "status": status,
        "reason": reason,
        "expected": fault_result.expected_diagnostic,
        "new_finding_count": len(new_findings),
        "new_findings": [{"rule_id": f.rule_id, "title": f.title,
                          "severity": f.severity.value} for f in new_findings[:5]],
    }


# ── Reports ────────────────────────────────────────────────────────

@router.get("/reports/{file_id}/summary")
async def download_summary_json(file_id: str):
    """Download analysis summary as JSON."""
    if file_id not in _state["analyses"]:
        raise HTTPException(404, "No analysis found.")
    
    summary = _state["analyses"][file_id]
    content = report_gen.analysis_summary_json(summary)
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=orbitstream_summary_{file_id}.json"},
    )


@router.get("/reports/{file_id}/findings/json")
async def download_findings_json(file_id: str):
    """Download diagnostic findings as JSON."""
    if file_id not in _state["analyses"]:
        raise HTTPException(404, "No analysis found.")
    
    findings = _state["analyses"][file_id].findings
    content = report_gen.findings_json(findings)
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=orbitstream_findings_{file_id}.json"},
    )


@router.get("/reports/{file_id}/findings/csv")
async def download_findings_csv(file_id: str):
    """Download diagnostic findings as CSV."""
    if file_id not in _state["analyses"]:
        raise HTTPException(404, "No analysis found.")
    
    findings = _state["analyses"][file_id].findings
    content = report_gen.findings_csv(findings)
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=orbitstream_findings_{file_id}.csv"},
    )


@router.get("/reports/{file_id}/pids/csv")
async def download_pid_csv(file_id: str):
    """Download PID inventory as CSV."""
    if file_id not in _state["analyses"]:
        raise HTTPException(404, "No analysis found.")
    
    summary = _state["analyses"][file_id]
    content = report_gen.pid_inventory_csv(summary)
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=orbitstream_pids_{file_id}.csv"},
    )


@router.get("/reports/{sim_id}/comparison")
async def download_comparison_json(sim_id: str):
    """Download simulation comparison report."""
    if sim_id not in _state["simulation_results"]:
        raise HTTPException(404, "Simulation not found.")
    
    fault_result = _state["simulation_results"][sim_id]
    mod_summary = _state["sim_analyses"].get(sim_id)
    
    # Find original analysis
    original_summary = None
    # Try to find from fault source file path
    for fid, summary in _state["analyses"].items():
        original_summary = summary
        break  # Use first available analysis

    if not original_summary or not mod_summary:
        raise HTTPException(400, "Both original and modified analyses are required.")

    content = report_gen.simulation_comparison_json(original_summary, mod_summary, fault_result)
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=orbitstream_comparison_{sim_id}.json"},
    )


# ── Health ─────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "active_analyses": len(_state["analyses"]),
    }


# ── Signal Lab (QPSK / 8PSK) ───────────────────────────────────────

@router.post("/signal/simulate")
async def simulate_signal(req: SignalSimulationRequest):
    """
    Simulate QPSK or 8PSK modulation over an AWGN channel with optional
    carrier phase offset and frequency drift.
    Returns constellation points and calculated BER/SER/EVM metrics.
    """
    res = sig_simulator.simulate(req)
    return res.model_dump()


@router.get("/signal/samples")
async def list_signal_samples():
    """List available reproducible synthetic I/Q test files."""
    iq_dir = os.path.join(config.fixtures_dir, "iq_samples")
    fixtures = generate_iq_fixtures(iq_dir)
    samples = []
    descriptions = {
        "qpsk_clean_20db": "QPSK at 20 dB SNR, Float32 LE (Clean reference vector)",
        "8psk_snr_18db": "8PSK at 18 dB SNR, Float32 LE (8-cluster phase distribution)",
        "qpsk_int16_noisy": "QPSK at 8 dB SNR with 15° phase offset, Int16 LE",
    }
    formats = {
        "qpsk_clean_20db": "float32_le",
        "8psk_snr_18db": "float32_le",
        "qpsk_int16_noisy": "int16_le",
    }

    for name, path in fixtures.items():
        if os.path.exists(path):
            samples.append({
                "name": name,
                "filename": os.path.basename(path),
                "file_size": os.path.getsize(path),
                "format": formats.get(name, "float32_le"),
                "description": descriptions.get(name, "Synthetic I/Q test vector"),
            })

    return {"samples": samples}


@router.post("/signal/samples/{sample_name}/analyze")
async def analyze_signal_sample(sample_name: str):
    """Analyze a built-in sample I/Q test file."""
    iq_dir = os.path.join(config.fixtures_dir, "iq_samples")
    fixtures = generate_iq_fixtures(iq_dir)
    if sample_name not in fixtures or not os.path.exists(fixtures[sample_name]):
        raise HTTPException(404, f"Signal sample '{sample_name}' not found.")

    path = fixtures[sample_name]
    sample_format = SampleFormat.INT16_LE if "int16" in sample_name else SampleFormat.FLOAT32_LE

    with open(path, "rb") as f:
        data = f.read()

    try:
        res = iq_analyzer.analyze_bytes(
            data=data,
            sample_format=sample_format,
            filename=os.path.basename(path),
        )
        return res.model_dump()
    except Exception as e:
        raise HTTPException(400, f"Analysis failed: {str(e)}")


@router.post("/signal/upload")
async def upload_and_analyze_iq(
    file: UploadFile = File(...),
    sample_format: SampleFormat = Query(SampleFormat.FLOAT32_LE),
):
    """Upload and analyze a raw I/Q binary file."""
    if not file.filename:
        raise HTTPException(400, "No filename provided.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "Uploaded I/Q file is empty.")

    try:
        res = iq_analyzer.analyze_bytes(
            data=content,
            sample_format=sample_format,
            filename=file.filename,
        )
        return res.model_dump()
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:
        raise HTTPException(500, f"I/Q analysis error: {str(e)}")

