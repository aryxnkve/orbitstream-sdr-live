"""
Synthetic MPEG-TS test fixture generator.

Generates small, documented .ts files for testing the parser,
diagnostic engine, replay, and simulation features.

All fixtures are synthetic — they do not contain real satellite captures.
"""
from __future__ import annotations

import os
import struct
from .mpegts.crc import crc32_mpeg2
from .mpegts.constants import SYNC_BYTE, PID_PAT, PID_NULL


def _make_ts_packet(pid: int, cc: int, payload: bytes = b"",
                    pusi: bool = False, tei: bool = False,
                    scrambling: int = 0, adaptation: bytes | None = None,
                    sync_byte: int = SYNC_BYTE) -> bytes:
    """
    Build a single 188-byte TS packet.
    
    Args:
        pid: 13-bit PID value.
        cc: 4-bit continuity counter.
        payload: Payload bytes (will be padded with 0xFF to fill packet).
        pusi: Payload unit start indicator.
        tei: Transport error indicator.
        scrambling: 2-bit scrambling control.
        adaptation: Raw adaptation field bytes (excluding length byte).
        sync_byte: Override sync byte (for corruption tests).
    """
    # Header byte 1: sync
    b0 = sync_byte

    # Header bytes 2-3: TEI, PUSI, TP, PID
    b1 = (pid >> 8) & 0x1F
    if tei:
        b1 |= 0x80
    if pusi:
        b1 |= 0x40
    b2 = pid & 0xFF

    # Header byte 4: scrambling, AFC, CC
    has_adaptation = adaptation is not None
    has_payload = len(payload) > 0 or not has_adaptation

    if has_adaptation and has_payload:
        afc = 0b11
    elif has_adaptation:
        afc = 0b10
    else:
        afc = 0b01

    b3 = ((scrambling & 0x03) << 6) | ((afc & 0x03) << 4) | (cc & 0x0F)

    header = bytes([b0, b1, b2, b3])

    if has_adaptation:
        af_data = bytes([len(adaptation)]) + adaptation
    else:
        af_data = b""

    content = header + af_data + payload
    
    # Pad to 188 bytes with 0xFF (stuffing)
    if len(content) < 188:
        content += b"\xFF" * (188 - len(content))
    elif len(content) > 188:
        content = content[:188]

    return content


def _build_pat_section(transport_stream_id: int,
                       programs: list[tuple[int, int]]) -> bytes:
    """
    Build a PAT section with valid CRC.
    
    Args:
        transport_stream_id: 16-bit TS ID.
        programs: List of (program_number, pmt_pid) tuples.
    """
    table_id = 0x00

    # Build section body (after the 3-byte header)
    body = struct.pack(">H", transport_stream_id)
    # Version 0, current, section 0 of 0
    body += bytes([0b11000001, 0x00, 0x00])

    for prog_num, pmt_pid in programs:
        body += struct.pack(">H", prog_num)
        body += struct.pack(">H", 0xE000 | (pmt_pid & 0x1FFF))

    # section_length includes body + CRC (4 bytes)
    section_length = len(body) + 4

    header = bytes([table_id])
    header += struct.pack(">H", 0xB000 | (section_length & 0x0FFF))

    section_without_crc = header + body
    crc = crc32_mpeg2(section_without_crc)
    section = section_without_crc + struct.pack(">I", crc)

    return section


def _build_pmt_section(program_number: int, pcr_pid: int,
                       streams: list[tuple[int, int]]) -> bytes:
    """
    Build a PMT section with valid CRC.
    
    Args:
        program_number: 16-bit program number.
        pcr_pid: PID carrying PCR for this program.
        streams: List of (stream_type, elementary_pid) tuples.
    """
    table_id = 0x02

    body = struct.pack(">H", program_number)
    # Version 0, current, section 0 of 0
    body += bytes([0b11000001, 0x00, 0x00])
    # PCR PID
    body += struct.pack(">H", 0xE000 | (pcr_pid & 0x1FFF))
    # Program info length = 0
    body += struct.pack(">H", 0xF000)

    for stream_type, es_pid in streams:
        body += bytes([stream_type])
        body += struct.pack(">H", 0xE000 | (es_pid & 0x1FFF))
        # ES info length = 0
        body += struct.pack(">H", 0xF000)

    section_length = len(body) + 4
    header = bytes([table_id])
    header += struct.pack(">H", 0xB000 | (section_length & 0x0FFF))

    section_without_crc = header + body
    crc = crc32_mpeg2(section_without_crc)
    section = section_without_crc + struct.pack(">I", crc)

    return section


def generate_valid_ts(output_path: str) -> str:
    """
    Generate a valid MPEG-TS file with PAT, PMT, video, audio, and null packets.
    
    Structure:
    - Program 1: Video on PID 0x0100 (H.264), Audio on PID 0x0101 (AAC)
    - PMT on PID 0x1000
    - 200 total packets
    """
    packets = []
    cc = {}  # PID -> CC

    def next_cc(pid: int) -> int:
        val = cc.get(pid, 0)
        cc[pid] = (val + 1) & 0x0F
        return val

    # PAT packet
    pat_section = _build_pat_section(
        transport_stream_id=1,
        programs=[(1, 0x1000)],
    )
    pat_payload = bytes([0x00]) + pat_section  # pointer_field = 0
    packets.append(_make_ts_packet(PID_PAT, next_cc(PID_PAT), pat_payload, pusi=True))

    # PMT packet
    pmt_section = _build_pmt_section(
        program_number=1,
        pcr_pid=0x0100,
        streams=[
            (0x1B, 0x0100),  # H.264 video
            (0x0F, 0x0101),  # AAC audio
        ],
    )
    pmt_payload = bytes([0x00]) + pmt_section
    packets.append(_make_ts_packet(0x1000, next_cc(0x1000), pmt_payload, pusi=True))

    # Video and audio packets
    for i in range(150):
        # Video packet
        vid_payload = bytes([0x00, 0x00, 0x01, 0xE0]) + bytes(range(180))
        vid_payload = vid_payload[:184]
        packets.append(_make_ts_packet(0x0100, next_cc(0x0100), vid_payload,
                                       pusi=(i % 20 == 0)))

        # Audio packet (every other iteration)
        if i % 2 == 0:
            aud_payload = bytes([0x00, 0x00, 0x01, 0xC0]) + bytes(range(180))
            aud_payload = aud_payload[:184]
            packets.append(_make_ts_packet(0x0101, next_cc(0x0101), aud_payload,
                                           pusi=(i % 30 == 0)))

    # Null packets
    for _ in range(20):
        packets.append(_make_ts_packet(PID_NULL, next_cc(PID_NULL)))

    data = b"".join(packets)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def generate_multi_program_ts(output_path: str) -> str:
    """
    Generate a TS file with multiple programs.
    
    Programs:
    - Program 1: PMT 0x1000, Video 0x0100, Audio 0x0101
    - Program 2: PMT 0x1001, Video 0x0200, Audio 0x0201
    """
    packets = []
    cc = {}

    def next_cc(pid: int) -> int:
        val = cc.get(pid, 0)
        cc[pid] = (val + 1) & 0x0F
        return val

    # PAT
    pat_section = _build_pat_section(
        transport_stream_id=2,
        programs=[(1, 0x1000), (2, 0x1001)],
    )
    pat_payload = bytes([0x00]) + pat_section
    packets.append(_make_ts_packet(PID_PAT, next_cc(PID_PAT), pat_payload, pusi=True))

    # PMT 1
    pmt1 = _build_pmt_section(1, 0x0100, [(0x1B, 0x0100), (0x0F, 0x0101)])
    packets.append(_make_ts_packet(0x1000, next_cc(0x1000),
                                   bytes([0x00]) + pmt1, pusi=True))

    # PMT 2
    pmt2 = _build_pmt_section(2, 0x0200, [(0x02, 0x0200), (0x03, 0x0201)])
    packets.append(_make_ts_packet(0x1001, next_cc(0x1001),
                                   bytes([0x00]) + pmt2, pusi=True))

    # Data packets
    for i in range(100):
        for pid in [0x0100, 0x0101, 0x0200, 0x0201]:
            payload = bytes([pid & 0xFF, i & 0xFF]) + b"\x00" * 182
            packets.append(_make_ts_packet(pid, next_cc(pid), payload))

    data = b"".join(packets)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def generate_cc_error_ts(output_path: str) -> str:
    """
    Generate a TS file with deliberate continuity counter errors on PID 0x0100.
    
    The CC sequence for PID 0x0100 will have a gap: 0,1,2,3,4, 7,8,...
    (packets with CC 5 and 6 are missing).
    """
    packets = []
    cc = {}

    def next_cc(pid: int) -> int:
        val = cc.get(pid, 0)
        cc[pid] = (val + 1) & 0x0F
        return val

    # PAT
    pat_section = _build_pat_section(1, [(1, 0x1000)])
    packets.append(_make_ts_packet(PID_PAT, next_cc(PID_PAT),
                                   bytes([0x00]) + pat_section, pusi=True))

    # PMT
    pmt_section = _build_pmt_section(1, 0x0100, [(0x1B, 0x0100)])
    packets.append(_make_ts_packet(0x1000, next_cc(0x1000),
                                   bytes([0x00]) + pmt_section, pusi=True))

    # Video packets with CC error
    for i in range(50):
        video_cc = next_cc(0x0100)
        # Skip CC 5 and 6 to create gap
        if video_cc == 5:
            cc[0x0100] = 7  # Jump to 7
            video_cc = next_cc(0x0100)
        
        payload = bytes([0xE0, i & 0xFF]) + b"\x00" * 182
        packets.append(_make_ts_packet(0x0100, video_cc, payload))

    data = b"".join(packets)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def generate_corrupt_sync_ts(output_path: str) -> str:
    """
    Generate a TS file with a corrupted sync byte at packet index 5.
    """
    packets = []
    cc = {}

    def next_cc(pid: int) -> int:
        val = cc.get(pid, 0)
        cc[pid] = (val + 1) & 0x0F
        return val

    # PAT
    pat_section = _build_pat_section(1, [(1, 0x1000)])
    packets.append(_make_ts_packet(PID_PAT, next_cc(PID_PAT),
                                   bytes([0x00]) + pat_section, pusi=True))

    for i in range(29):
        pid = 0x0100
        payload = bytes([i & 0xFF]) + b"\x00" * 183
        if i == 4:  # Packet index 5 (0-based: PAT + 4 data packets)
            packets.append(_make_ts_packet(pid, next_cc(pid), payload,
                                           sync_byte=0x00))  # Corrupt!
        else:
            packets.append(_make_ts_packet(pid, next_cc(pid), payload))

    data = b"".join(packets)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def generate_truncated_ts(output_path: str) -> str:
    """
    Generate a TS file with a truncated final packet (100 bytes instead of 188).
    """
    packets = []
    cc = {}

    def next_cc(pid: int) -> int:
        val = cc.get(pid, 0)
        cc[pid] = (val + 1) & 0x0F
        return val

    for i in range(20):
        payload = bytes([i & 0xFF]) + b"\x00" * 183
        packets.append(_make_ts_packet(0x0100, next_cc(0x0100), payload))

    data = b"".join(packets)
    # Truncate last packet
    data = data[:-88]  # Remove last 88 bytes (leaves 100 bytes of last packet)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def generate_all_fixtures(fixture_dir: str) -> dict[str, str]:
    """Generate all test fixtures and return a map of name -> path."""
    fixtures = {}
    
    fixtures["valid_basic"] = generate_valid_ts(
        os.path.join(fixture_dir, "valid_basic.ts")
    )
    fixtures["multi_program"] = generate_multi_program_ts(
        os.path.join(fixture_dir, "multi_program.ts")
    )
    fixtures["cc_error"] = generate_cc_error_ts(
        os.path.join(fixture_dir, "cc_error.ts")
    )
    fixtures["corrupt_sync"] = generate_corrupt_sync_ts(
        os.path.join(fixture_dir, "corrupt_sync.ts")
    )
    fixtures["truncated"] = generate_truncated_ts(
        os.path.join(fixture_dir, "truncated.ts")
    )
    
    return fixtures
