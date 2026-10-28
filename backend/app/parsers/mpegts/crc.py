"""
MPEG Transport Stream CRC-32 implementation.
Uses the CRC-32/MPEG-2 polynomial (0x04C11DB7) as specified in ISO/IEC 13818-1.
"""


def _build_crc32_table() -> list[int]:
    """Build the CRC-32 lookup table for MPEG-2."""
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
        table.append(crc)
    return table


_CRC32_TABLE = _build_crc32_table()


def crc32_mpeg2(data: bytes) -> int:
    """
    Compute CRC-32/MPEG-2 over the given data.
    The initial value is 0xFFFFFFFF and there is no final XOR
    (the standard expects the CRC field itself to be included
    in the check, yielding 0x00000000 for valid sections).
    """
    crc = 0xFFFFFFFF
    for byte in data:
        crc = ((crc << 8) ^ _CRC32_TABLE[((crc >> 24) ^ byte) & 0xFF]) & 0xFFFFFFFF
    return crc


def verify_section_crc(section_data: bytes) -> bool:
    """
    Verify CRC-32 of a complete MPEG-2 section (including the CRC field).
    Returns True if the CRC is valid (result is 0x00000000).
    """
    if len(section_data) < 4:
        return False
    return crc32_mpeg2(section_data) == 0x00000000
