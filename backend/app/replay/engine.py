"""
Packet replay engine for offline navigation through captured TS packets.

Provides indexed access to packets, filtering, and navigation
linked to diagnostic findings.
"""
from __future__ import annotations

from typing import Optional
from ..parsers.mpegts.models import TSPacket, ParseResult


class ReplayEngine:
    """
    Offline packet replay engine.
    
    Provides indexed random access to parsed packets with filtering
    and navigation capabilities.
    """

    def __init__(self, parse_result: ParseResult):
        self._packets = parse_result.packets
        self._total = len(self._packets)
        self._pid_index: dict[int, list[int]] = {}  # PID -> list of positions in self._packets
        self._build_indices()

    def _build_indices(self) -> None:
        """Build lookup indices for fast navigation."""
        for i, pkt in enumerate(self._packets):
            if pkt.pid not in self._pid_index:
                self._pid_index[pkt.pid] = []
            self._pid_index[pkt.pid].append(i)

    @property
    def total_packets(self) -> int:
        return self._total

    @property
    def available_pids(self) -> list[int]:
        return sorted(self._pid_index.keys())

    def get_packet(self, index: int) -> Optional[TSPacket]:
        """Get a packet by its sequential index."""
        if 0 <= index < self._total:
            return self._packets[index]
        return None

    def get_packets_range(self, start: int, count: int = 20) -> list[TSPacket]:
        """Get a range of packets starting from the given index."""
        start = max(0, start)
        end = min(self._total, start + count)
        return self._packets[start:end]

    def get_packets_around(self, center: int, radius: int = 5) -> list[TSPacket]:
        """Get packets around a center index."""
        start = max(0, center - radius)
        end = min(self._total, center + radius + 1)
        return self._packets[start:end]

    def get_packets_by_pid(self, pid: int, offset: int = 0,
                           count: int = 20) -> list[TSPacket]:
        """Get packets filtered by PID."""
        if pid not in self._pid_index:
            return []
        indices = self._pid_index[pid]
        selected = indices[offset:offset + count]
        return [self._packets[i] for i in selected]

    def count_packets_by_pid(self, pid: int) -> int:
        """Count packets for a specific PID."""
        return len(self._pid_index.get(pid, []))

    def find_packet_by_offset(self, byte_offset: int) -> Optional[int]:
        """Find the packet index closest to the given byte offset."""
        # Binary search
        lo, hi = 0, self._total - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._packets[mid].offset == byte_offset:
                return mid
            elif self._packets[mid].offset < byte_offset:
                lo = mid + 1
            else:
                hi = mid - 1
        return lo if lo < self._total else self._total - 1

    def get_packet_header_display(self, packet: TSPacket) -> dict:
        """Get a display-friendly representation of packet header fields."""
        return {
            "index": packet.index,
            "offset": packet.offset,
            "offset_hex": f"0x{packet.offset:08X}",
            "sync_byte": f"0x{packet.sync_byte:02X}",
            "pid": packet.pid,
            "pid_hex": f"0x{packet.pid:04X}",
            "tei": packet.transport_error_indicator,
            "pusi": packet.payload_unit_start_indicator,
            "priority": packet.transport_priority,
            "scrambling": packet.scrambling_control.value,
            "scrambling_name": packet.scrambling_control.name,
            "afc": packet.adaptation_field_control.value,
            "afc_name": packet.adaptation_field_control.name,
            "cc": packet.continuity_counter,
            "has_payload": packet.has_payload,
            "is_valid": packet.is_valid,
            "header_hex": packet.header_hex(),
            "raw_hex": packet.raw_hex(),
        }
