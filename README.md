# FIRE-C2: Fire-Triggered C2 Backdoor Simulation Framework

**Environment-Triggered Command-and-Control Backdoor Dataset Generator for IoT Fire Alarm Networks**

[![ns-3: 3.x](https://img.shields.io/badge/ns--3-3.x-blue.svg)](https://www.nsnam.org/)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Dataset Structure](#dataset-structure)
- [Configuration](#configuration)
- [Advanced Usage](#advanced-usage)
- [Research Context](#research-context)
- [Citation](#citation)
- [License](#license)

---

## 🔬 Overview

FIRE-C2 is a high-fidelity ns-3-based simulation framework that generates multi-modal datasets for studying environment-triggered C2 backdoors in IoT fire alarm networks. Unlike reactive malware, these backdoors activate only when environmental conditions (fire detection) provide plausible cover for network anomalies.

**Research Contribution**: This framework enables controlled experimentation with adaptive IoT malware in safety-critical systems where real-world testing is impossible.

### Attack Scenario

1. **Dormant Phase**: Compromised sensors behave normally
2. **Environmental Trigger**: Physical fire detected via temperature sensors (≥55°C)
3. **C2 Activation**: Backdoor initiates covert communication under fire alarm cover traffic
4. **Bidirectional C&C**: Attacker exfiltrates data AND receives commands from cloud server
5. **Evasion**: Spoofed temperature readings conceal attack while fire spreads

---

## ✨ Key Features

### Network Simulation
- **80-node grid topology** (8×10) with realistic WiFi 802.11n
- **Dual-channel architecture**: Legitimate traffic (UDP:9000) + Covert C2 (UDP:4444 uplink, UDP:4445 downlink)
- **Physical-layer metrics**: Position-based RSSI/SINR via log-distance path loss model with Nakagami-m fading
- **Network conditions**: 3% packet loss, 80ms jitter, realistic propagation delays
- **Grid spacing**: 15 meters between adjacent nodes

### Fire Dynamics
- **Realistic heat transfer**: Inverse-distance diffusion with thermal inertia (Equations 4–6 in paper)
- **Probabilistic fire spread**: Distance-dependent ignition with heat accumulation
- **Temporal realism**: Independent fire physics timestep (1s) decoupled from network transmission
- **NFPA 72 & ISO 7240 alignment**: Fire parameters calibrated to real-world fire-alarm testing profiles

### C2 Backdoor Implementation
- **Dual-channel covert communication**:
  - **LSB steganography**: Temperature value manipulation (fractional LSB encoding, ±0.01°C perturbation)
  - **Timing modulation**: Inter-packet delays encode binary patterns (0 → base, 1 → +350ms)
- **Bidirectional C&C**:
  - **Uplink**: Beacons (heartbeat, 2.5s interval) + Exfiltration (6.0s interval, temperature history)
  - **Downlink**: Commands on UDP:4445 (increase_exfil, decrease_exfil, go_dormant, resume, change_pattern)
- **Realistic trigger logic**: Activates only when `temp > 55°C` AND `time >= FIRE_START`

### Dataset Generation
- **Six CSV modalities** per simulation run with synchronized timestamps:
  1. **packets**: Timestamped network traffic (21 columns)
  2. **node_states**: Time-series of all nodes (24 columns)
  3. **covert_channel**: C2 activity (9 columns)
  4. **network_metrics**: Performance statistics (15 columns)
  5. **attack_events**: Attack lifecycle (11 columns)
  6. **fire_dynamics**: Heat propagation (13 columns)

---

## 💻 System Requirements

### Minimum
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Disk**: 5 GB free space

### Software Dependencies
- **ns-3**: Version 3.35+ with Python bindings (cppyy)
- **Python**: 3.8 or higher
- **Libraries**:
  ```bash
  numpy>=1.21.0
  ```

---

## 🚀 Installation

### 1. Install ns-3 with Python Bindings

```bash
# Clone ns-3
cd ~
git clone https://gitlab.com/nsnam/ns-3-dev.git
cd ns-3-dev

# Configure with Python bindings
./ns3 configure --enable-examples --enable-tests --enable-python-bindings

# Build
./ns3 build
```

### 2. Install FIRE-C2 Framework

```bash
# Clone into ns-3 scratch directory
cd ~/ns-3-dev/scratch
git clone https://github.com/rouaamohd/fire-c2-framework.git version-2

# Install Python dependencies
cd version-2/classes
pip3 install -r requirements.txt
```

### 3. Verify Installation

```bash
cd ~/ns-3-dev
./ns3 run "scratch/version-2/classes/validation-test.py"
```

**Expected output**:
```
🎉 VALIDATION PASSED - Ready for dataset generation!
```

---

## 🎯 Quick Start

### Run Single Simulation

```bash
cd ~/ns-3-dev
./ns3 run "scratch/version-2/classes/main.py --stop 240 --seed 12345"
```

**Output**: `c2_backdoor_dataset/` directory (in current working directory) with 6 CSV files + metadata

### Generate Full Dataset (250 runs)

```bash
cd ~/ns-3-dev/scratch/version-2
bash generate_dataset.sh
```

### Key Parameters

```bash
--stop SECONDS      # Simulation duration (default: 240s)
--rows INT          # Grid rows (default: 8)
--cols INT          # Grid columns (default: 10)
--seed INT          # RNG seed for reproducibility (default: 12345)
--run INT           # Run number for seed offset (default: 0)
--output DIR        # Output directory (default: c2_backdoor_dataset)
--c2 {0,1}          # Enable C2 (1) or benign-only (0) (default: 1)
```

---

## 📊 Dataset Structure

### File Naming Convention
```
{modality}_{timestamp}_seed{seed}_run{run}_c2{c2}.csv
```

Example:
```
packets_20260214_120530_seed42_run0_c21.csv
```

### Modality Schemas

#### 1. `packets_{run_id}.csv` (Network Traffic) — 21 columns

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Simulation time (seconds) |
| `node_id` | int | Source node ID (0-79) |
| `packet_type` | str | BENIGN, FIRE, RX_CLOUD, DROPPED, TX_C2_BEACON, TX_C2_EXFIL, TX_C2_CMD, C2_SPOOF, REACTIVE_SPOOF |
| `direction` | str | tx, rx, tx_c2, tx_c2_cmd |
| `size_bytes` | int | Packet size (128 bytes typical) |
| `source_ip` | str | Source IP address (10.0.0.x or 10.0.1.x) |
| `dest_ip` | str | Destination IP address |
| `protocol` | str | UDP (all in FIRE-C2) |
| `sequence_number` | int | Per-flow packet sequence |
| `temperature_value` | float | Reported temperature reading (may be spoofed) |
| `is_spoofed` | bool | True if attacker node generated spoofed telemetry |
| `attack_pattern` | str | BENIGN, FIRE, C2_SPOOF, or attack label |
| `network_delay` | float | End-to-end latency (seconds) |
| `packet_loss` | bool | 1 if packet was dropped, 0 otherwise |
| `rssi` | float | Received Signal Strength Indicator (dBm) |
| `sinr` | float | Signal-to-Interference-plus-Noise Ratio (dB) |
| `tx_power` | float | Transmit power (dBm) |
| `data_rate` | float | Link data rate (Mbps) |
| `retransmission_count` | int | Number of MAC-layer retransmissions |
| `congestion_window` | int | TCP/UDP congestion control window |
| `queue_delay` | float | Queueing contribution to latency (seconds) |
| `hop_count` | int | Path length / routing hops |

**Labels by packet_type**:
- `BENIGN`: Normal telemetry from benign nodes
- `FIRE`: Temperature telemetry from nodes affected by fire
- `RX_CLOUD`: Packet received at cloud sink
- `DROPPED`: Packet lost due to DROP_P probability
- `TX_C2_BEACON`: Timing-modulated beacon (uplink)
- `TX_C2_EXFIL`: LSB-encoded exfiltration (uplink)
- `TX_C2_CMD`: Downlink command from cloud to attacker
- `C2_SPOOF`: Spoofed telemetry from compromised node during C2
- `REACTIVE_SPOOF`: Spoofed telemetry from node responding to local fire detection

---

#### 2. `node_states_{run_id}.csv` (Time-Series Telemetry) — 24 columns

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Simulation time |
| `node_id` | int | Node ID (0-79) |
| `position_x`, `position_y` | float | Physical grid coordinates (meters) |
| `actual_temperature` | float | True ambient + fire effect temperature |
| `reported_temperature` | float | Value transmitted (may differ if spoofed) |
| `temperature_variance` | float | Variance with neighbors' readings |
| `is_on_fire` | bool | Node is actively burning |
| `heat_level` | float | Normalized heat intensity [0.0, 1.0] |
| `received_heat` | float | Heat received from neighboring nodes |
| `fire_start_time` | float | Timestamp of fire ignition at this node |
| `is_attacker` | bool | Node is compromised (in ATTACKER_IDS) |
| `attack_triggered` | bool | C2 backdoor is active |
| `attack_mode` | str | None, C2_BACKDOOR, or DORMANT |
| `coalition_active` | bool | Global flag: any attacker has activated |
| `battery_level_reserved` | str | Reserved for future power modeling |
| `sensor_health_reserved` | str | Reserved for future reliability modeling |
| `neighbor_count` | int | Number of 4-connected neighbors in grid |
| `packets_sent` | int | benign_tx + malicious_tx |
| `packets_received` | int | Packets this node received from others |
| `packets_dropped` | int | Packets dropped due to wireless loss |
| `malicious_packets_sent` | int | Count of C2-related packets transmitted |
| `spoofing_count` | int | Number of temperature spoofing events |
| `drift_offset` | float | Clock synchronization drift (seconds) |

---

#### 3. `covert_channel_{run_id}.csv` (C2 Activity) — 9 columns

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Event time (seconds) |
| `node_id` | int | Attacker node ID |
| `channel_type` | str | c2_udp (uplink beacons/exfil), c2_downlink (commands), c2_reception (command received) |
| `message_type` | str | beacon, exfil, command |
| `bit_sequence` | str | 32-bit pattern being encoded/transmitted |
| `timing_delay` | float | Modulation delay applied (0.0 for bit=0, 0.35s for bit=1) |
| `lsb_encoded_value` | int | Decoded LSB parity bit from temperature (0 or 1) |
| `payload_size` | int | Packet size in bytes |
| `protocol_used` | str | UDP or SIMULATED_CMD |

**Ground-truth C2 events**: Each row is a direct C2 communication event with full transparency into timing, encoding, and command details. This is the primary source for validating C2 detection algorithms.

---

#### 4. `network_metrics_{run_id}.csv` (Performance Metrics) — 15 columns

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Measurement time |
| `metric_type` | str | Performance category (throughput, latency, signal_strength, etc.) |
| `value` | float | Primary metric value |
| `node_id` | int | Node-specific (-1 for global metrics) |
| `interface` | str | Network interface (wifi, p2p, etc.) |
| `throughput_mbps` | float | Data transfer rate (Mbps) |
| `latency_ms` | float | Round-trip time (milliseconds) |
| `jitter_ms` | float | Delay variation (ms) |
| `packet_loss_rate` | float | Loss percentage [0.0, 1.0] |
| `utilization_percent` | float | Channel usage [0.0, 100.0] |
| `queue_length` | int | Buffer occupancy (packets) |
| `collision_count` | int | MAC-layer collisions |
| `signal_strength` | float | RSSI (dBm) |
| `noise_floor` | float | Background noise (dBm, typically -95) |
| `channel_busy_time` | float | Medium occupancy fraction [0.0, 1.0] |

---

#### 5. `attack_events_{run_id}.csv` (Attack Lifecycle) — 11 columns

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Event time |
| `attack_type` | str | C2_ACTIVATION, SPOOFING, FIRE_DETECTION, ALARM |
| `attacker_ids` | list | Comma-separated node IDs participating |
| `duration` | float | Attack phase duration (seconds) |
| `intensity` | float | Attack strength [0.0, 1.0] |
| `success_rate` | float | Effectiveness [0.0, 1.0] |
| `detection_status` | str | undetected, suspicious, detected |
| `impact_score` | float | Consequence severity [0.0, 1.0] |
| `technique` | str | Attack technique used |
| `target_nodes` | list | Affected node IDs |
| `triggers` | list | Activation conditions met |

---

#### 6. `fire_dynamics_{run_id}.csv` (Fire Propagation) — 13 columns

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Sample time |
| `node_id` | int | Node ID |
| `fire_intensity` | float | Heat intensity [0.0, 1.0] |
| `spread_rate` | float | Fire propagation velocity |
| `wind_effect_x`, `wind_effect_y` | float | Environmental wind factors (reserved for future use) |
| `neighbor_influence` | float | Heat influence from neighboring nodes |
| `ignition_probability` | float | Likelihood of node catching fire [0.0, 1.0] |
| `radiative_heat` | float | Radiative heat transfer component |
| `convective_heat` | float | Convective heat transfer component |
| `fuel_remaining` | float | Fuel consumption [0.0, 100.0] |
| `suppression_effect` | float | Firefighting effectiveness [0.0, 1.0] |
| `reignition_count` | int | Number of ignition events |

---

### Dataset Statistics (Typical 240s Run)

**Single simulation run (240 seconds):**
- **Total packets**: ~11,000–14,000 (varies with stochasticity)
- **Node states**: ~19,000–24,000 (sampled at NODE_STATE_SAMPLE_RATE × STOP_TIME)
- **Covert channel events**: ~400–600 (beacons, exfiltration, commands)
- **Network metrics**: ~2,000–3,000 (sampled at NETWORK_METRICS_SAMPLE_RATE × STOP_TIME)
- **Attack events**: ~5–10 (lifecycle markers)
- **Fire dynamics**: ~18,000–24,000 (fire propagation per tick)
- **Total size**: ~3–5 MB per run (depends on sampling rates)

**Full dataset (250 runs):**
- **Total packets**: 2,842,854
- **Node state records**: 14,218,508
- **Covert channel events**: 104,770
- **Attack events**: 1,250
- **Total size**: ~625–700 MB

---

## ⚙️ Configuration

Edit `classes/Config.py` to customize simulation parameters:

```python
class Config:
    # Random Seed
    SEED = 1337
    
    # Grid Topology
    N_ROWS, N_COLS = 8, 10        # 80 nodes total
    N_NODES = N_ROWS * N_COLS
    ATTACKER_IDS = [25, 26, 34, 36, 45]  # 5 compromised nodes (6.25%)
    FIRE_NODE_ID = 35              # Fire ignition node
    
    # Fire Event Timing
    FIRE_START = 25.0              # Fire ignition time (s)
    FIRE_DURATION = 140.0          # Fire lifetime (s)
    FIRE_SPREAD_DELAY = 4.0        # Delay before spreading
    FIRE_TICK_INTERVAL = 1.0       # Fire propagation step (s)
    
    # Temperature Thresholds
    FIRE_TEMP = 85.0               # Maximum fire temperature (°C)
    FIRE_THRESH = 70.0             # Fire alarm threshold (°C)
    FIRE_DETECT_THRESH = 55.0      # C2 activation threshold (°C)
    BENIGN_TEMP_RANGE = (20.0, 25.0)
    SPOOFED_TEMP_RANGE = (18.0, 22.0)
    
    # Network Parameters
    DROP_P = 0.03                  # 3% packet loss
    SEND_INT = 2.0                 # Base transmission interval (s)
    JITTER_MAX = 0.08              # Max jitter (s)
    PKT_SIZE = 128                 # Standard packet size (bytes)
    PORT = 9000                    # Legitimate telemetry port
    STOP_TIME = 240.0              # Simulation duration (s)
    
    # Temperature Spoofing
    SPOOFED_TEMP_MEAN = 20.0
    SPOOFED_TEMP_STD = 1.0
    MAX_TEMP_DELTA = 0.3           # Max temperature change per step
    TEMP_HISTORY_WINDOW = 20       # Temperature history buffer size
    
    # Fire Dynamics (Physics)
    FIRE_SPREAD_RATE = 0.22        # Ignition probability multiplier
    HEAT_DIFFUSION_RATE = 0.45     # Heat transfer coefficient
    RESIDUAL_HEAT_DECAY = 0.88     # Heat decay rate
    MAX_HEAT_RADIUS = 3            # Manhattan distance for heat propagation
    
    # Data Collection
    DATA_COLLECTION_ENABLED = True
    DATA_OUTPUT_DIR = "c2_backdoor_dataset"
    NODE_STATE_SAMPLE_RATE = 0.4   # Fraction of nodes sampled per tick
    NETWORK_METRICS_SAMPLE_RATE = 0.8
    
    # C2 Backdoor (Uplink)
    C2_ENABLED = True
    C2_PORT = 4444                 # Covert uplink port
    C2_BEACON_INT = 2.5            # Beacon interval (s)
    C2_JITTER = 0.2                # ±0.2s random jitter on beacon timing
    C2_TIMING_DELTA = 0.35         # Timing offset for bit encoding (s)
    C2_BITSTRING = "10110011100101101011001110010110"  # 32-bit pattern
    C2_EXFIL_PERIOD = 6.0          # Exfiltration interval (s)
    C2_MAX_BYTES = 128             # Max exfiltration payload (bytes)
    
    # C2 Backdoor (Downlink / Commands)
    C2_CMD_PORT = 4445             # Command port
    C2_CMD_INTERVAL = 15.0         # Base command dispatch interval (s)
    C2_CMD_JITTER = 2.0            # ±2.0s jitter on commands
```

---

## 🔧 Advanced Usage

### Custom Attacker Placement

```python
# Edit Config.py
ATTACKER_IDS = [10, 20, 30, 40, 50]  # Custom node IDs
```

### Benign-Only Dataset (No C2)

```bash
./ns3 run "scratch/version-2/classes/main.py --c2 0 --output benign_dataset"
```

### Batch Generation with Parameter Sweep

```bash
# Vary fire start time
for fire_time in 20 25 30 35 40; do
    # Edit Config.FIRE_START or use environment variable
    ./ns3 run "scratch/version-2/classes/main.py --seed $fire_time --output dataset_fire$fire_time"
done
```

### Reproducibility

```bash
# Same seed + run = identical simulation
./ns3 run "scratch/version-2/classes/main.py --seed 42 --run 0"  # Run A
./ns3 run "scratch/version-2/classes/main.py --seed 42 --run 0"  # Run B (identical to A)

# Different run number = different random events
./ns3 run "scratch/version-2/classes/main.py --seed 42 --run 1"  # Run C (different from A/B)
```

---

## 🐛 Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'ns'`

**Solution**: ns-3 Python bindings not installed. Re-run:
```bash
cd ~/ns-3-dev
./ns3 configure --enable-python-bindings
./ns3 build
```

### Issue: Validation test fails

**Solution**: Check ns-3 version compatibility:
```bash
./ns3 --version  # Should be 3.35+
```

### Issue: Empty covert_channel CSV

**Solution**: Verify C2 is enabled and attackers are configured:
```bash
grep "C2_ENABLED\|ATTACKER_IDS" classes/Config.py
```

---

### Citation

If you use FIRE-C2 in your research, please cite:

```bibtex

```

**Dataset Citation**:

```bibtex
@dataset{FIRE-C2-dataset,
  author = {Naim, Rouaa and Gelban, Hams and Badawy, Ahmed},
  title = {{FIRE-C2}: A Multi-Modal {ns-3} Dataset for Environment-Triggered Backdoor Attacks in Wireless {IoT} Networks},
  year = {2026},
  doi = {10.21227/dgv6-1f39}
}
```

---

