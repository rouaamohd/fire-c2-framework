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
2. **Environmental Trigger**: Physical fire detected via temperature sensors
3. **C2 Activation**: Backdoor initiates covert communication under fire alarm cover traffic
4. **Bidirectional C&C**: Attacker exfiltrates data AND receives commands from cloud server
5. **Evasion**: Spoofed temperature readings conceal attack while fire spreads

---

## ✨ Key Features

### Network Simulation
- **80-node grid topology** (8×10) with realistic WiFi 802.11n
- **Dual-channel architecture**: Legitimate traffic (9000/UDP) + Covert C2 (4444/UDP + 4445/UDP)
- **Physical-layer metrics**: Position-based RSSI/SINR via log-distance path loss model
- **Network conditions**: 3% packet loss, 80ms jitter, realistic propagation delays

### Fire Dynamics
- **Realistic heat transfer**: Inverse-distance diffusion with thermal inertia
- **Probabilistic fire spread**: Distance-dependent ignition with heat accumulation
- **Temporal realism**: Independent fire physics timestep (1s) decoupled from network

### C2 Backdoor Implementation
- **Dual-channel covert communication**:
  - **LSB steganography**: Temperature value manipulation (fractional LSB encoding)
  - **Timing modulation**: Inter-packet delays encode binary patterns (0 → base, 1 → +350ms)
- **Bidirectional C&C**:
  - **Uplink**: Beacons (status) + Exfiltration (temperature history)
  - **Downlink**: Commands (increase_exfil, decrease_exfil, go_dormant, resume)
- **Realistic trigger logic**: Activates only when `temp > 55°C` AND `time >= FIRE_START`

### Dataset Generation
- **Six CSV modalities** per simulation run:
  1. **packets**: Timestamped network traffic (RSSI, SINR, delay, labels)
  2. **node_states**: Time-series of all 80 nodes (temp, fire status, attack mode)
  3. **covert_channel**: C2 activity (beacons, exfil, downlink commands)
  4. **network_metrics**: Performance statistics (throughput, latency, signal strength)
  5. **attack_events**: Attack lifecycle events
  6. **fire_dynamics**: Heat propagation and spread

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
git clone https://github.com/YOUR_ORG/fire-c2.git version-2

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

**Output**: `c2_backdoor_dataset/` directory with 6 CSV files

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

#### 1. `packets_{run_id}.csv` (Network Traffic)

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Simulation time (seconds) |
| `node_id` | int | Source node ID (0-79) |
| `packet_type` | str | TX, RX, TX_C2, TX_C2_CMD |
| `direction` | str | tx, rx, tx_c2, tx_c2_cmd |
| `size_bytes` | int | Packet size |
| `rssi` | float | Received Signal Strength Indicator (dBm) |
| `sinr` | float | Signal-to-Interference-plus-Noise Ratio (dB) |
| `network_delay` | float | Propagation + link delay (seconds) |
| `attack_pattern` | str | BENIGN, FIRE, C2_SPOOF, c2_downlink |

#### 2. `node_states_{run_id}.csv` (Time-Series Telemetry)

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Simulation time |
| `node_id` | int | Node ID |
| `actual_temperature` | float | True temperature reading |
| `reported_temperature` | float | Transmitted value (may be spoofed) |
| `is_on_fire` | bool | Fire status |
| `heat_level` | float | Normalized heat (0.0-1.0) |
| `is_attacker` | bool | Compromised node flag |
| `attack_triggered` | bool | C2 backdoor active |
| `attack_mode` | str | None, C2_BACKDOOR, DORMANT |

#### 3. `covert_channel_{run_id}.csv` (C2 Activity)

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Event time |
| `node_id` | int | Attacker node |
| `channel_type` | str | c2_udp (uplink), c2_downlink (commands) |
| `message_type` | str | beacon, exfil, command |
| `bit_sequence` | str | Encoded pattern or command type |
| `timing_delay` | float | Modulation delay (seconds) |
| `payload_size` | int | Packet size |

#### 4. `network_metrics_{run_id}.csv` (Performance Stats)

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Measurement time |
| `metric_type` | str | node_signal, global_throughput |
| `value` | float | Metric value |
| `signal_strength` | float | RSSI (dBm) |
| `noise_floor` | float | Background noise (dBm) |

#### 5. `attack_events_{run_id}.csv` (Attack Lifecycle)

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Event time |
| `attack_type` | str | C2_ACTIVATION, SPOOFING |
| `attacker_ids` | list | Active attacker node IDs |

#### 6. `fire_dynamics_{run_id}.csv` (Fire Propagation)

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | float | Sample time |
| `node_id` | int | Node ID |
| `fire_intensity` | float | Normalized intensity |
| `spread_rate` | float | Propagation velocity |

### Dataset Statistics (Typical 240s Run)

- **Total packets**: ~4800
- **Node states**: ~7200 (80 nodes × 90 samples)
- **C2 activity**: ~160 covert events
- **Network metrics**: ~600 samples
- **Fire dynamics**: ~4500 records
- **Total size**: ~2.5 MB per run

---

## ⚙️ Configuration

Edit `classes/Config.py` to customize simulation parameters:

```python
class Config:
    # Grid Topology
    N_ROWS, N_COLS = 8, 10
    ATTACKER_IDS = [25, 26, 34, 36, 45]  # Compromised nodes
    FIRE_NODE_ID = 35  # Fire ignition node

    # Fire Timing
    FIRE_START = 25.0  # Fire ignition time (s)
    FIRE_DURATION = 140.0  # Fire lifetime (s)

    # Temperature Thresholds
    FIRE_TEMP = 85.0  # Fire temperature (°C)
    FIRE_DETECT_THRESH = 55.0  # C2 activation threshold

    # Network Parameters
    DROP_P = 0.03  # 3% packet loss
    SEND_INT = 2.0  # Transmission interval (s)
    JITTER_MAX = 0.08  # Max jitter (s)

    # C2 Backdoor
    C2_BEACON_INT = 2.5  # Beacon interval (s)
    C2_TIMING_DELTA = 0.35  # Timing modulation (s)
    C2_BITSTRING = "10110011..."  # 32-bit pattern
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
    # Edit Config.FIRE_START temporarily or use environment variable
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

**Last Updated**: February 14, 2026
**Framework Version**: 1.0
**Compatible ns-3 Versions**: 3.35+


