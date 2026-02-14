# FIRE-C2 Revision TODO — Ordered Task List
## Mapping Reviewer Comments → Code Edits + Paper Edits

> **Decision**: Reject — Resubmission Allowed (1 resubmission permitted)
> **Strategy**: Code fixes first (they change what you can truthfully claim), then paper rewrites.

---

# PHASE 1 — CODE FIXES (Weeks 1–3)
*These must be done before rewriting paper sections, because the paper must accurately describe the code.*

---

## TASK 1 ✦ Seed Python RNG per-run for reproducibility
**Addresses**: Reviewer 1 (parameter justification), Editor (reproducibility)
**Diagnosed bug**: `main.py` seeds ns-3 via `RngSeedManager.SetSeed(args.seed)` but never calls `random.seed(args.seed)`. All fire dynamics, jitter, drops use uncontrolled Python RNG.

- [ ] **CODE** — `main.py`: Add `random.seed(args.seed)` right after `ns.RngSeedManager.SetSeed(args.seed)` in `run_simulation()`
- [ ] **CODE** — `main.py`: Also add `import numpy as np; np.random.seed(args.seed)` for DataCollector's numpy calls
- [ ] **VERIFY** — Run the same seed twice and diff the output CSVs to confirm identical results

---

## TASK 2 ✦ Hook up real ns-3 network metrics (RSSI, SINR, delay, throughput)
**Addresses**: Reviewer 1 (parameter justification, missing references), Reviewer 2 (experimental detail)
**Diagnosed bug**: All values in `network_metrics_*.csv` and per-packet RSSI/SINR/tx_power/data_rate are `random.uniform()` or hardcoded constants — none come from ns-3.

- [ ] **CODE** — `FireAlarmSimulation.py`: Install ns-3 `FlowMonitor` in `_setup_infrastructure()` for per-flow delay/throughput/loss
- [ ] **CODE** — `FireAlarmSimulation.py`: Attach PHY-layer trace sources (`MonitorSnifferRx`, `PhyRxDrop`) to extract real RSSI and SINR per received packet
- [ ] **CODE** — `FireAlarmSimulation.py`: Hook MAC-layer traces (`MacTx`, `MacRx`, `MacTxDrop`) for retransmission counts and collision data
- [ ] **CODE** — `FireAlarmSimulation.py`: In `_handle_transmission()`, pass real `rssi`, `sinr`, `tx_power`, `data_rate` to `record_packet()` instead of relying on defaults
- [ ] **CODE** — `FireAlarmSimulation.py`: Replace `_schedule_network_metrics()` random values with FlowMonitor stats queries
- [ ] **CODE** — `FireAlarmSimulation.py`: Compute real `network_delay` per packet from TX/RX timestamp difference (not `random.uniform(0.001, 0.01)`)
- [ ] **CODE** — `DataCollector.py`: Remove hardcoded defaults for `rssi=-80`, `sinr=20`, `tx_power=15`, `data_rate=54` — require callers to provide values or mark as NaN
- [ ] **VERIFY** — Check that RSSI varies by node distance from AP (near nodes should have stronger signal)

---

## TASK 3 ✦ Give each attacker its own CovertChannel bit index
**Addresses**: Reviewer 1 (C2 channel design criticism)
**Diagnosed bug**: One global `CovertChannel` instance shares `self.idx` across all 5 attackers — bits interleave rather than cycling independently per node.

- [ ] **CODE** — `FireAlarmSimulation.py`: In `_setup_infrastructure()`, create a per-attacker `CovertChannel` instance: `node.covert_channel = CovertChannel(Config.C2_BITSTRING, Config.C2_TIMING_DELTA)`
- [ ] **CODE** — `FireAlarmSimulation.py`: In `_handle_c2_communication()`, replace `self._covert_channel` with `node.covert_channel`
- [ ] **CODE** — `FireAlarmSimulation.py`: In `_handle_c2_packet()` (cloud-side decode), use a per-node decoder or stateless decode (already stateless for LSB, but timing decode needs care)
- [ ] **VERIFY** — Check covert_channel CSV: each node should cycle bits 0–31 independently

---

## TASK 4 ✦ Fix beacon timing to match paper's Eq. (8)
**Addresses**: Reviewer 1 (C2 timing channel lacks novelty / design critique)
**Diagnosed bug**: `next_delay()` returns 0.0 or 0.35s (just the modulation offset). When bit=0, beacon fires at delay=0.0 (same timestamp as regular TX — trivially detectable "double-send"). The paper's Eq. (8) says `Δt = δ_base + b_i · δ_timing`.

- [ ] **CODE** — `CovertChannel.py`: Change `next_delay()` to return `C2_BEACON_INT + (self.dt if bit else 0.0) + random.uniform(-jitter, jitter)` — OR keep it as modulation-only but fix the scheduling
- [ ] **CODE** — `FireAlarmSimulation.py`: If keeping modulation-only `next_delay()`, then schedule the beacon with `ns.Simulator.Schedule(ns.Seconds(C2_BEACON_INT + delay + jitter), ...)` instead of `ns.Seconds(delay)` alone
- [ ] **CODE** — Remove the separate `node.next_c2_beacon` reschedule logic since timing is now self-contained in the scheduled event
- [ ] **VERIFY** — Check covert_channel CSV: inter-beacon gaps should be ~2.5s ± 0.35s ± 0.2s, never 0.0s

---

## TASK 5 ✦ Add jitter to exfiltration scheduling
**Addresses**: Reviewer 1 (C2 channel stealth critique)
**Diagnosed bug**: `node.next_exfil = sim_time + max(1.0, C2_EXFIL_PERIOD)` — no jitter, strictly periodic at 6.0s.

- [ ] **CODE** — `FireAlarmSimulation.py` line ~560: Change to `node.next_exfil = sim_time + max(1.0, C2_EXFIL_PERIOD + random.uniform(-C2_JITTER, C2_JITTER))`
- [ ] **VERIFY** — Check packets CSV: inter-exfil times should vary, not be exactly 6.0s

---

## TASK 6 ✦ Fix temp_history for attacker and fire nodes
**Addresses**: Reviewer 1 (what data is exfiltrated?)
**Diagnosed bug**: `temp_history.append()` only in the `else` branch of `update_temperature()` — attacker/fire nodes have stale history.

- [ ] **CODE** — `SmartSensor.py`: Move `self.temp_history.append(self.current_temp)` to the end of `update_temperature()`, after all branches, so every node always records its current temp
- [ ] **VERIFY** — After activation, exfil payloads should contain post-activation (spoofed) temperatures, not stale pre-fire values

---

## TASK 7 ✦ Decouple fire spread from SEND_INT
**Addresses**: Reviewer 1 (fire scenario parameters lack references to state-of-the-art)
**Diagnosed bug**: `random.random() < spread_prob * Config.SEND_INT` ties fire physics to the communication interval.

- [ ] **CODE** — `SmartSensor.py`: Replace `Config.SEND_INT` with a dedicated `Config.FIRE_TICK_INTERVAL` (e.g., 1.0s) or normalize spread_prob so it's independent of the calling rate
- [ ] **CODE** — `Config.py`: Add `FIRE_TICK_INTERVAL = 1.0` with a comment citing the fire dynamics model step
- [ ] **VERIFY** — Changing `SEND_INT` should no longer change fire behavior

---

## TASK 8 ✦ Fix cloud sink source-node identification
**Addresses**: Reviewer 2 (experimental details underspecified)
**Diagnosed bug**: Source node identified by temperature matching with 5°C tolerance — unreliable when multiple nodes have similar temps.

- [ ] **CODE** — `FireAlarmSimulation.py`: Embed node_id in the first 2 bytes of every regular payload (e.g., `struct.pack("<H", node.id) + payload`)
- [ ] **CODE** — `SmartSensor.py`: Modify `generate_payload()` to prepend a 2-byte node ID header
- [ ] **CODE** — `FireAlarmSimulation.py`: In `_setup_cloud_sink()`, extract `node_id = struct.unpack("<H", buffer[0:2])[0]` instead of temperature matching
- [ ] **VERIFY** — Every RX_CLOUD packet should have the correct source node_id

---

## TASK 9 ✦ Implement downlink C2 command channel (bidirectionality)
**Addresses**: Reviewer 1 (C2 channel is one-way, should be bidirectional — strongest technical objection)

- [ ] **CODE** — `Config.py`: Add `C2_CMD_PORT = 4445`, `C2_CMD_INTERVAL = 15.0`, `C2_CMD_JITTER = 1.0`
- [ ] **CODE** — `FireAlarmSimulation.py`: In `_setup_infrastructure()`, create a UDP socket on the cloud node that sends to each attacker's STA
- [ ] **CODE** — `FireAlarmSimulation.py`: Add `_schedule_c2_commands()` method: cloud periodically sends encoded command packets (e.g., "increase exfil rate", "go dormant") to each active attacker via timing-modulated intervals
- [ ] **CODE** — `SmartSensor.py`: Add `_handle_c2_command()` callback that processes incoming commands and adjusts behavior (e.g., changes exfil period)
- [ ] **CODE** — `DataCollector.py`: Record downlink C2 events in covert_channel CSV with `direction="downlink"`
- [ ] **CODE** — `CovertChannel.py`: Add `build_command_payload()` and `decode_command()` methods
- [ ] **VERIFY** — covert_channel CSV should show both "beacon"/"exfil" (uplink) and "command" (downlink) message types

---

## TASK 10 ✦ Clean up dead code and commented-out versions
**Addresses**: Editor (framework release), Reviewer 2 (reproducibility)

- [ ] **CODE** — `Config.py`: Remove all three commented-out Config class versions, keep only the active one
- [ ] **CODE** — `main.py`: Remove both commented-out `__main__` versions
- [ ] **CODE** — `FireAlarmSimulation.py`: Remove commented-out `_setup_cloud_sink()` (lines 591–664) and commented-out `run()` (lines 823–865)
- [ ] **CODE** — `SmartSensor.py`: Remove commented-out temperature priority block (lines around the `# if self.on_fire:` section)
- [ ] **CODE** — `SmartSensor.py`: Remove dead method `generate_c2_payload()` (never called)
- [ ] **CODE** — `FireAlarmSimulation.py`: Remove dead method `_record_covert_activity()` (never called)
- [ ] **CODE** — `NodeStats.py`: Remove `seq_c2` (never incremented) or wire it up
- [ ] **CODE** — `Config.py`: Remove `COAL_PATTERN` (coalition leftover)
- [ ] **CODE** — Remove `MobilityConfig.py` entirely (unused)
- [ ] **CODE** — `DataCollector.py`: Remove coalition_events_file creation if coalition logic is gone

---

## TASK 11 ✦ Remove or compute fabricated fields
**Addresses**: Reviewer 1 (justification), code integrity

- [ ] **CODE** — `DataCollector.py`: Remove `stealth_score` and `detection_risk` from covert channel schema (hardcoded magic numbers, not computed)
- [ ] **CODE** — `DataCollector.py`: Either implement battery drain simulation or remove `battery_level` from node state schema (always 100)
- [ ] **CODE** — `DataCollector.py`: Either implement sensor degradation or remove `sensor_health` from node state schema (always 1.0)
- [ ] **CODE** — `CovertChannel.py`: Change padding from `bytes([node.id & 0xFF])` to `bytes([0x00])` or random bytes (current padding leaks node ID)

---

## TASK 12 ✦ Fix memory and performance issues
**Addresses**: Practical framework usability for 250-run generation

- [ ] **CODE** — `DataCollector.py`: Stop dual-writing (remove in-memory lists or clear them periodically). Compute summary stats from file or running counters instead.
- [ ] **CODE** — `DataCollector.py`: Use a buffered CSV writer (open file once, flush periodically) instead of open/write/close per row
- [ ] **CODE** — `FireAlarmSimulation.py`: Periodically clear `self._event_refs` (old callbacks are no longer needed once fired)
- [ ] **CODE** — `FireAlarmSimulation.py`: Reduce print verbosity — remove per-packet `[CLOUD] Received temp` and `Node{id} → Cloud` prints (80 nodes × ~120 TX each = ~9600 prints per run)

---

## TASK 13 ✦ Improve node state sampling
**Addresses**: Reviewer 2 (experimental details)
**Diagnosed issue**: Only 4 nodes sampled per cycle; each node sampled every ~8s despite TX every ~2s.

- [ ] **CODE** — `FireAlarmSimulation.py`: In `_schedule_node_state_collection()`, sample ALL 80 nodes each cycle (the per-TX recording in `_handle_transmission` already exists, so either remove the separate sampling loop or make it comprehensive)
- [ ] **CODE** — Alternatively, remove the separate sampling loop entirely and rely solely on the per-TX node state recording for simplicity
- [ ] **VERIFY** — node_states CSV should have uniform temporal coverage across all nodes

---

## TASK 14 ✦ Fix validation-test.py
**Addresses**: Framework release quality

- [ ] **CODE** — `validation-test.py`: Add `import cppyy` and the `setup_cppyy_callbacks()` call from main.py
- [ ] **CODE** — `validation-test.py`: Update `Config.N_NODES` after changing `N_ROWS`/`N_COLS`
- [ ] **CODE** — `Config.py`: Add a `@classmethod def update_derived(cls)` method that recomputes `N_NODES = N_ROWS * N_COLS` (call after any override)

---

## TASK 15 ✦ Regenerate the dataset with all fixes
**Addresses**: All reviewers (the released dataset must match the revised paper)

- [ ] **CODE** — `generate_dataset.sh`: Add `set -e` for error handling, add logging of failed runs
- [ ] **CODE** — `generate_dataset.sh`: Add optional parallelization (`xargs -P $(nproc)`)
- [ ] **RUN** — Execute all 250 runs with the fixed codebase
- [ ] **VERIFY** — Spot-check: RSSI varies by distance, inter-beacon gaps ~2.5s, exfil times have jitter, temp_history updates post-activation, downlink commands appear in covert_channel CSV
- [ ] **VERIFY** — Re-run ML benchmarks on new dataset; update Tables 8–11 with new results

---

# PHASE 2 — PAPER WRITING EDITS (Weeks 3–5)
*Now that the code is fixed, rewrite the paper to match.*

---

## TASK 16 ✦ Reframe contribution as "framework + dataset"
**Addresses**: Editor ("limited generalizability"), Reviewer 1 ("what value beyond one scenario?")

- [ ] **PAPER §I.A (Contribution)**: Rewrite bullet 1 to lead with "open-source configurable framework" rather than "dataset". Add GitHub URL.
- [ ] **PAPER §I.A**: Add a new bullet: "We release the full simulation codebase as an open-source framework, enabling researchers to generate custom datasets by varying topology, attacker count, fire dynamics, covert channel parameters, and wireless conditions."
- [ ] **PAPER §Abstract**: Change "we introduce FIRE-C2, an ns-3–based simulation and dataset generation framework" → emphasize the framework is publicly released and configurable.
- [ ] **PAPER §Title/Abstract**: Consider adding "Open-Source" to signal the framework release.

---

## TASK 17 ✦ Restructure Section II (Background)
**Addresses**: Reviewer 2 ("Background should cover backdoor attacks in IoT/CPS before datasets")

- [ ] **PAPER §II**: Reorder to: (A) Backdoor Attacks in IoT/CPS → (B) Related Backdoor Attack Frameworks & Techniques → (C) IoT Security Datasets → (D) ns-3 Environment → (E) Gap Analysis
- [ ] **PAPER §II.A**: Remove or relocate ML/federated learning discussion that Reviewer 1 flagged as inconsistent — keep only what's directly relevant to IoT backdoors
- [ ] **PAPER §II**: Add a comparison table of *backdoor attack techniques* (not just datasets) showing what FIRE-C2 covers vs. prior work

---

## TASK 18 ✦ Add formal attacker model section
**Addresses**: Reviewer 2 ("Missing formal attacker model section")

- [ ] **PAPER**: Insert new §III-E (or §IV-preamble) titled "Threat Model" containing:
  - Attacker capabilities: compromises N nodes at deployment via supply chain/firmware attack (cite real examples)
  - Attacker goals: covert exfiltration of operational intelligence + persistent C2 access
  - Attacker knowledge: knows network topology, fire detection threshold; does NOT know IDS configuration
  - Trust assumptions: cloud infrastructure is trusted; wireless channel is observable
- [ ] **PAPER**: Explicitly justify that LSB encoding occurs at the compromised node *before* any link-layer encryption, and the C2 server is the intended decoding recipient — so E2E encryption between sensor and cloud does not defeat this channel (addresses Reviewer 1's encryption objection)
- [ ] **PAPER**: Discuss bidirectional C2 — describe the new downlink command channel (from Task 9)

---

## TASK 19 ✦ Justify what data is worth exfiltrating
**Addresses**: Reviewer 1 ("what sensitive data beyond sensor readings?")

- [ ] **PAPER §IV (Attack Model)**: Add a paragraph on exfiltration value:
  - Building occupancy inference from temperature patterns
  - Security system status during emergencies (fire suppression active/inactive)
  - Infrastructure topology mapping (which nodes are neighbors)
  - Using compromised sensors as stepping stones for lateral movement
  - Operational intelligence for planning physical attacks during emergency chaos
- [ ] **PAPER**: Cite 2–3 real-world IoT attack case studies (e.g., Mirai botnet, Stuxnet's sensor manipulation, Target HVAC breach)

---

## TASK 20 ✦ Justify fire-alarm scenario choice
**Addresses**: Reviewer 2 ("fire-alarm scenario choice requires explicit justification"), Editor ("relevance inadequately motivated")

- [ ] **PAPER §I or §III**: Add explicit justification paragraph:
  - Fire alarms are safety-critical (false negatives = lives at risk)
  - Environment-triggered attacks exploit the emergency itself as cover for anomalous traffic
  - Fire-alarm networks are widely deployed, standardized (cite NFPA 72), and increasingly IP-connected
  - The scenario generalizes to any environment-triggered CPS attack (the framework supports other triggers)
- [ ] **PAPER §I (Introduction)**: Add context about IoT environments, consequences, device types as Reviewer 2 requested

---

## TASK 21 ✦ Add parameter justification with references
**Addresses**: Reviewer 1 ("missing justifications for parameter choices"), ("fire scenario parameters lack references")

- [ ] **PAPER §III or §V**: For every Config.py parameter in Table 3, add a citation or rationale:
  - `FIRE_TEMP=85°C`, `FIRE_DURATION=140s`, `FIRE_SPREAD_RATE=0.22` → cite NFPA 72, ISO 7240, or fire simulation literature (e.g., FDS simulations)
  - `DROP_P=0.03`, `JITTER_MAX=0.08`, `SEND_INT=2.0` → cite real WSN deployment studies (e.g., IEEE 802.15.4 or Wi-Fi sensor network measurements)
  - `C2_BEACON_INT=2.5s`, `C2_TIMING_DELTA=0.35s` → justify via covert channel capacity analysis (bits/second = 1/2.5 ≈ 0.4 bps)
  - Uniform jitter → explain it prevents TDMA-like synchronization artifacts unrealistic in CSMA/CA Wi-Fi
  - 5 compromised nodes (6.25%) → cite supply chain attack statistics or APT compromise rates
- [ ] **PAPER Table 2 & 3**: Add a "Justification/Source" column

---

## TASK 22 ✦ Expand experimental details
**Addresses**: Reviewer 2 ("5 compromised nodes sufficient?", "beacon periodicity?", "why 250 runs?")

- [ ] **PAPER §V.A**: Justify 250 runs: cite comparable simulation-based dataset papers (e.g., CIC-IDS uses N runs), discuss statistical stability of packet counts across runs
- [ ] **PAPER §V.A**: Justify 5 attackers: argue 6.25% is within realistic APT penetration ranges; note the framework allows varying this parameter
- [ ] **PAPER §V.A**: Clarify beacon periodicity: ~2.5s ± 0.35s modulation ± 0.2s jitter (now matches the fixed code)
- [ ] **PAPER §V.A**: Specify simulation durations: 150 runs × 240s + 100 runs × 300s, and why two durations (captures different attack lifecycle stages)

---

## TASK 23 ✦ Add parameter sensitivity analysis
**Addresses**: Reviewer 2 ("parameter sensitivity analysis missing")

- [ ] **RUN** — Generate 3 small additional batches varying key parameters:
  - Batch A: 2 attackers vs. 5 vs. 10
  - Batch B: C2_BEACON_INT = 1.5s vs. 2.5s vs. 5.0s
  - Batch C: DROP_P = 0.01 vs. 0.03 vs. 0.10
- [ ] **PAPER §VI (new subsection)**: Add sensitivity analysis table showing how detection accuracy changes across configurations
- [ ] **PAPER**: Discuss which parameters most affect detectability

---

## TASK 24 ✦ Discuss near-perfect ML results critically
**Addresses**: Reviewer 2 ("near-perfect ML results need generalizability discussion")

- [ ] **PAPER §VI.B**: After Table 8, add a paragraph explaining *why* results are perfect: aggregating an entire run compresses the backdoor lifecycle into clearly distinguishable statistics (higher TX count, C2 port usage). This is expected and serves as an upper-bound sanity check.
- [ ] **PAPER §VI.F (Discussion)**: Explicitly state results may not generalize to: fewer attacker transmissions, more benign variability, real-world measurement noise, different topologies
- [ ] **PAPER §VI.E**: For packet-level results, emphasize this is the realistic benchmark — highlight that PR-AUC drops to 0.886 even for RandomForest, showing the covert channel has genuine stealth
- [ ] **PAPER**: Note that real ns-3 metrics (from Task 2) may change the ML results — the updated benchmarks reflect actual network behavior rather than synthetic features

---

## TASK 25 ✦ Add Limitations section
**Addresses**: Reviewer 2 ("no limitations section"), Editor ("generalizability")

- [ ] **PAPER**: Add §VII-D "Limitations" (or fold into §VIII before Future Work):
  - Simulation vs. real-world gap: ns-3 models idealized MAC/PHY; real deployments have interference, hardware variation
  - Single-scenario focus: fire-alarm only (but framework supports other triggers)
  - Fixed topology: grid layout may not represent all building geometries
  - ML model generalizability: models trained on FIRE-C2 may need retraining for different configurations
  - No encryption modeling: the simulation does not implement application-layer encryption (discuss why this is acceptable per the threat model)
  - No real firmware/OS stack: sensor behavior is abstracted, not running real embedded code

---

## TASK 26 ✦ Fix Section II.A ML/FL inconsistencies
**Addresses**: Reviewer 1 ("Section II.A references ML/federated learning inconsistently")

- [ ] **PAPER §II.A**: Remove or refocus paragraphs about federated learning model poisoning — these describe a different threat than FIRE-C2's network-level C2 backdoor
- [ ] **PAPER §II.A**: Keep FL discussion only if you frame it as: "our C2 backdoor could *complement* FL attacks by providing a covert command channel for coordinating poisoned updates"
- [ ] **PAPER §II.A**: Tighten the definition: FIRE-C2 models a *system-level* backdoor (hidden C2 channel), distinct from *model-level* backdoors (poisoned weights). Make this distinction explicit.

---

## TASK 27 ✦ Fix figures and minor formatting
**Addresses**: Reviewer 1 ("COMM label awkward in Figure 2"), Reviewer 2 ("introduction should outline paper structure")

- [ ] **PAPER Fig. 2**: Change "C2 COMM" label to "Covert C2 Channel" or "C2 Uplink / Downlink"
- [ ] **PAPER Fig. 2**: Update figure to show bidirectional C2 (uplink exfil + downlink commands)
- [ ] **PAPER §I**: Add structure paragraph at end of introduction: "The remainder of this paper is organized as follows: Section III presents..."
- [ ] **PAPER §III Fig. 3 (UML)**: Fix typos: "bengign_tx" → "benign_tx", "attcack_triggered" → "attack_triggered", "dalta" → "delta"
- [ ] **PAPER Table 3**: Update parameter values if any changed during code fixes (e.g., if FIRE_TICK_INTERVAL was added)
- [ ] **PAPER Tables 12–17**: Remove columns for fields that were deleted (stealth_score, detection_risk, battery_level, sensor_health) or mark as "reserved for future use"

---

# PHASE 3 — FRAMEWORK RELEASE & RESPONSE LETTER (Week 5–6)

---

## TASK 28 ✦ Prepare GitHub repository
**Addresses**: Editor ("provide flexible framework for others"), Reviewer 1 ("limited value of fixed dataset")

- [ ] **REPO** — Create clean GitHub repo: `FIRE-C2-Framework`
- [ ] **REPO** — Add cleaned code files (all fixes from Phase 1 applied)
- [ ] **REPO** — Write `README.md`: installation (ns-3 + Python bindings), quick start, configuration reference, example custom scenarios
- [ ] **REPO** — Add `examples/` folder with 3 example configurations:
  - `example_small.py` — 4×5 grid, 1 attacker, 60s
  - `example_default.py` — 8×10 grid, 5 attackers, 240s (paper config)
  - `example_custom.py` — different topology, 10 attackers, higher stealth settings
- [ ] **REPO** — Add `LICENSE` (Apache 2.0 or MIT)
- [ ] **REPO** — Add citation file (`CITATION.cff` or `CITATION.bib`)
- [ ] **PAPER §I.A**: Add GitHub URL; **§V**: Reference as the framework release

---

## TASK 29 ✦ Write point-by-point response letter
**Addresses**: All reviewer comments for the resubmission

- [ ] **LETTER** — Create structured response addressing every numbered comment from both reviewers
- [ ] **LETTER** — For each comment: quote the concern, describe what changed (code + paper), reference specific sections/figures/tables
- [ ] **LETTER** — Highlight the 4 major changes upfront: (1) open-source framework release, (2) bidirectional C2, (3) real ns-3 metrics, (4) formal threat model
- [ ] **LETTER** — For Reviewer 1's encryption concern: explain threat model explicitly, reference new §III-E
- [ ] **LETTER** — For Reviewer 1's "C2 is one-way": describe the new downlink command channel
- [ ] **LETTER** — For Editor's generalizability: point to GitHub + sensitivity analysis + limitations section
- [ ] **LETTER** — Thank Reviewer 2 for constructive feedback; enumerate all structural changes made

---

## TASK 30 ✦ Final pre-submission checks

- [ ] **VERIFY** — Paper compiles without errors (LaTeX)
- [ ] **VERIFY** — All tables/figures reference correct (updated) numbers
- [ ] **VERIFY** — Dataset DOI updated on IEEE DataPort with regenerated data
- [ ] **VERIFY** — GitHub repo is public and URL in paper resolves
- [ ] **VERIFY** — Page count within IEEE OJCOMS limits
- [ ] **VERIFY** — No orphan references to removed features (coalition, battery_level, etc.)
- [ ] **VERIFY** — Response letter references correct section/table numbers in revised paper
- [ ] **SUBMIT**

---

# Quick Reference: Reviewer Comment → Task Mapping

| Reviewer Comment | Tasks |
|---|---|
| **Editor**: Limited generalizability | 16, 28 |
| **Editor**: Should provide flexible framework | 16, 28 |
| **Editor**: Attack scenario lacks clarity | 18, 19 |
| **Editor**: Assumptions need justification | 21 |
| **Editor**: Relevance inadequately motivated | 20 |
| **R1**: LSB assumes unencrypted communication | 18 (threat model) |
| **R1**: Timing channel lacks novelty | 4, 9 (bidirectional) |
| **R1**: What sensitive data is exfiltrated? | 19 |
| **R1**: C2 channel is one-way, should be bidirectional | 9 |
| **R1**: Section II.A ML/FL inconsistencies | 26 |
| **R1**: Missing parameter justifications | 21 |
| **R1**: Fire parameters lack references | 7, 21 |
| **R1**: "COMM" label in Figure 2 | 27 |
| **R2**: Introduction needs more context | 20 |
| **R2**: Background should cover backdoor attacks first | 17 |
| **R2**: Fire-alarm choice needs justification | 20 |
| **R2**: Missing formal attacker model | 18 |
| **R2**: 5 compromised nodes sufficient? | 22, 23 |
| **R2**: Beacon periodicity underspecified | 4, 22 |
| **R2**: Why 250 runs? | 22 |
| **R2**: Near-perfect ML results need discussion | 24 |
| **R2**: Parameter sensitivity analysis missing | 23 |
| **R2**: No limitations section | 25 |
| **R2**: Introduction should outline structure | 27 |
| **Code diagnostic**: Fabricated network metrics | 2 |
| **Code diagnostic**: Python RNG unseeded | 1 |
| **Code diagnostic**: Shared covert channel index | 3 |
| **Code diagnostic**: Stale temp_history | 6 |
| **Code diagnostic**: Dead code throughout | 10 |
