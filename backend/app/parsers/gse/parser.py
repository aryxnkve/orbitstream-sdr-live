"""
Generic Stream Encapsulation (GSE) Parser Scaffold.
Specification: ETSI TS 102 606 (DVB-GSE).

GSE provides efficient encapsulation of IP and other network-layer packets
over DVB-S2 physical and baseband layers.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    from dataclasses import dataclass as BaseModel, field
    def Field(*args, **kwargs):
        return field(default=kwargs.get("default", None))


class GSEStartEnd(int, Enum):
  INTERMEDIATE = 0b00  # Intermediate fragment
  END = 0b01  # End fragment
  START = 0b10  # Start fragment
  COMPLETE = 0b11  # Single, complete packet (unfragmented)


class GSEHeader(BaseModel):
  start_end: GSEStartEnd
  length: int = Field(ge=0, le=4095, description="GSE packet length in bytes")
  protocol_type: Optional[int] = Field(
      default=None, description="EtherType or extension header type"
  )
  label_type: int = Field(
      default=0, description="0=6-byte MAC, 1=3-byte, 2=Broadcast, 3=Reserved"
  )
  total_length: Optional[int] = Field(
      default=None, description="Total PDU length (if Start fragment)"
  )


class GSEParseResult(BaseModel):
  filename: str
  packets_parsed: int = 0
  valid_packets: int = 0
  errors: list[str] = []
  warnings: list[str] = []
  is_scaffold: bool = True
  status_note: str = (
      "GSE protocol header scaffold implemented per ETSI TS 102 606."
  )


class GSEParser:
  """Parser for GSE streams."""

  def __init__(self):
    self.version = "0.1.0"

  def parse_bytes(
      self, data: bytes, filename: str = "buffer"
  ) -> GSEParseResult:
    """Parse GSE packets from bytes."""
    if len(data) < 2:
      return GSEParseResult(
          filename=filename,
          errors=["Buffer too small for GSE header (minimum 2 bytes required)"],
      )

    # First 2 bytes: S (1 bit), E (1 bit), LT (2 bits), GSE Length (12 bits)
    first_word = (data[0] << 8) | data[1]
    se_bits = (first_word >> 14) & 0x03
    lt_bits = (first_word >> 12) & 0x03
    gse_len = first_word & 0x0FFF

    return GSEParseResult(
        filename=filename,
        packets_parsed=1,
        valid_packets=1 if len(data) >= 2 + gse_len else 0,
        warnings=["GSE encapsulation parsing is in scaffold evaluation mode."],
    )
