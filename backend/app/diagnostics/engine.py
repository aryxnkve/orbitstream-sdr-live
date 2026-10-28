"""
Evidence-based diagnostic engine for MPEG Transport Streams.

Consumes parser results and produces structured diagnostic findings.
Each finding is linked to actual evidence from the analyzed file.

This is a deterministic rule engine — no AI/ML required.
"""
from __future__ import annotations

from typing import Optional
from ..parsers.mpegts.models import ParseResult, PIDInfo, StreamFormat
from ..parsers.mpegts.constants import PID_NULL, PID_PAT
from ..models.diagnostic_models import (
    DiagnosticFinding, Severity, Certainty,
)


class DiagnosticEngine:
    """
    Rule-based diagnostic engine.
    
    Runs a set of diagnostic rules against parser results and
    returns a list of findings ordered by severity.
    """

    RULES_VERSION = "0.1.0"

    def __init__(self):
        self._rules = [
            self._rule_no_sync,
            self._rule_transport_errors,
            self._rule_continuity_errors,
            self._rule_sync_losses,
            self._rule_missing_pat,
            self._rule_pat_crc_failure,
            self._rule_pmt_crc_failure,
            self._rule_high_null_ratio,
            self._rule_scrambled_streams,
            self._rule_single_pid,
            self._rule_no_programs,
            self._rule_truncated_warnings,
            self._rule_stream_health,
        ]

    def analyze(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Run all rules and return findings sorted by severity."""
        findings = []
        for rule in self._rules:
            rule_findings = rule(result)
            if rule_findings:
                findings.extend(rule_findings)

        # Sort: critical first, then warning, info, ok
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.WARNING: 1,
            Severity.INFO: 2,
            Severity.OK: 3,
        }
        findings.sort(key=lambda f: severity_order.get(f.severity, 99))
        return findings

    # ── Rules ──────────────────────────────────────────────────────

    def _rule_no_sync(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Check if the file could not be parsed at all."""
        if result.detected_format == StreamFormat.UNKNOWN:
            return [DiagnosticFinding(
                rule_id="DIAG-001",
                severity=Severity.CRITICAL,
                title="Unrecognized stream format",
                explanation=(
                    "This file does not appear to be a valid MPEG Transport Stream. "
                    "No consistent sync byte pattern (0x47) was found."
                ),
                technical_detail=(
                    "The parser scanned the first bytes of the file for repeating "
                    "0x47 sync bytes at 188, 192, or 204 byte intervals. "
                    "No consistent pattern was detected."
                ),
                certainty=Certainty.CONFIRMED,
                evidence={"file_size": result.file_size},
                possible_causes=[
                    "The file is not an MPEG-TS capture.",
                    "The file uses a container format not yet supported (GSE, BBFrame, PCAP).",
                    "The file is corrupted beyond recognition.",
                    "The file is empty or too short.",
                ],
                recommended_steps=[
                    "Verify the file was saved correctly from the receiver.",
                    "Check the file extension and expected format.",
                    "Try opening the file with a hex editor to inspect its structure.",
                ],
            )]
        return []

    def _rule_transport_errors(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Check for packets with the Transport Error Indicator set."""
        findings = []
        for pid, info in result.pids.items():
            if info.error_count > 0:
                # Find packet indices with TEI set
                tei_indices = []
                tei_offsets = []
                for pkt in result.packets:
                    if pkt.pid == pid and pkt.transport_error_indicator:
                        tei_indices.append(pkt.index)
                        tei_offsets.append(pkt.offset)
                        if len(tei_indices) >= 20:  # Cap evidence list
                            break

                findings.append(DiagnosticFinding(
                    rule_id="DIAG-010",
                    severity=Severity.WARNING,
                    title=f"Transport errors on PID {info.pid_hex}",
                    explanation=(
                        f"{info.error_count} packet(s) on PID {info.pid_hex} "
                        f"({info.label}) have the Transport Error Indicator (TEI) set. "
                        f"This flag is typically set by upstream equipment when "
                        f"uncorrectable errors are detected."
                    ),
                    technical_detail=(
                        f"TEI bit (bit 15 of TS header) is set in {info.error_count} "
                        f"packets. The receiver or demodulator flagged these packets "
                        f"as containing uncorrectable errors before recording."
                    ),
                    affected_pid=pid,
                    affected_pid_hex=info.pid_hex,
                    affected_stream=info.label,
                    packet_indices=tei_indices,
                    byte_offsets=tei_offsets,
                    evidence={
                        "error_count": info.error_count,
                        "total_packets_on_pid": info.packet_count,
                        "error_rate": round(info.error_count / max(info.packet_count, 1), 4),
                    },
                    certainty=Certainty.CONFIRMED,
                    possible_causes=[
                        "Signal degradation or low carrier-to-noise ratio.",
                        "Antenna misalignment.",
                        "Interference or adjacent channel issues.",
                        "Equipment malfunction in the signal chain.",
                        "Errors introduced during file capture or transfer.",
                    ],
                    recommended_steps=[
                        "Inspect the affected packets in the packet replay view.",
                        "Check if errors cluster in time (consecutive packets) or are scattered.",
                        "Review signal quality metrics from the receiver if available.",
                    ],
                ))
        return findings

    def _rule_continuity_errors(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Check for continuity counter discontinuities."""
        findings = []
        
        # Rebuild CC tracking to find exact error locations
        cc_tracker: dict[int, int] = {}
        
        for pkt in result.packets:
            pid = pkt.pid
            if not pkt.has_payload or pid == PID_NULL:
                continue
            
            if pkt.adaptation_field and pkt.adaptation_field.discontinuity_indicator:
                cc_tracker[pid] = pkt.continuity_counter
                continue

            if pid not in cc_tracker:
                cc_tracker[pid] = pkt.continuity_counter
                continue

            expected = (cc_tracker[pid] + 1) & 0x0F
            actual = pkt.continuity_counter

            if actual != expected and actual != cc_tracker[pid]:
                # This is a CC error — record it
                info = result.pids.get(pid)
                pid_hex = f"0x{pid:04X}"
                label = info.label if info else f"PID {pid}"
                
                gap = (actual - expected) & 0x0F
                
                findings.append(DiagnosticFinding(
                    rule_id="DIAG-020",
                    severity=Severity.WARNING,
                    title=f"Continuity counter discontinuity on PID {pid_hex}",
                    explanation=(
                        f"The continuity counter on PID {pid_hex} ({label}) "
                        f"jumped from {cc_tracker[pid]} to {actual} at packet {pkt.index}. "
                        f"Expected {expected}. This suggests {gap} packet(s) may be missing."
                    ),
                    technical_detail=(
                        f"ISO 13818-1 requires the CC to increment by 1 (mod 16) "
                        f"for each packet with payload on the same PID. "
                        f"Previous CC={cc_tracker[pid]}, expected next={expected}, "
                        f"actual={actual}. Gap={gap} packets."
                    ),
                    affected_pid=pid,
                    affected_pid_hex=pid_hex,
                    affected_stream=label,
                    packet_indices=[pkt.index],
                    byte_offsets=[pkt.offset],
                    expected_value=str(expected),
                    observed_value=str(actual),
                    evidence={
                        "previous_cc": cc_tracker[pid],
                        "expected_cc": expected,
                        "actual_cc": actual,
                        "gap_packets": gap,
                        "packet_index": pkt.index,
                        "byte_offset": pkt.offset,
                    },
                    certainty=Certainty.OBSERVED,
                    possible_causes=[
                        "Packet loss during satellite transmission.",
                        "Receiver buffer overflow or processing gap.",
                        "Capture file was trimmed or concatenated.",
                        "Source discontinuity (channel change, stream restart).",
                        "Recording started or stopped mid-stream.",
                    ],
                    recommended_steps=[
                        "Use packet replay to inspect packets around the discontinuity.",
                        "Check if the gap affects video/audio playback.",
                        "Look for correlating transport errors on the same or nearby PIDs.",
                    ],
                    limitations=[
                        "The CC field wraps at 15, so a gap of N could also be 16-N "
                        "packets lost (ambiguous for gaps > 8).",
                        "If the capture begins mid-stream, the first CC value may "
                        "appear discontinuous but is expected.",
                    ],
                ))

            cc_tracker[pid] = actual

        return findings

    def _rule_sync_losses(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Report sync byte losses."""
        if result.sync_losses > 0:
            return [DiagnosticFinding(
                rule_id="DIAG-030",
                severity=Severity.CRITICAL if result.sync_losses > 5 else Severity.WARNING,
                title=f"Sync byte loss detected ({result.sync_losses} occurrence(s))",
                explanation=(
                    f"The parser lost synchronization {result.sync_losses} time(s). "
                    f"This means one or more packet boundaries had an unexpected byte "
                    f"where the sync byte (0x47) was expected."
                ),
                technical_detail=(
                    f"Sync losses: {result.sync_losses}. The parser attempted "
                    f"resynchronization by scanning for the next valid 0x47 pattern."
                ),
                evidence={
                    "sync_losses": result.sync_losses,
                    "total_packets": result.total_packets,
                },
                certainty=Certainty.CONFIRMED,
                possible_causes=[
                    "Corrupted bytes in the capture file.",
                    "File was not captured as a raw TS stream.",
                    "Byte-level corruption during file transfer.",
                    "Mixed packet sizes in a single file.",
                ],
                recommended_steps=[
                    "Check the file integrity (compare checksums if available).",
                    "Inspect the corrupted region with a hex editor.",
                    "Re-capture the stream if possible.",
                ],
            )]
        return []

    def _rule_missing_pat(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Check if PAT was found."""
        if result.detected_format == StreamFormat.UNKNOWN:
            return []
        if result.pat is None:
            return [DiagnosticFinding(
                rule_id="DIAG-040",
                severity=Severity.INFO,
                title="No Program Association Table (PAT) found",
                explanation=(
                    "The file does not contain a PAT, so program and stream "
                    "identification is limited. PIDs are still listed, but stream "
                    "types cannot be determined from signaling data."
                ),
                technical_detail=(
                    "PAT is expected on PID 0x0000. Either no packets on PID 0 "
                    "were found, or the section data was incomplete/invalid."
                ),
                certainty=Certainty.CONFIRMED,
                evidence={
                    "pat_pid_packets": result.pids.get(PID_PAT, PIDInfo(pid=0)).packet_count,
                },
                possible_causes=[
                    "The capture started after the last PAT was transmitted.",
                    "PAT is transmitted infrequently and was not in this capture window.",
                    "The file contains only a subset of the original stream.",
                ],
                recommended_steps=[
                    "Check PID 0x0000 in the stream inventory.",
                    "Try capturing a longer segment of the stream.",
                ],
            )]
        return []

    def _rule_pat_crc_failure(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Report PAT CRC failures."""
        if result.pat and result.pat.crc_valid is False:
            return [DiagnosticFinding(
                rule_id="DIAG-041",
                severity=Severity.WARNING,
                title="PAT CRC-32 check failed",
                explanation=(
                    "The Program Association Table has an invalid CRC. "
                    "The program mappings shown may be incorrect."
                ),
                technical_detail=(
                    "CRC-32/MPEG-2 verification of the PAT section returned "
                    "a non-zero remainder, indicating data corruption."
                ),
                certainty=Certainty.CONFIRMED,
                possible_causes=[
                    "Bit errors in the PAT section.",
                    "Truncated or incomplete PAT data.",
                ],
            )]
        return []

    def _rule_pmt_crc_failure(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Report PMT CRC failures."""
        findings = []
        for prog, pmt in result.pmts.items():
            if pmt.crc_valid is False:
                findings.append(DiagnosticFinding(
                    rule_id="DIAG-042",
                    severity=Severity.WARNING,
                    title=f"PMT CRC-32 check failed (Program {prog})",
                    explanation=(
                        f"The Program Map Table for program {prog} has an invalid CRC. "
                        f"Stream type identification for this program may be incorrect."
                    ),
                    certainty=Certainty.CONFIRMED,
                ))
        return findings

    def _rule_high_null_ratio(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Report if null packet ratio is unusually high."""
        if result.total_packets < 10:
            return []
        null_ratio = result.null_packets / result.total_packets
        if null_ratio > 0.5:
            return [DiagnosticFinding(
                rule_id="DIAG-050",
                severity=Severity.INFO,
                title=f"High null packet ratio ({null_ratio:.0%})",
                explanation=(
                    f"{result.null_packets} of {result.total_packets} packets "
                    f"({null_ratio:.0%}) are null stuffing packets (PID 0x1FFF). "
                    f"This suggests the stream has significant unused bandwidth."
                ),
                evidence={
                    "null_packets": result.null_packets,
                    "total_packets": result.total_packets,
                    "null_ratio": round(null_ratio, 4),
                },
                certainty=Certainty.CONFIRMED,
            )]
        return []

    def _rule_scrambled_streams(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Report scrambled streams."""
        findings = []
        for pid, info in result.pids.items():
            if info.scrambled_count > 0:
                findings.append(DiagnosticFinding(
                    rule_id="DIAG-060",
                    severity=Severity.INFO,
                    title=f"Scrambled packets on PID {info.pid_hex}",
                    explanation=(
                        f"{info.scrambled_count} of {info.packet_count} packets "
                        f"on PID {info.pid_hex} ({info.label}) have scrambling "
                        f"control bits set. This content may be encrypted."
                    ),
                    affected_pid=pid,
                    affected_pid_hex=info.pid_hex,
                    affected_stream=info.label,
                    evidence={
                        "scrambled_count": info.scrambled_count,
                        "total_on_pid": info.packet_count,
                    },
                    certainty=Certainty.CONFIRMED,
                    limitations=[
                        "This tool does not decrypt scrambled content.",
                        "Scrambling bits indicate header-level flags only.",
                    ],
                ))
        return findings

    def _rule_single_pid(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Note if only one PID exists (excluding null)."""
        non_null_pids = [p for p in result.pids if p != PID_NULL]
        if len(non_null_pids) == 1:
            pid = non_null_pids[0]
            return [DiagnosticFinding(
                rule_id="DIAG-070",
                severity=Severity.INFO,
                title="Single PID stream",
                explanation=(
                    f"Only one PID ({result.pids[pid].pid_hex}) carries data. "
                    f"This may be a single elementary stream capture."
                ),
                affected_pid=pid,
                certainty=Certainty.OBSERVED,
            )]
        return []

    def _rule_no_programs(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Note if PAT exists but no programs were found."""
        if result.pat and len(result.pat.entries) == 0:
            return [DiagnosticFinding(
                rule_id="DIAG-071",
                severity=Severity.INFO,
                title="PAT contains no program entries",
                explanation=(
                    "The Program Association Table was parsed but contains no "
                    "program entries. This is unusual for a normal broadcast stream."
                ),
                certainty=Certainty.CONFIRMED,
            )]
        return []

    def _rule_truncated_warnings(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Surface truncation warnings from the parser."""
        findings = []
        for warning in result.warnings:
            if "truncat" in warning.lower():
                findings.append(DiagnosticFinding(
                    rule_id="DIAG-080",
                    severity=Severity.INFO,
                    title="Truncated data detected",
                    explanation=warning,
                    certainty=Certainty.CONFIRMED,
                    possible_causes=[
                        "The file was not captured completely.",
                        "The recording was interrupted.",
                    ],
                ))
        return findings

    def _rule_stream_health(self, result: ParseResult) -> list[DiagnosticFinding]:
        """Provide an overall health assessment if no major issues found."""
        if (result.error_packets == 0 and result.sync_losses == 0 and
            result.total_packets > 0 and result.detected_format != StreamFormat.UNKNOWN):
            
            # Check CC errors
            total_cc_errors = sum(
                info.continuity_errors for info in result.pids.values()
            )
            if total_cc_errors == 0:
                return [DiagnosticFinding(
                    rule_id="DIAG-100",
                    severity=Severity.OK,
                    title="Stream appears healthy",
                    explanation=(
                        f"No transport errors, sync losses, or continuity counter "
                        f"issues were detected across {result.total_packets} packets."
                    ),
                    evidence={
                        "total_packets": result.total_packets,
                        "pid_count": len(result.pids),
                        "error_packets": 0,
                        "sync_losses": 0,
                        "cc_errors": 0,
                    },
                    certainty=Certainty.OBSERVED,
                    limitations=[
                        "This assessment is based on packet-level analysis only.",
                        "Content-level issues (codec errors, PES problems) are not checked.",
                        "Short captures may not reveal intermittent problems.",
                    ],
                )]
        return []
