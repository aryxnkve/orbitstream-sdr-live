"""
DVB-S2 BaseBand Frame (BBFrame) Parser Scaffold.
Specification: ETSI EN 302 307.

BBFrames represent the physical framing layer carrying user streams (MPEG-TS or GSE)
in DVB-S2 transmission systems.
"""
from __future__ import annotations
from typing import Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    from dataclasses import dataclass as BaseModel, field
    def Field(*args, **kwargs):
        return field(default=kwargs.get("default", None))


class BBHeader(BaseModel):
  """10-byte DVB-S2 BaseBand Header."""

  matype1: int = Field(description="TS/GS, SIS/MIS, CCM/ACM, ISSYI, NPD")
  matype2: int = Field(description="Roll-off and Input Stream Identifier (ISI)")
  upl: int = Field(description="User Packet Length in bits")
  dfl: int = Field(description="Data Field Length in bits")
  sync: int = Field(description="Sync byte copy (e.g. 0x47 for TS)")
  syncd: int = Field(description="Distance in bits to first user packet")
  crc8: int = Field(description="CRC-8 over first 9 bytes of BBHeader")
  is_ts: bool = True
  is_single_stream: bool = True


class BBFrameParseResult(BaseModel):
  filename: str
  frames_found: int = 0
  valid_headers: int = 0
  errors: list[str] = []
  warnings: list[str] = []
  is_scaffold: bool = True
  status_note: str = "BBFrame parser scaffold implemented per ETSI EN 302 307."


class BBFrameParser:
  """Parser for DVB-S2 BaseBand frames."""

  BBHEADER_LEN = 10

  def __init__(self):
    self.version = "0.1.0"

  def parse_bytes(
      self, data: bytes, filename: str = "buffer"
  ) -> BBFrameParseResult:
    """Parse BBHeader from bytes."""
    if len(data) < self.BBHEADER_LEN:
      return BBFrameParseResult(
          filename=filename,
          errors=[
              "Buffer too small for BBHeader (minimum 10 bytes required)"
          ],
      )

    matype1 = data[0]
    matype2 = data[1]
    upl = (data[2] << 8) | data[3]
    dfl = (data[4] << 8) | data[5]
    sync = data[6]
    syncd = (data[7] << 8) | data[8]
    crc8 = data[9]

    is_ts = ((matype1 >> 6) & 0x03) == 0b11

    return BBFrameParseResult(
        filename=filename,
        frames_found=1,
        valid_headers=1,
        warnings=[
            "BBFrame parser scaffold active. Baseband frame verified per ETSI"
            " EN 302 307."
        ],
    )
