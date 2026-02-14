#!/bin/bash
#
# FIRE-C2 Dataset Generation Script
#
# Generates 250 simulation runs with varied RNG seeds for diverse dataset coverage.
# Each run produces 6 CSV files capturing network traffic, node states, C2 activity,
# network metrics, attack events, and fire dynamics.
#
# Output: ~/fire_c2_dataset_TIMESTAMP/ directory with ~625 MB total
# Runtime: ~60 minutes on 4-core system (parallelizable)
#
# Usage:
#   bash generate_dataset.sh [NUM_RUNS] [START_SEED] [PARALLEL_JOBS]
#
# Examples:
#   bash generate_dataset.sh              # 250 runs, seed 1000, 4 parallel jobs
#   bash generate_dataset.sh 100 5000 8   # 100 runs, seed 5000, 8 parallel jobs
#

set -e  # Exit on error

# ============================================================================
# Configuration
# ============================================================================

NUM_RUNS=${1:-250}          # Number of simulation runs
START_SEED=${2:-1000}       # Starting RNG seed
PARALLEL_JOBS=${3:-4}       # Number of parallel simulations
STOP_TIME=240               # Simulation duration (seconds)
OUTPUT_BASE="${HOME}/fire_c2_dataset_$(date +%Y%m%d_%H%M%S)"

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================================
# Validation
# ============================================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FIRE-C2 Dataset Generation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Runs:            $NUM_RUNS"
echo "  Start Seed:      $START_SEED"
echo "  Parallel Jobs:   $PARALLEL_JOBS"
echo "  Simulation Time: ${STOP_TIME}s"
echo "  Output Dir:      $OUTPUT_BASE"
echo ""

# Check ns-3 directory
if [ ! -d "../../build" ]; then
    echo -e "${RED}ERROR: ns-3 not found. Run from ns-3-dev/scratch/version-2/${NC}"
    exit 1
fi

# Check if validation test passes
echo -e "${YELLOW}Running validation test...${NC}"
cd ../../
if ! ./ns3 run "scratch/version-2/classes/validation-test.py" > /tmp/fire_c2_validation.log 2>&1; then
    echo -e "${RED}ERROR: Validation test failed. Check /tmp/fire_c2_validation.log${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Validation passed${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_BASE"

# ============================================================================
# Dataset Generation
# ============================================================================

echo -e "${BLUE}Generating dataset (this will take ~$((NUM_RUNS / PARALLEL_JOBS * 15 / 60)) minutes)...${NC}"
echo ""

# Progress tracking
COMPLETED=0
FAILED=0
START_TIME=$(date +%s)

# Function to run a single simulation
run_simulation() {
    local seed=$1
    local run_id=$2

    local log_file="$OUTPUT_BASE/run_${run_id}_seed${seed}.log"

    if ./ns3 run "scratch/version-2/classes/main.py --stop $STOP_TIME --seed $seed --run $run_id --output $OUTPUT_BASE" > "$log_file" 2>&1; then
        echo -e "${GREEN}✓${NC} Run $run_id (seed $seed) completed"
        rm -f "$log_file"  # Remove log on success
        return 0
    else
        echo -e "${RED}✗${NC} Run $run_id (seed $seed) FAILED (see $log_file)"
        return 1
    fi
}

export -f run_simulation
export OUTPUT_BASE STOP_TIME GREEN RED NC

# Generate runs in parallel using GNU parallel if available, otherwise sequential
if command -v parallel > /dev/null 2>&1; then
    echo "Using GNU parallel for ${PARALLEL_JOBS}x speedup"
    seq 0 $((NUM_RUNS - 1)) | parallel -j $PARALLEL_JOBS --bar "run_simulation \$((START_SEED + {})) {}"
    COMPLETED=$(find "$OUTPUT_BASE" -name "packets_*.csv" | wc -l)
else
    echo "GNU parallel not found. Running sequentially (install with: sudo apt install parallel)"
    for run_id in $(seq 0 $((NUM_RUNS - 1))); do
        seed=$((START_SEED + run_id))

        run_simulation $seed $run_id

        COMPLETED=$((COMPLETED + 1))

        # Progress indicator
        if ((run_id % 10 == 0)); then
            elapsed=$(($(date +%s) - START_TIME))
            eta=$((elapsed * NUM_RUNS / (run_id + 1) - elapsed))
            echo -e "${BLUE}Progress: $COMPLETED/$NUM_RUNS (ETA: $((eta / 60))m $((eta % 60))s)${NC}"
        fi
    done
fi

# ============================================================================
# Post-Processing & Summary
# ============================================================================

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Count successful runs
COMPLETED=$(find "$OUTPUT_BASE" -name "packets_*.csv" | wc -l)
FAILED=$((NUM_RUNS - COMPLETED))

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Dataset Generation Complete${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Completed: $COMPLETED runs${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}✗ Failed:    $FAILED runs${NC}"
fi
echo "  Duration:    $((ELAPSED / 60))m $((ELAPSED % 60))s"
echo "  Output:      $OUTPUT_BASE"
echo ""

# Dataset statistics
TOTAL_SIZE=$(du -sh "$OUTPUT_BASE" | cut -f1)
NUM_FILES=$(find "$OUTPUT_BASE" -name "*.csv" | wc -l)

echo -e "${YELLOW}Dataset Statistics:${NC}"
echo "  Total Size:  $TOTAL_SIZE"
echo "  CSV Files:   $NUM_FILES"
echo "  Runs:        $COMPLETED"
echo ""

# Create dataset metadata
cat > "$OUTPUT_BASE/README.txt" << EOF
FIRE-C2 Dataset
Generated: $(date)
================================================================================

Configuration:
- Runs: $COMPLETED
- Seeds: $START_SEED to $((START_SEED + NUM_RUNS - 1))
- Simulation Duration: ${STOP_TIME}s per run
- Framework Version: 2.0

Dataset Contents:
- Total CSV Files: $NUM_FILES (6 modalities × $COMPLETED runs)
- Total Size: $TOTAL_SIZE

Modalities per Run:
1. packets_*.csv         - Network traffic (RSSI, SINR, delays, labels)
2. node_states_*.csv     - Node telemetry (temp, fire, attack status)
3. covert_channel_*.csv  - C2 backdoor activity
4. network_metrics_*.csv - Performance statistics
5. attack_events_*.csv   - Attack lifecycle
6. fire_dynamics_*.csv   - Fire propagation data

For usage instructions, see:
https://github.com/YOUR_ORG/fire-c2/blob/main/README.md
EOF

echo -e "${GREEN}Dataset ready at: $OUTPUT_BASE${NC}"
echo ""

# Optional: Create a compressed archive
read -p "Create compressed archive (tar.gz)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ARCHIVE="${OUTPUT_BASE}.tar.gz"
    echo "Creating archive: $ARCHIVE"
    tar -czf "$ARCHIVE" -C "$(dirname "$OUTPUT_BASE")" "$(basename "$OUTPUT_BASE")"
    echo -e "${GREEN}✓ Archive created: $ARCHIVE ($(du -sh "$ARCHIVE" | cut -f1))${NC}"
fi

echo ""
echo -e "${BLUE}Done!${NC}"
