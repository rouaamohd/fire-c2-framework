"""
NodeStats: Per-node traffic statistics tracker

This module provides a lightweight statistics tracker for monitoring node-level
network activity in the FIRE-C2 simulation framework.

"""

from dataclasses import dataclass

@dataclass
class NodeStats:
    """
    Tracks per-node packet transmission and drop statistics.

    Attributes:
        benign_tx: Count of legitimate packets transmitted
        malicious_tx: Count of attack packets transmitted (spoofed/C2)
        drops: Count of packets dropped due to network conditions
        seq_tx: Sequence number for cloud-bound transmissions
        seq_c2: Sequence number for C2 backdoor channel transmissions
    """
    benign_tx: int = 0
    malicious_tx: int = 0
    drops: int = 0
    seq_tx: int = 0
    seq_c2: int = 0
