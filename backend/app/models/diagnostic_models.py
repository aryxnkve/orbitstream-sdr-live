"""
Pydantic models for diagnostic findings and analysis results.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    OK = "ok"


class Certainty(str, Enum):
    CONFIRMED = "confirmed"          # Structural violation proven by data
    OBSERVED = "observed"            # Anomaly detected, cause uncertain
    HEURISTIC = "heuristic"          # Classification based on pattern matching
    POSSIBLE = "possible"            # Plausible but unverified
    UNKNOWN = "unknown"              # Cannot be determined


class DiagnosticFinding(BaseModel):
    """A single diagnostic finding from the analysis engine."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    rule_id: str = Field(description="Identifier of the diagnostic rule that produced this finding")
    severity: Severity
    title: str = Field(description="Short human-readable title")
    explanation: str = Field(description="Plain-language explanation for non-experts")
    technical_detail: str = Field(default="", description="Technical explanation for engineers")
    evidence: dict = Field(default_factory=dict, description="Observed evidence data")
    affected_pid: Optional[int] = None
    affected_pid_hex: str = ""
    affected_stream: str = ""
    packet_indices: list[int] = Field(default_factory=list)
    byte_offsets: list[int] = Field(default_factory=list)
    expected_value: Optional[str] = None
    observed_value: Optional[str] = None
    certainty: Certainty = Certainty.CONFIRMED
    possible_causes: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    """Overall analysis summary combining parser results and diagnostics."""
    file_id: str
    filename: str
    file_size: int
    detected_format: str
    packet_size: int = 188
    total_packets: int = 0
    valid_packets: int = 0
    error_packets: int = 0
    null_packets: int = 0
    scrambled_packets: int = 0
    pid_count: int = 0
    program_count: int = 0
    findings: list[DiagnosticFinding] = []
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    pids: list[dict] = []
    programs: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    parser_version: str = "0.1.0"
    analysis_timestamp: str = ""
    is_synthetic: bool = False
    sync_losses: int = 0
