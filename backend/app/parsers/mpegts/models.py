"""
Pydantic models for MPEG Transport Stream parsing results.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PacketSize(int, Enum):
    """Known TS packet sizes."""
    STANDARD = 188
    TIMESTAMPED = 192
    FEC = 204


class AdaptationFieldControl(int, Enum):
    RESERVED = 0
    PAYLOAD_ONLY = 1
    ADAPTATION_ONLY = 2
    ADAPTATION_AND_PAYLOAD = 3


class ScramblingControl(int, Enum):
    NOT_SCRAMBLED = 0
    RESERVED = 1
    EVEN_KEY = 2
    ODD_KEY = 3


class AdaptationField(BaseModel):
    """Parsed adaptation field from a TS packet."""
    length: int = Field(ge=0, le=183)
    discontinuity_indicator: bool = False
    random_access_indicator: bool = False
    elementary_stream_priority: bool = False
    pcr_flag: bool = False
    opcr_flag: bool = False
    splicing_point_flag: bool = False
    transport_private_data_flag: bool = False
    extension_flag: bool = False
    pcr: Optional[int] = None
    opcr: Optional[int] = None
    splice_countdown: Optional[int] = None


class TSPacket(BaseModel):
    """A single parsed MPEG Transport Stream packet."""
    index: int = Field(description="Zero-based packet index in the file")
    offset: int = Field(description="Byte offset in the source file")
    sync_byte: int = Field(description="Should be 0x47 for valid packets")
    transport_error_indicator: bool = False
    payload_unit_start_indicator: bool = False
    transport_priority: bool = False
    pid: int = Field(ge=0, le=0x1FFF)
    scrambling_control: ScramblingControl = ScramblingControl.NOT_SCRAMBLED
    adaptation_field_control: AdaptationFieldControl = AdaptationFieldControl.PAYLOAD_ONLY
    continuity_counter: int = Field(ge=0, le=15)
    adaptation_field: Optional[AdaptationField] = None
    payload: Optional[bytes] = None
    raw_bytes: Optional[bytes] = None
    has_payload: bool = True
    is_valid: bool = True
    parse_error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def payload_hex(self) -> Optional[str]:
        if self.payload:
            return self.payload.hex()
        return None

    def raw_hex(self) -> Optional[str]:
        if self.raw_bytes:
            return self.raw_bytes.hex()
        return None

    def header_hex(self) -> str:
        if self.raw_bytes and len(self.raw_bytes) >= 4:
            return self.raw_bytes[:4].hex()
        return ""


class PIDInfo(BaseModel):
    """Aggregated information about a single PID."""
    pid: int
    pid_hex: str = ""
    packet_count: int = 0
    byte_count: int = 0
    label: str = ""
    stream_type: Optional[int] = None
    stream_type_name: str = ""
    program_number: Optional[int] = None
    has_errors: bool = False
    error_count: int = 0
    scrambled_count: int = 0
    is_scrambled: bool = False
    continuity_errors: int = 0
    first_packet_index: int = 0
    last_packet_index: int = 0


class PATEntry(BaseModel):
    """A single entry in the Program Association Table."""
    program_number: int
    pid: int
    pid_hex: str = ""
    is_network_pid: bool = False  # program_number == 0 means NIT PID


class PATInfo(BaseModel):
    """Parsed Program Association Table."""
    transport_stream_id: int = 0
    version_number: int = 0
    current_next: bool = True
    entries: list[PATEntry] = []
    crc_valid: Optional[bool] = None
    raw_section_length: int = 0


class PMTStream(BaseModel):
    """A single elementary stream entry in a PMT."""
    stream_type: int
    stream_type_name: str = ""
    elementary_pid: int
    elementary_pid_hex: str = ""
    es_info_length: int = 0


class PMTInfo(BaseModel):
    """Parsed Program Map Table."""
    program_number: int
    version_number: int = 0
    current_next: bool = True
    pcr_pid: int = 0
    pcr_pid_hex: str = ""
    program_info_length: int = 0
    streams: list[PMTStream] = []
    crc_valid: Optional[bool] = None
    raw_section_length: int = 0


class StreamFormat(str, Enum):
    MPEGTS_188 = "mpegts_188"
    MPEGTS_192 = "mpegts_192"
    MPEGTS_204 = "mpegts_204"
    GSE = "gse"
    BBFRAME = "bbframe"
    PCAP = "pcap"
    UNKNOWN = "unknown"


class ParseResult(BaseModel):
    """Complete result of parsing a transport stream file."""
    filename: str
    file_size: int
    detected_format: StreamFormat
    packet_size: int = 188
    total_packets: int = 0
    valid_packets: int = 0
    error_packets: int = 0
    null_packets: int = 0
    scrambled_packets: int = 0
    pids: dict[int, PIDInfo] = {}
    pat: Optional[PATInfo] = None
    pmts: dict[int, PMTInfo] = {}  # keyed by program_number
    packets: list[TSPacket] = []
    warnings: list[str] = []
    errors: list[str] = []
    parser_version: str = "0.1.0"
    sync_losses: int = 0
    duration_estimate: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
