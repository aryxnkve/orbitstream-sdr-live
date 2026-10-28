"""
Report generation for analysis results.

Generates JSON and CSV exports of analysis summaries,
diagnostic findings, PID inventories, and simulation comparisons.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from ..models.diagnostic_models import AnalysisSummary, DiagnosticFinding
from ..parsers.mpegts.models import ParseResult
from ..simulation.engine import FaultResult


class ReportGenerator:
    """Generates downloadable reports from analysis results."""

    REPORT_VERSION = "0.1.0"

    def analysis_summary_json(self, summary: AnalysisSummary) -> str:
        """Generate a JSON analysis summary report."""
        report = {
            "report_type": "analysis_summary",
            "report_version": self.REPORT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file": {
                "name": summary.filename,
                "size_bytes": summary.file_size,
                "detected_format": summary.detected_format,
                "packet_size": summary.packet_size,
            },
            "statistics": {
                "total_packets": summary.total_packets,
                "valid_packets": summary.valid_packets,
                "error_packets": summary.error_packets,
                "null_packets": summary.null_packets,
                "scrambled_packets": summary.scrambled_packets,
                "pid_count": summary.pid_count,
                "program_count": summary.program_count,
            },
            "findings_summary": summary.findings_by_severity,
            "findings": [f.model_dump(exclude={"packet_indices", "byte_offsets"})
                         for f in summary.findings],
            "warnings": summary.warnings,
            "errors": summary.errors,
            "parser_version": summary.parser_version,
        }
        return json.dumps(report, indent=2, default=str)

    def findings_json(self, findings: list[DiagnosticFinding]) -> str:
        """Generate a JSON report of diagnostic findings."""
        report = {
            "report_type": "diagnostic_findings",
            "report_version": self.REPORT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "finding_count": len(findings),
            "findings": [f.model_dump() for f in findings],
        }
        return json.dumps(report, indent=2, default=str)

    def pid_inventory_csv(self, summary: AnalysisSummary) -> str:
        """Generate a CSV of the PID/stream inventory."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "PID", "PID (hex)", "Label", "Stream Type", "Program",
            "Packet Count", "Byte Count", "Errors", "CC Errors",
            "Scrambled", "Status",
        ])
        for pid_data in summary.pids:
            status = "OK"
            if pid_data.get("has_errors"):
                status = "Errors detected"
            elif pid_data.get("is_scrambled"):
                status = "Scrambled"
            writer.writerow([
                pid_data.get("pid", ""),
                pid_data.get("pid_hex", ""),
                pid_data.get("label", ""),
                pid_data.get("stream_type_name", ""),
                pid_data.get("program_number", ""),
                pid_data.get("packet_count", 0),
                pid_data.get("byte_count", 0),
                pid_data.get("error_count", 0),
                pid_data.get("continuity_errors", 0),
                pid_data.get("scrambled_count", 0),
                status,
            ])
        return output.getvalue()

    def findings_csv(self, findings: list[DiagnosticFinding]) -> str:
        """Generate a CSV of diagnostic findings."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Rule", "Severity", "Title", "Explanation",
            "Affected PID", "Certainty", "Expected", "Observed",
        ])
        for f in findings:
            writer.writerow([
                f.id, f.rule_id, f.severity.value, f.title,
                f.explanation, f.affected_pid_hex or "",
                f.certainty.value, f.expected_value or "",
                f.observed_value or "",
            ])
        return output.getvalue()

    def simulation_comparison_json(self, original_summary: AnalysisSummary,
                                   modified_summary: AnalysisSummary,
                                   fault_result: FaultResult) -> str:
        """Generate a comparison report between original and modified analysis."""
        report = {
            "report_type": "simulation_comparison",
            "report_version": self.REPORT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scenario": fault_result.scenario.value,
            "description": fault_result.description,
            "source_hash": fault_result.source_hash,
            "modified_hash": fault_result.modified_hash,
            "modifications": fault_result.modifications,
            "expected_diagnostic": fault_result.expected_diagnostic,
            "original": {
                "total_packets": original_summary.total_packets,
                "error_packets": original_summary.error_packets,
                "findings_count": len(original_summary.findings),
                "findings_by_severity": original_summary.findings_by_severity,
            },
            "modified": {
                "total_packets": modified_summary.total_packets,
                "error_packets": modified_summary.error_packets,
                "findings_count": len(modified_summary.findings),
                "findings_by_severity": modified_summary.findings_by_severity,
            },
            "new_findings": [],
            "resolved_findings": [],
        }

        original_rules = {f.rule_id + (f.affected_pid_hex or "") for f in original_summary.findings}
        modified_rules = {f.rule_id + (f.affected_pid_hex or "") for f in modified_summary.findings}

        for f in modified_summary.findings:
            key = f.rule_id + (f.affected_pid_hex or "")
            if key not in original_rules:
                report["new_findings"].append({
                    "rule_id": f.rule_id,
                    "severity": f.severity.value,
                    "title": f.title,
                    "affected_pid": f.affected_pid_hex,
                })

        for f in original_summary.findings:
            key = f.rule_id + (f.affected_pid_hex or "")
            if key not in modified_rules:
                report["resolved_findings"].append({
                    "rule_id": f.rule_id,
                    "title": f.title,
                })

        return json.dumps(report, indent=2, default=str)
