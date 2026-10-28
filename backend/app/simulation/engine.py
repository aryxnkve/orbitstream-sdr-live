"""
Controlled fault simulation lab.

Operates on copies of uploaded files — never modifies the original.
Generates modified captures with specific, documented faults
for validating the diagnostic engine.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from ..parsers.mpegts.constants import SYNC_BYTE


class FaultScenario(str, Enum):
    REMOVE_PACKETS = "remove_packets"
    CC_DISCONTINUITY = "cc_discontinuity"
    CORRUPT_SYNC = "corrupt_sync"
    MODIFY_HEADER = "modify_header"
    CHANGE_SCRAMBLING = "change_scrambling"


class FaultConfig(BaseModel):
    """Configuration for a fault simulation scenario."""
    scenario: FaultScenario
    target_pid: int = 0x0100
    target_packet_indices: list[int] = Field(default_factory=list)
    # For CC discontinuity: how many CC values to skip
    cc_skip: int = 3
    # For corrupt sync: replacement byte
    corrupt_byte: int = 0x00
    # For modify header: which field and value
    header_field: str = ""
    header_value: int = 0
    # For scrambling: new scrambling control value (0-3)
    scrambling_value: int = 2
    description: str = ""


class FaultResult(BaseModel):
    """Result of applying a fault simulation."""
    scenario: FaultScenario
    description: str
    source_file: str
    modified_file: str
    source_hash: str
    modified_hash: str
    packets_affected: int = 0
    modifications: list[dict] = Field(default_factory=list)
    expected_diagnostic: str = ""
    success: bool = True
    error: str = ""


class SimulationEngine:
    """
    Fault simulation engine.
    
    Creates modified copies of TS files with controlled, documented faults.
    Each modification is recorded for verification against the diagnostic engine.
    """

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def apply_fault(self, source_path: str, config: FaultConfig) -> FaultResult:
        """Apply a fault scenario to a copy of the source file."""
        # Read source
        with open(source_path, "rb") as f:
            data = bytearray(f.read())

        source_hash = hashlib.sha256(bytes(data)).hexdigest()[:16]

        # Determine packet size (assume 188 for now, could be detected)
        packet_size = 188

        # Apply the fault
        try:
            if config.scenario == FaultScenario.REMOVE_PACKETS:
                result_data, mods = self._remove_packets(data, packet_size, config)
                expected = "Missing packets and potential continuity counter errors"
            elif config.scenario == FaultScenario.CC_DISCONTINUITY:
                result_data, mods = self._corrupt_cc(data, packet_size, config)
                expected = f"Continuity counter discontinuity on PID 0x{config.target_pid:04X}"
            elif config.scenario == FaultScenario.CORRUPT_SYNC:
                result_data, mods = self._corrupt_sync(data, packet_size, config)
                expected = "Sync byte loss and resynchronization"
            elif config.scenario == FaultScenario.MODIFY_HEADER:
                result_data, mods = self._modify_header(data, packet_size, config)
                expected = "Modified header field detected"
            elif config.scenario == FaultScenario.CHANGE_SCRAMBLING:
                result_data, mods = self._change_scrambling(data, packet_size, config)
                expected = f"Scrambled packets detected on PID 0x{config.target_pid:04X}"
            else:
                return FaultResult(
                    scenario=config.scenario,
                    description="Unknown scenario",
                    source_file=source_path,
                    modified_file="",
                    source_hash=source_hash,
                    modified_hash="",
                    success=False,
                    error=f"Unknown scenario: {config.scenario}",
                )
        except Exception as e:
            return FaultResult(
                scenario=config.scenario,
                description=config.description or str(config.scenario),
                source_file=source_path,
                modified_file="",
                source_hash=source_hash,
                modified_hash="",
                success=False,
                error=str(e),
            )

        # Write modified file
        modified_hash = hashlib.sha256(bytes(result_data)).hexdigest()[:16]
        modified_name = f"sim_{config.scenario.value}_{modified_hash}.ts"
        modified_path = os.path.join(self.storage_dir, modified_name)

        with open(modified_path, "wb") as f:
            f.write(result_data)

        return FaultResult(
            scenario=config.scenario,
            description=config.description or self._default_description(config),
            source_file=source_path,
            modified_file=modified_path,
            source_hash=source_hash,
            modified_hash=modified_hash,
            packets_affected=len(mods),
            modifications=mods,
            expected_diagnostic=expected,
        )

    def _remove_packets(self, data: bytearray, pkt_size: int,
                        config: FaultConfig) -> tuple[bytearray, list[dict]]:
        """Remove specified packets from the stream."""
        total = len(data) // pkt_size
        indices_to_remove = set()
        mods = []

        if config.target_packet_indices:
            indices_to_remove = set(config.target_packet_indices)
        else:
            # Remove first 2 packets matching the target PID
            count = 0
            for i in range(total):
                offset = i * pkt_size
                if offset + 4 > len(data):
                    break
                pid = ((data[offset + 1] & 0x1F) << 8) | data[offset + 2]
                if pid == config.target_pid:
                    indices_to_remove.add(i)
                    count += 1
                    if count >= 2:
                        break

        result = bytearray()
        for i in range(total):
            offset = i * pkt_size
            if i in indices_to_remove:
                pid = ((data[offset + 1] & 0x1F) << 8) | data[offset + 2]
                mods.append({
                    "action": "removed",
                    "packet_index": i,
                    "byte_offset": offset,
                    "pid": pid,
                })
            else:
                result.extend(data[offset:offset + pkt_size])

        return result, mods

    def _corrupt_cc(self, data: bytearray, pkt_size: int,
                    config: FaultConfig) -> tuple[bytearray, list[dict]]:
        """Introduce a CC discontinuity on the target PID."""
        result = bytearray(data)
        total = len(data) // pkt_size
        mods = []
        found_first = False

        for i in range(total):
            offset = i * pkt_size
            if offset + 4 > len(data):
                break
            pid = ((data[offset + 1] & 0x1F) << 8) | data[offset + 2]
            if pid == config.target_pid:
                if not found_first:
                    found_first = True
                    continue  # Skip first packet
                # Modify CC of the second packet found
                old_byte = result[offset + 3]
                old_cc = old_byte & 0x0F
                new_cc = (old_cc + config.cc_skip) & 0x0F
                result[offset + 3] = (old_byte & 0xF0) | new_cc

                mods.append({
                    "action": "cc_modified",
                    "packet_index": i,
                    "byte_offset": offset,
                    "pid": pid,
                    "old_cc": old_cc,
                    "new_cc": new_cc,
                    "skip": config.cc_skip,
                })
                break  # Only modify one packet to create a single discontinuity

        return result, mods

    def _corrupt_sync(self, data: bytearray, pkt_size: int,
                      config: FaultConfig) -> tuple[bytearray, list[dict]]:
        """Corrupt the sync byte of specified packets."""
        result = bytearray(data)
        total = len(data) // pkt_size
        mods = []

        targets = config.target_packet_indices if config.target_packet_indices else [5]

        for idx in targets:
            if idx < total:
                offset = idx * pkt_size
                old_sync = result[offset]
                result[offset] = config.corrupt_byte & 0xFF
                mods.append({
                    "action": "sync_corrupted",
                    "packet_index": idx,
                    "byte_offset": offset,
                    "old_value": f"0x{old_sync:02X}",
                    "new_value": f"0x{config.corrupt_byte:02X}",
                })

        return result, mods

    def _modify_header(self, data: bytearray, pkt_size: int,
                       config: FaultConfig) -> tuple[bytearray, list[dict]]:
        """Set the Transport Error Indicator on target packets."""
        result = bytearray(data)
        total = len(data) // pkt_size
        mods = []

        targets = config.target_packet_indices
        if not targets:
            # Find first packet on target PID
            for i in range(total):
                offset = i * pkt_size
                pid = ((data[offset + 1] & 0x1F) << 8) | data[offset + 2]
                if pid == config.target_pid:
                    targets = [i]
                    break

        for idx in targets:
            if idx < total:
                offset = idx * pkt_size
                old_byte = result[offset + 1]
                result[offset + 1] = old_byte | 0x80  # Set TEI bit
                mods.append({
                    "action": "tei_set",
                    "packet_index": idx,
                    "byte_offset": offset,
                    "old_header_byte": f"0x{old_byte:02X}",
                    "new_header_byte": f"0x{result[offset + 1]:02X}",
                })

        return result, mods

    def _change_scrambling(self, data: bytearray, pkt_size: int,
                           config: FaultConfig) -> tuple[bytearray, list[dict]]:
        """Change scrambling control bits on target PID packets."""
        result = bytearray(data)
        total = len(data) // pkt_size
        mods = []
        count = 0

        for i in range(total):
            offset = i * pkt_size
            if offset + 4 > len(data):
                break
            pid = ((data[offset + 1] & 0x1F) << 8) | data[offset + 2]
            if pid == config.target_pid:
                old_byte = result[offset + 3]
                old_sc = (old_byte >> 6) & 0x03
                new_sc = config.scrambling_value & 0x03
                result[offset + 3] = (old_byte & 0x3F) | (new_sc << 6)
                mods.append({
                    "action": "scrambling_changed",
                    "packet_index": i,
                    "byte_offset": offset,
                    "pid": pid,
                    "old_scrambling": old_sc,
                    "new_scrambling": new_sc,
                })
                count += 1
                if count >= 10:  # Limit modifications
                    break

        return result, mods

    def _default_description(self, config: FaultConfig) -> str:
        """Generate a default description for a scenario."""
        descriptions = {
            FaultScenario.REMOVE_PACKETS: (
                f"Remove packets from PID 0x{config.target_pid:04X} to simulate packet loss."
            ),
            FaultScenario.CC_DISCONTINUITY: (
                f"Skip {config.cc_skip} CC values on PID 0x{config.target_pid:04X} "
                f"to simulate a continuity counter discontinuity."
            ),
            FaultScenario.CORRUPT_SYNC: (
                f"Replace sync byte with 0x{config.corrupt_byte:02X} "
                f"to test parser resynchronization."
            ),
            FaultScenario.MODIFY_HEADER: (
                f"Set Transport Error Indicator on packets to simulate error flagging."
            ),
            FaultScenario.CHANGE_SCRAMBLING: (
                f"Set scrambling control to {config.scrambling_value} "
                f"on PID 0x{config.target_pid:04X}. "
                f"This modifies header bits only — it does not encrypt content."
            ),
        }
        return descriptions.get(config.scenario, str(config.scenario))

    def verify_original_unchanged(self, original_path: str,
                                  original_hash: str) -> bool:
        """Verify the original file was not modified."""
        with open(original_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        return current_hash == original_hash
