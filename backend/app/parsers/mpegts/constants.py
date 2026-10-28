"""
MPEG Transport Stream parser constants.
Based on ISO/IEC 13818-1 (MPEG-2 Systems).
"""

# Sync byte that starts every TS packet
SYNC_BYTE = 0x47

# Standard packet sizes
TS_PACKET_SIZE = 188
TS_PACKET_SIZE_192 = 192  # With 4-byte timestamp prefix (BDAV/M2TS)
TS_PACKET_SIZE_204 = 204  # With 16-byte FEC suffix (DVB)

KNOWN_PACKET_SIZES = [TS_PACKET_SIZE, TS_PACKET_SIZE_192, TS_PACKET_SIZE_204]

# Well-known PIDs
PID_PAT = 0x0000          # Program Association Table
PID_CAT = 0x0001          # Conditional Access Table
PID_TSDT = 0x0002         # Transport Stream Description Table
PID_IPMP = 0x0003         # IPMP Control Information
PID_NULL = 0x1FFF         # Null packets (stuffing)

# PID ranges
PID_DVB_RESERVED_MIN = 0x0004
PID_DVB_RESERVED_MAX = 0x000F
PID_GENERAL_MIN = 0x0010
PID_GENERAL_MAX = 0x1FFE

# Table IDs
TABLE_ID_PAT = 0x00
TABLE_ID_PMT = 0x02
TABLE_ID_CAT = 0x01

# Adaptation field control values
AFC_RESERVED = 0b00
AFC_PAYLOAD_ONLY = 0b01
AFC_ADAPTATION_ONLY = 0b10
AFC_ADAPTATION_AND_PAYLOAD = 0b11

# Scrambling control values
SC_NOT_SCRAMBLED = 0b00
SC_RESERVED = 0b01
SC_EVEN_KEY = 0b10
SC_ODD_KEY = 0b11

# Continuity counter range
CC_MAX = 15  # 4-bit field: 0-15

# Stream type codes (ISO/IEC 13818-1 Table 2-36 + extensions)
STREAM_TYPES = {
    0x00: "Reserved",
    0x01: "MPEG-1 Video (ISO/IEC 11172-2)",
    0x02: "MPEG-2 Video (ISO/IEC 13818-2)",
    0x03: "MPEG-1 Audio (ISO/IEC 11172-3)",
    0x04: "MPEG-2 Audio (ISO/IEC 13818-3)",
    0x05: "Private Sections (ISO/IEC 13818-1)",
    0x06: "PES Private Data (ISO/IEC 13818-1)",
    0x07: "MHEG",
    0x08: "DSM-CC",
    0x09: "ITU-T H.222.1",
    0x0A: "DSM-CC Type A",
    0x0B: "DSM-CC Type B",
    0x0C: "DSM-CC Type C",
    0x0D: "DSM-CC Type D",
    0x0E: "Auxiliary (ISO/IEC 13818-1)",
    0x0F: "AAC Audio (ISO/IEC 13818-7)",
    0x10: "MPEG-4 Visual (ISO/IEC 14496-2)",
    0x11: "MPEG-4 Audio (ISO/IEC 14496-3)",
    0x15: "Metadata (ISO/IEC 13818-1)",
    0x1B: "H.264/AVC Video (ISO/IEC 14496-10)",
    0x24: "H.265/HEVC Video (ITU-T H.265)",
    0x81: "AC-3 Audio (ATSC)",
    0x82: "DTS Audio",
    0x83: "Dolby TrueHD",
    0x84: "Dolby Digital Plus (AC-3+)",
    0x86: "SCTE-35 Splice Information",
    0x87: "E-AC-3 Audio",
}

# CRC-32 polynomial for MPEG-2 sections
CRC32_POLY = 0x04C11DB7
