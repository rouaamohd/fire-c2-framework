"""
FIRE-C2 Configuration Parameters

This module defines all simulation parameters for the FIRE-C2 framework,
including network topology, fire dynamics, C2 backdoor characteristics,
and dataset collection settings.

Parameter categories:
- Grid topology and node placement
- Fire ignition, propagation, and heat transfer physics
- Network conditions (packet loss, jitter, timing)
- C2 backdoor channel parameters (timing modulation, LSB encoding)
- Data collection and output settings

Copyright (c) 2025 FIRE-C2 Research Team
Licensed under the MIT License
"""

class Config:
    """Global configuration parameters for FIRE-C2 simulation"""

    SEED = 1337

    # ============================================================================
    # Grid Topology Configuration
    # ============================================================================
    N_ROWS, N_COLS = 8, 10
    N_NODES = N_ROWS * N_COLS
    ATTACKER_IDS = [25, 26, 34, 36, 45]
    FIRE_NODE_ID = 35

    # ============================================================================
    # Fire Event Timing
    # ============================================================================
    FIRE_START = 25.0
    FIRE_DURATION = 140.0
    FIRE_SPREAD_DELAY = 4.0

    # ============================================================================
    # Temperature Thresholds
    # ============================================================================
    FIRE_TEMP = 85.0
    FIRE_THRESH = 70.0
    FIRE_DETECT_THRESH = 55.0
    BENIGN_TEMP_RANGE = (20.0, 25.0)
    SPOOFED_TEMP_RANGE = (18.0, 22.0)

    # ============================================================================
    # Network Parameters
    # ============================================================================
    DROP_P = 0.03
    SEND_INT = 2.0
    JITTER_MAX = 0.08
    PKT_SIZE = 128
    PORT = 9000
    STOP_TIME = 240.0

    # ============================================================================
    # Attack Configuration
    # ============================================================================
    TEMP_HISTORY_WINDOW = 20

    # ============================================================================
    # Fire Dynamics (Physical Modeling)
    # ============================================================================
    FIRE_SPREAD_RATE = 0.22
    HEAT_DIFFUSION_RATE = 0.45
    RESIDUAL_HEAT_DECAY = 0.88
    MAX_HEAT_RADIUS = 3
    FIRE_TICK_INTERVAL = 1.0

    # ============================================================================
    # Temperature Spoofing Parameters
    # ============================================================================
    SPOOFED_TEMP_MEAN = 20.0
    SPOOFED_TEMP_STD = 1.0
    MAX_TEMP_DELTA = 0.3

    # ============================================================================
    # Data Collection Settings
    # ============================================================================
    DATA_COLLECTION_ENABLED = True
    DATA_OUTPUT_DIR = "c2_backdoor_dataset"
    NODE_STATE_SAMPLE_RATE = 0.4
    NETWORK_METRICS_SAMPLE_RATE = 0.8

    # ============================================================================
    # C2 Backdoor Channel Parameters
    # ============================================================================
    C2_ENABLED = True
    C2_PORT = 4444
    C2_BEACON_INT = 2.5
    C2_JITTER = 0.2
    C2_TIMING_DELTA = 0.35
    C2_BITSTRING = "10110011100101101011001110010110"
    C2_EXFIL_PERIOD = 6.0
    C2_MAX_BYTES = 128

    # ============================================================================
    # Bidirectional C2 Command Channel
    # ============================================================================
    C2_CMD_PORT = 4445
    C2_CMD_INTERVAL = 15.0
    C2_CMD_JITTER = 2.0
