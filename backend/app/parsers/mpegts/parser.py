"""
MPEG Transport Stream parser.

Parses 188-byte, 192-byte, and 204-byte TS packets according to
ISO/IEC 13818-1 (MPEG-2 Systems).

This parser is deterministic and independently testable.
It does not require network access or external services.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Optional

from .constants import (
    SYNC_BYTE, TS_PACKET_SIZE, TS_PACKET_SIZE_192, TS_PACKET_SIZE_204,
    KNOWN_PACKET_SIZES, PID_PAT, PID_NULL, PID_CAT,
    TABLE_ID_PAT, TABLE_ID_PMT,
    AFC_ADAPTATION_ONLY, AFC_ADAPTATION_AND_PAYLOAD, AFC_PAYLOAD_ONLY,
    SC_NOT_SCRAMBLED, STREAM_TYPES, CC_MAX,
)
from .models import (
    TSPacket, AdaptationField, PIDInfo, PATEntry, PATInfo,
    PMTStream, PMTInfo, ParseResult, StreamFormat,
    AdaptationFieldControl, ScramblingControl,
)
from .crc import crc32_mpeg2, verify_section_crc


class MPEGTSParser:
    """
    Stateful MPEG Transport Stream parser.
    
    Usage:
        parser = MPEGTSParser()
        result = parser.parse_file(file_path)
    """

    # How many bytes to scan when detecting packet size
    SYNC_SCAN_WINDOW = 204 * 20
    # Minimum sync bytes needed to confirm packet size
    MIN_SYNC_CONFIRMS = 5

    def __init__(self, *, store_packets: bool = True, store_payload: bool = False,
                 store_raw: bool = True, max_packets: int = 0):
        """
        Args:
            store_packets: Whether to store all parsed TSPacket objects in results.
            store_payload: Whether to store payload bytes in each packet.
            store_raw: Whether to store raw packet bytes.
            max_packets: Maximum packets to parse (0 = all).
        """
        self.store_packets = store_packets
        self.store_payload = store_payload
        self.store_raw = store_raw
        self.max_packets = max_packets

        # Internal state
        self._packets: list[TSPacket] = []
        self._pid_info: dict[int, PIDInfo] = {}
        self._cc_tracker: dict[int, int] = {}  # PID -> last CC
        self._cc_errors: dict[int, int] = {}   # PID -> error count
        self._pat_sections: dict[int, bytes] = {}  # table section accumulator
        self._pmt_sections: dict[int, bytes] = {}
        self._pat: Optional[PATInfo] = None
        self._pmts: dict[int, PMTInfo] = {}
        self._pmt_pids: set[int] = set()
        self._warnings: list[str] = []
        self._errors: list[str] = []
        self._packet_index = 0
        self._null_count = 0
        self._error_count = 0
        self._scrambled_count = 0
        self._sync_losses = 0

    def parse_file(self, filepath: str) -> ParseResult:
        """Parse a TS file and return structured results."""
        import os
        file_size = os.path.getsize(filepath)
        
        with open(filepath, "rb") as f:
            return self._parse_stream(f, filepath, file_size)

    def parse_bytes(self, data: bytes, filename: str = "buffer") -> ParseResult:
        """Parse TS data from a bytes object."""
        import io
        f = io.BytesIO(data)
        return self._parse_stream(f, filename, len(data))

    def _parse_stream(self, f: BinaryIO, filename: str, file_size: int) -> ParseResult:
        """Core parsing logic."""
        # Step 1: Detect packet size
        packet_size = self._detect_packet_size(f, file_size)
        if packet_size is None:
            return ParseResult(
                filename=filename,
                file_size=file_size,
                detected_format=StreamFormat.UNKNOWN,
                errors=["Could not detect a valid MPEG Transport Stream. "
                        "No consistent 0x47 sync byte pattern found."],
            )

        # Determine format enum
        fmt_map = {
            188: StreamFormat.MPEGTS_188,
            192: StreamFormat.MPEGTS_192,
            204: StreamFormat.MPEGTS_204,
        }
        detected_format = fmt_map.get(packet_size, StreamFormat.UNKNOWN)

        # Step 2: Find first sync byte
        f.seek(0)
        start_offset = self._find_first_sync(f, packet_size)
        if start_offset < 0:
            return ParseResult(
                filename=filename,
                file_size=file_size,
                detected_format=detected_format,
                packet_size=packet_size,
                errors=["Found sync pattern during detection but could not "
                        "locate first sync byte during parsing."],
            )

        if start_offset > 0:
            self._warnings.append(
                f"Skipped {start_offset} bytes before first sync byte."
            )

        # Step 3: Parse packets
        f.seek(start_offset)
        self._parse_packets(f, packet_size, start_offset, file_size)

        # Step 4: Resolve stream types from PMTs
        self._resolve_stream_types()

        # Step 5: Build result
        total_packets = self._packet_index
        valid_packets = total_packets - self._error_count

        # Set hex strings for PID info
        for pid, info in self._pid_info.items():
            info.pid_hex = f"0x{pid:04X}"
            info.continuity_errors = self._cc_errors.get(pid, 0)
            if info.continuity_errors > 0:
                info.has_errors = True
                info.error_count += info.continuity_errors

        return ParseResult(
            filename=filename,
            file_size=file_size,
            detected_format=detected_format,
            packet_size=packet_size,
            total_packets=total_packets,
            valid_packets=valid_packets,
            error_packets=self._error_count,
            null_packets=self._null_count,
            scrambled_packets=self._scrambled_count,
            pids=self._pid_info,
            pat=self._pat,
            pmts=self._pmts,
            packets=self._packets if self.store_packets else [],
            warnings=self._warnings,
            errors=self._errors,
            sync_losses=self._sync_losses,
        )

    def _detect_packet_size(self, f: BinaryIO, file_size: int) -> Optional[int]:
        """
        Detect TS packet size by looking for consistent sync byte patterns.
        Tries 188, 192, and 204 byte spacings.
        """
        f.seek(0)
        scan_size = min(file_size, self.SYNC_SCAN_WINDOW)
        header = f.read(scan_size)
        if len(header) < 188:
            return None

        best_size = None
        best_count = 0

        for pkt_size in KNOWN_PACKET_SIZES:
            # Try multiple starting positions
            min_required = max(1, min(self.MIN_SYNC_CONFIRMS, len(header) // pkt_size))
            for start in range(min(pkt_size, len(header))):
                if header[start] != SYNC_BYTE:
                    continue
                count = 0
                pos = start
                while pos < len(header):
                    if header[pos] == SYNC_BYTE:
                        count += 1
                        pos += pkt_size
                    else:
                        break
                if count > best_count and count >= min_required:
                    best_count = count
                    best_size = pkt_size

        return best_size

    def _find_first_sync(self, f: BinaryIO, packet_size: int) -> int:
        """Find the byte offset of the first confirmed sync byte."""
        f.seek(0)
        data = f.read(min(packet_size * 10, 2048))
        
        for i in range(len(data)):
            if data[i] != SYNC_BYTE:
                continue
            # Verify consecutive sync bytes at this spacing if data allows
            confirmed = True
            num_checks = min(4, (len(data) - i) // packet_size)
            if num_checks > 1:
                for j in range(1, num_checks):
                    if data[i + j * packet_size] != SYNC_BYTE:
                        confirmed = False
                        break
            if confirmed:
                return i
        return -1

    def _parse_packets(self, f: BinaryIO, packet_size: int, start_offset: int,
                       file_size: int) -> None:
        """Parse all TS packets from the stream."""
        # For 192-byte packets, the TS data starts 4 bytes in
        ts_offset_in_packet = 4 if packet_size == 192 else 0

        while True:
            if self.max_packets > 0 and self._packet_index >= self.max_packets:
                break

            current_offset = f.tell()
            raw = f.read(packet_size)
            if len(raw) < packet_size:
                if len(raw) > 0:
                    self._warnings.append(
                        f"Truncated packet at offset {current_offset} "
                        f"({len(raw)} bytes, expected {packet_size})."
                    )
                break

            # Extract the 188-byte TS portion
            ts_data = raw[ts_offset_in_packet:ts_offset_in_packet + 188]

            packet, raw_payload = self._parse_single_packet(ts_data, current_offset, raw)
            
            if packet is None:
                # Sync loss — try to resynchronize
                self._sync_losses += 1
                self._error_count += 1
                resync_offset = self._resync(f, packet_size, current_offset + 1)
                if resync_offset >= 0:
                    self._warnings.append(
                        f"Sync loss at offset {current_offset}, "
                        f"resynchronized at offset {resync_offset}."
                    )
                    f.seek(resync_offset)
                else:
                    self._errors.append(
                        f"Sync loss at offset {current_offset}, "
                        f"could not resynchronize. Stopping parse."
                    )
                    break
                continue

            self._process_packet(packet, raw_payload)
            self._packet_index += 1

    def _parse_single_packet(self, ts_data: bytes, file_offset: int,
                             raw: bytes) -> tuple[Optional[TSPacket], Optional[bytes]]:
        """Parse a single 188-byte TS packet. Returns (None, None) if sync byte is wrong."""
        if len(ts_data) < 4:
            return None, None

        sync = ts_data[0]
        if sync != SYNC_BYTE:
            return None, None

        # Parse the 4-byte header
        header = struct.unpack(">I", ts_data[0:4])[0]
        
        tei = bool(header & 0x00800000)
        pusi = bool(header & 0x00400000)
        tp = bool(header & 0x00200000)
        pid = (header >> 8) & 0x1FFF
        sc = (header >> 6) & 0x03
        afc = (header >> 4) & 0x03
        cc = header & 0x0F

        has_adaptation = afc in (AFC_ADAPTATION_ONLY, AFC_ADAPTATION_AND_PAYLOAD)
        has_payload = afc in (AFC_PAYLOAD_ONLY, AFC_ADAPTATION_AND_PAYLOAD)

        adaptation = None
        payload_start = 4

        # Parse adaptation field
        if has_adaptation:
            if len(ts_data) < 5:
                return TSPacket(
                    index=self._packet_index,
                    offset=file_offset,
                    sync_byte=sync,
                    transport_error_indicator=tei,
                    payload_unit_start_indicator=pusi,
                    transport_priority=tp,
                    pid=pid,
                    scrambling_control=ScramblingControl(sc),
                    adaptation_field_control=AdaptationFieldControl(afc),
                    continuity_counter=cc,
                    has_payload=has_payload,
                    is_valid=False,
                    parse_error="Adaptation field indicated but packet too short",
                    raw_bytes=raw if self.store_raw else None,
                ), None
            
            af_length = ts_data[4]
            payload_start = 5 + af_length

            if af_length > 183:
                return TSPacket(
                    index=self._packet_index,
                    offset=file_offset,
                    sync_byte=sync,
                    transport_error_indicator=tei,
                    payload_unit_start_indicator=pusi,
                    transport_priority=tp,
                    pid=pid,
                    scrambling_control=ScramblingControl(sc),
                    adaptation_field_control=AdaptationFieldControl(afc),
                    continuity_counter=cc,
                    has_payload=has_payload,
                    is_valid=False,
                    parse_error=f"Adaptation field length {af_length} exceeds maximum (183)",
                    raw_bytes=raw if self.store_raw else None,
                ), None

            if af_length > 0:
                adaptation = self._parse_adaptation_field(ts_data[5:5 + af_length], af_length)

        # Extract payload
        payload = None
        if has_payload and payload_start < 188:
            payload = ts_data[payload_start:]

        pkt = TSPacket(
            index=self._packet_index,
            offset=file_offset,
            sync_byte=sync,
            transport_error_indicator=tei,
            payload_unit_start_indicator=pusi,
            transport_priority=tp,
            pid=pid,
            scrambling_control=ScramblingControl(sc),
            adaptation_field_control=AdaptationFieldControl(afc),
            continuity_counter=cc,
            adaptation_field=adaptation,
            payload=payload if self.store_payload else None,
            raw_bytes=raw if self.store_raw else None,
            has_payload=has_payload,
            is_valid=not tei,
            parse_error="Transport error indicator set" if tei else None,
        )

        return pkt, payload

    def _parse_adaptation_field(self, data: bytes, length: int) -> AdaptationField:
        """Parse adaptation field flags and optional fields."""
        af = AdaptationField(length=length)

        if len(data) < 1:
            return af

        flags = data[0]
        af.discontinuity_indicator = bool(flags & 0x80)
        af.random_access_indicator = bool(flags & 0x40)
        af.elementary_stream_priority = bool(flags & 0x20)
        af.pcr_flag = bool(flags & 0x10)
        af.opcr_flag = bool(flags & 0x08)
        af.splicing_point_flag = bool(flags & 0x04)
        af.transport_private_data_flag = bool(flags & 0x02)
        af.extension_flag = bool(flags & 0x01)

        pos = 1

        # Parse PCR (6 bytes)
        if af.pcr_flag and pos + 6 <= len(data):
            pcr_base = (data[pos] << 25) | (data[pos+1] << 17) | \
                       (data[pos+2] << 9) | (data[pos+3] << 1) | \
                       ((data[pos+4] >> 7) & 0x01)
            pcr_ext = ((data[pos+4] & 0x01) << 8) | data[pos+5]
            af.pcr = pcr_base * 300 + pcr_ext
            pos += 6

        # Parse OPCR (6 bytes)
        if af.opcr_flag and pos + 6 <= len(data):
            opcr_base = (data[pos] << 25) | (data[pos+1] << 17) | \
                        (data[pos+2] << 9) | (data[pos+3] << 1) | \
                        ((data[pos+4] >> 7) & 0x01)
            opcr_ext = ((data[pos+4] & 0x01) << 8) | data[pos+5]
            af.opcr = opcr_base * 300 + opcr_ext
            pos += 6

        # Parse splice countdown
        if af.splicing_point_flag and pos + 1 <= len(data):
            af.splice_countdown = struct.unpack("b", data[pos:pos+1])[0]
            pos += 1

        return af

    def _process_packet(self, packet: TSPacket, raw_payload: Optional[bytes] = None) -> None:
        """Process a parsed packet: update stats, check CC, parse tables."""
        pid = packet.pid

        # Update PID info
        if pid not in self._pid_info:
            self._pid_info[pid] = PIDInfo(
                pid=pid,
                first_packet_index=packet.index,
            )
            self._assign_pid_label(pid)

        info = self._pid_info[pid]
        info.packet_count += 1
        info.byte_count += 188
        info.last_packet_index = packet.index

        # Null packets
        if pid == PID_NULL:
            self._null_count += 1

        # Error packets
        if packet.transport_error_indicator:
            self._error_count += 1
            info.has_errors = True
            info.error_count += 1

        # Scrambling
        if packet.scrambling_control != ScramblingControl.NOT_SCRAMBLED:
            self._scrambled_count += 1
            info.scrambled_count += 1
            info.is_scrambled = True

        # Continuity counter check
        if packet.has_payload and pid != PID_NULL:
            self._check_continuity(packet)

        # Store packet
        if self.store_packets:
            self._packets.append(packet)

        # Parse PSI tables
        effective_payload = raw_payload if raw_payload is not None else packet.payload
        if pid == PID_PAT and packet.has_payload and effective_payload:
            self._accumulate_section(packet, self._pat_sections, self._parse_pat, effective_payload)
        elif pid in self._pmt_pids and packet.has_payload and effective_payload:
            self._accumulate_section(packet, self._pmt_sections, self._parse_pmt, effective_payload)

    def _check_continuity(self, packet: TSPacket) -> None:
        """
        Check continuity counter correctness per ISO 13818-1 Section 2.4.3.3.
        
        Rules:
        - CC increments by 1 (mod 16) for each packet with payload on the same PID.
        - Adaptation-only packets (no payload) do not increment CC.
        - Duplicate packets are allowed: same CC value with identical packet content.
        - Discontinuity indicator resets tracking.
        """
        pid = packet.pid
        
        # Skip adaptation-only (no payload) packets for CC tracking
        if not packet.has_payload:
            return

        # Check discontinuity indicator
        if (packet.adaptation_field and 
            packet.adaptation_field.discontinuity_indicator):
            # Discontinuity: reset CC tracking for this PID
            self._cc_tracker[pid] = packet.continuity_counter
            return

        if pid not in self._cc_tracker:
            # First packet on this PID — just record
            self._cc_tracker[pid] = packet.continuity_counter
            return

        expected_cc = (self._cc_tracker[pid] + 1) & 0x0F
        actual_cc = packet.continuity_counter

        if actual_cc == expected_cc:
            # Normal increment
            self._cc_tracker[pid] = actual_cc
        elif actual_cc == self._cc_tracker[pid]:
            # Duplicate packet (same CC) — allowed by spec
            pass
        else:
            # Continuity error
            if pid not in self._cc_errors:
                self._cc_errors[pid] = 0
            self._cc_errors[pid] += 1
            self._cc_tracker[pid] = actual_cc

    def _assign_pid_label(self, pid: int) -> None:
        """Assign a human-readable label to a PID."""
        info = self._pid_info[pid]
        if pid == PID_PAT:
            info.label = "PAT"
        elif pid == PID_CAT:
            info.label = "CAT"
        elif pid == 0x0002:
            info.label = "TSDT"
        elif pid == PID_NULL:
            info.label = "Null"
        elif pid in self._pmt_pids:
            info.label = "PMT"
        elif 0x0010 <= pid <= 0x001F:
            info.label = "DVB SI/PSI"
        else:
            info.label = f"PID {pid}"
        info.pid_hex = f"0x{pid:04X}"

    def _accumulate_section(self, packet: TSPacket, section_store: dict,
                            parse_fn, payload: Optional[bytes] = None) -> None:
        """
        Accumulate PSI section data across packets and parse when complete.
        Simplified: handles single-section-per-packet cases.
        """
        effective_payload = payload if payload is not None else packet.payload
        if not effective_payload:
            return

        p_bytes = effective_payload
        pid = packet.pid

        if packet.payload_unit_start_indicator:
            # Pointer field
            if len(p_bytes) < 1:
                return
            pointer = p_bytes[0]
            section_start = 1 + pointer
            if section_start >= len(p_bytes):
                return
            section_data = p_bytes[section_start:]
            
            # Check if we have a complete section
            if len(section_data) >= 3:
                section_length = ((section_data[1] & 0x0F) << 8) | section_data[2]
                total_needed = 3 + section_length
                
                if len(section_data) >= total_needed:
                    parse_fn(section_data[:total_needed], pid)
                else:
                    # Store partial section
                    section_store[pid] = bytearray(section_data)
            return

        # Continuation
        if pid in section_store:
            section_store[pid].extend(p_bytes)
            section_data = bytes(section_store[pid])
            
            if len(section_data) >= 3:
                section_length = ((section_data[1] & 0x0F) << 8) | section_data[2]
                total_needed = 3 + section_length
                
                if len(section_data) >= total_needed:
                    parse_fn(section_data[:total_needed], pid)
                    del section_store[pid]

    def _parse_pat(self, section: bytes, pid: int) -> None:
        """Parse a Program Association Table section."""
        if len(section) < 8:
            self._warnings.append("PAT section too short to parse.")
            return

        table_id = section[0]
        if table_id != TABLE_ID_PAT:
            self._warnings.append(
                f"Expected PAT table_id 0x00, got 0x{table_id:02X}."
            )
            return

        section_length = ((section[1] & 0x0F) << 8) | section[2]
        if section_length < 5:
            self._warnings.append("PAT section_length too small.")
            return

        total_section = 3 + section_length
        if len(section) < total_section:
            self._warnings.append("PAT section data shorter than declared length.")
            return

        # CRC check
        crc_valid = verify_section_crc(section[:total_section])

        ts_id = (section[3] << 8) | section[4]
        version = (section[5] >> 1) & 0x1F
        current_next = bool(section[5] & 0x01)
        # section_number = section[6]
        # last_section_number = section[7]

        entries: list[PATEntry] = []
        entry_data = section[8:total_section - 4]  # Exclude CRC

        for i in range(0, len(entry_data) - 3, 4):
            prog_num = (entry_data[i] << 8) | entry_data[i + 1]
            entry_pid = ((entry_data[i + 2] & 0x1F) << 8) | entry_data[i + 3]

            is_nit = prog_num == 0
            entry = PATEntry(
                program_number=prog_num,
                pid=entry_pid,
                pid_hex=f"0x{entry_pid:04X}",
                is_network_pid=is_nit,
            )
            entries.append(entry)

            if not is_nit:
                self._pmt_pids.add(entry_pid)
                # Update PID labels
                if entry_pid in self._pid_info:
                    self._pid_info[entry_pid].label = f"PMT (Program {prog_num})"
                    self._pid_info[entry_pid].program_number = prog_num

        self._pat = PATInfo(
            transport_stream_id=ts_id,
            version_number=version,
            current_next=current_next,
            entries=entries,
            crc_valid=crc_valid,
            raw_section_length=section_length,
        )

        if not crc_valid:
            self._warnings.append("PAT CRC-32 check failed.")

    def _parse_pmt(self, section: bytes, pid: int) -> None:
        """Parse a Program Map Table section."""
        if len(section) < 12:
            self._warnings.append(f"PMT section on PID 0x{pid:04X} too short.")
            return

        table_id = section[0]
        if table_id != TABLE_ID_PMT:
            return

        section_length = ((section[1] & 0x0F) << 8) | section[2]
        total_section = 3 + section_length
        if len(section) < total_section:
            self._warnings.append(
                f"PMT section data shorter than declared length on PID 0x{pid:04X}."
            )
            return

        crc_valid = verify_section_crc(section[:total_section])

        program_number = (section[3] << 8) | section[4]
        version = (section[5] >> 1) & 0x1F
        current_next = bool(section[5] & 0x01)
        pcr_pid = ((section[8] & 0x1F) << 8) | section[9]
        program_info_length = ((section[10] & 0x0F) << 8) | section[11]

        streams: list[PMTStream] = []
        es_start = 12 + program_info_length
        es_end = total_section - 4  # Exclude CRC

        pos = es_start
        while pos + 5 <= es_end:
            stream_type = section[pos]
            elementary_pid = ((section[pos + 1] & 0x1F) << 8) | section[pos + 2]
            es_info_len = ((section[pos + 3] & 0x0F) << 8) | section[pos + 4]

            stream_type_name = STREAM_TYPES.get(stream_type, f"Unknown (0x{stream_type:02X})")

            stream = PMTStream(
                stream_type=stream_type,
                stream_type_name=stream_type_name,
                elementary_pid=elementary_pid,
                elementary_pid_hex=f"0x{elementary_pid:04X}",
                es_info_length=es_info_len,
            )
            streams.append(stream)

            # Update PID info
            if elementary_pid in self._pid_info:
                self._pid_info[elementary_pid].stream_type = stream_type
                self._pid_info[elementary_pid].stream_type_name = stream_type_name
                self._pid_info[elementary_pid].program_number = program_number
                self._pid_info[elementary_pid].label = stream_type_name
            
            pos += 5 + es_info_len

        pmt = PMTInfo(
            program_number=program_number,
            version_number=version,
            current_next=current_next,
            pcr_pid=pcr_pid,
            pcr_pid_hex=f"0x{pcr_pid:04X}",
            program_info_length=program_info_length,
            streams=streams,
            crc_valid=crc_valid,
            raw_section_length=section_length,
        )

        self._pmts[program_number] = pmt

        if not crc_valid:
            self._warnings.append(
                f"PMT CRC-32 check failed for program {program_number}."
            )

    def _resolve_stream_types(self) -> None:
        """Update PID labels and stream types from parsed PMTs."""
        for prog_num, pmt in self._pmts.items():
            for stream in pmt.streams:
                pid = stream.elementary_pid
                if pid in self._pid_info:
                    info = self._pid_info[pid]
                    if not info.stream_type:
                        info.stream_type = stream.stream_type
                        info.stream_type_name = stream.stream_type_name
                        info.program_number = prog_num
                        info.label = stream.stream_type_name

    def _resync(self, f: BinaryIO, packet_size: int, start_pos: int) -> int:
        """
        Attempt to resynchronize after a sync loss.
        Returns the file offset of the next valid sync byte, or -1.
        """
        f.seek(start_pos)
        scan = f.read(packet_size * 10)
        
        for i in range(len(scan)):
            if scan[i] != SYNC_BYTE:
                continue
            # Verify 3 consecutive sync bytes
            ok = True
            for j in range(1, min(4, (len(scan) - i) // packet_size)):
                if i + j * packet_size >= len(scan):
                    break
                if scan[i + j * packet_size] != SYNC_BYTE:
                    ok = False
                    break
            if ok:
                return start_pos + i
        return -1
