"""
FIRE-C2: Fire Alarm IoT Research Framework with Command & Control Backdoor Analysis

This module implements the main simulation orchestrator for the FIRE-C2 framework,
a research testbed for studying covert Command & Control (C2) channels in IoT
fire alarm systems built on ns-3.

Key Responsibilities:
    - Network Infrastructure Setup: Deploys Wi-Fi grid network with Access Point
      and cloud connectivity (802.11n with realistic propagation models)
    - Smart Sensor Node Creation: Instantiates grid of IoT sensor nodes with
      thermal and network capabilities
    - C2 Backdoor Channel: Implements bidirectional covert communication using
      timing modulation and LSB steganography in temperature telemetry
    - Fire Dynamics Simulation: Models fire spread, heat transfer, and sensor
      response across spatial grid
    - Comprehensive Data Collection: Records network metrics, node states, attack
      events, and covert channel activity for ML/IDS research

Network Topology:
    - Sensor Grid (10.0.0.0/24): N_ROWS × N_COLS nodes connected via 802.11n Wi-Fi
    - Access Point: Central hub with P2P link to cloud (100Mbps, 2ms delay)
    - Cloud Server (10.0.1.0/24): Receives legitimate telemetry (PORT) and C2
      traffic (C2_PORT)
    - Attack Model: Subset of sensors run embedded C2 backdoor triggered by
      temperature threshold

Research Context:
    This is a RESEARCH FRAMEWORK for studying IoT security, specifically analyzing
    how malware can leverage legitimate sensor traffic to hide C2 communications.
    The framework enables dataset generation for training intrusion detection systems.

Copyright (c) 2024-2026 FIRE-C2 Research Project
Licensed under GPL-3.0

Author: Network Security Research Lab
Contact: [Insert research contact]
Version: 2.0
"""

from ns import ns
import random
import struct
import ctypes
import cppyy
import math
from typing import List
from SmartSensor import SmartSensor
from Config import Config
from DataCollector import DataCollector
from CovertChannel import CovertChannel

class FireAlarmSimulation:
    def __init__(self):
        """
        Initialize the Fire Alarm C2 simulation environment.

        Sets up core data structures, initializes covert channel subsystem,
        and constructs the complete network infrastructure with sensor grid,
        access point, and cloud server.

        Attributes:
            nodes: List of SmartSensor objects in spatial grid
            cloud_alarms: Counter for fire alarms received by cloud
            _event_refs: Event callback references to prevent garbage collection
            node_grid: 2D spatial layout of sensor nodes for neighbor calculations
            _covert_channel: Global C2 channel instance for attack coordination
            c2_active: Flag indicating whether any C2 backdoor has activated
            data_collector: Centralized data recording for research datasets
            cloud_alarm_last_t: Timestamp of most recent alarm (for debouncing)
            cloud_alarm_cooldown: Minimum seconds between alarm broadcasts
            packet_tx_times: Maps (node_id, seq) to transmission timestamp for delay calculation
            ap_position: Coordinates of access point for RSSI/SINR computation
        """
        self.nodes: List[SmartSensor] = []
        self.cloud_alarms = 0
        self._event_refs = []
        self.node_grid = [[None for _ in range(Config.N_COLS)]
                         for _ in range(Config.N_ROWS)]

        self._covert_channel = CovertChannel(Config.C2_BITSTRING, Config.C2_TIMING_DELTA)
        self.c2_active = False

        self.data_collector = DataCollector()
        self.cloud_alarm_last_t = -1e9
        self.cloud_alarm_cooldown = 5.0
        self.cloud_alarm_rule = "HOT_FRAC>=0.30 or MEAN>=FIRE_THRESH"

        self.last_sample_index = 0
        self.packet_tx_times = {}
        self.ap_position = None

        self._setup_infrastructure()

    def _compute_rssi_sinr(self, node_position):
        """
        Compute realistic RSSI and SINR based on node distance from access point.

        Uses log-distance path loss model with Nakagami-m fading to match the
        ns-3 propagation configuration (exponent=3.0, m=1.5). Provides accurate
        signal strength metrics for network analysis without requiring FlowMonitor
        (which has Python binding issues).

        Args:
            node_position: Tuple of (x, y, z) coordinates in meters

        Returns:
            Tuple of (rssi_dbm, sinr_db):
                - rssi_dbm: Received signal strength indicator in dBm
                - sinr_db: Signal-to-interference-plus-noise ratio in dB

        Implementation Details:
            - Path loss: PL(d) = PL_0 + 10*n*log10(d/d_0) where n=3.0
            - Fading: Gaussian variation with σ=2dB approximates Nakagami m=1.5
            - Noise floor: -95 dBm (typical for 802.11n in 2.4 GHz band)
            - TX power: 20 dBm (100 mW, standard for Wi-Fi APs)
        """
        if self.ap_position is None:
            return -80.0, 20.0

        dx = node_position[0] - self.ap_position[0]
        dy = node_position[1] - self.ap_position[1]
        distance = math.sqrt(dx*dx + dy*dy)
        distance = max(1.0, distance)

        tx_power_dbm = 20.0
        path_loss_exponent = 3.0
        reference_distance = 1.0
        reference_loss = 40.0

        path_loss = reference_loss + 10 * path_loss_exponent * math.log10(distance / reference_distance)
        rssi = tx_power_dbm - path_loss

        fading_variation = random.gauss(0, 2.0)
        rssi += fading_variation

        noise_floor = -95.0
        sinr_db = rssi - noise_floor

        return rssi, sinr_db
    
    def _setup_infrastructure(self):
        """
        Build complete network infrastructure for Fire Alarm IoT system.

        Creates a realistic three-tier architecture:
        1. IoT Sensor Grid: N_ROWS × N_COLS nodes in spatial layout with 802.11n Wi-Fi
        2. Access Point: Central hub with realistic propagation models
        3. Cloud Server: Connected via dedicated 100Mbps P2P link

        Network Configuration:
            - Wi-Fi subnet: 10.0.0.0/24 (sensors + AP)
            - P2P subnet: 10.0.1.0/24 (AP ↔ cloud)
            - Propagation: Log-distance (exponent=3.0) + Nakagami fading (m=1.5)
            - MAC: 802.11n with Minstrel-HT rate adaptation
            - Node spacing: 15 meters in grid pattern

        Socket Setup:
            - Each sensor → Cloud: UDP socket on Config.PORT (legitimate telemetry)
            - Each attacker → Cloud: UDP socket on Config.C2_PORT (backdoor channel)
            - Cloud → Attackers: Command sockets on Config.C2_CMD_PORT (C2 downlink)

        Attacker Configuration:
            - Attacker IDs specified in Config.ATTACKER_IDS
            - Each attacker receives dedicated CovertChannel instance
            - Backdoor activates upon temperature threshold breach

        Implementation Notes:
            - Uses single node/device creation (no duplicates)
            - AP position stored for RSSI/SINR calculations
            - FlowMonitor disabled due to Python binding issues (position-based metrics used)
        """
        try:
            n_rows = int(getattr(Config, "N_ROWS"))
            n_cols = int(getattr(Config, "N_COLS"))
            n_total = n_rows * n_cols
        except Exception:
            # Fallback: infer from existing nodes (if any)
            n_total = len(getattr(self, "nodes", []))

        # --- Create node containers (only once) ---
        # STAs grid
        self.stas = ns.NodeContainer()
        self.stas.Create(n_total)

        # AP and Cloud singleton nodes
        self.apNode = ns.NodeContainer()
        self.apNode.Create(1)

        self.cloud = ns.NodeContainer()
        self.cloud.Create(1)

        internet = ns.InternetStackHelper()
        internet.Install(self.stas)
        internet.Install(self.apNode)
        internet.Install(self.cloud)


        # ---------------- Wi-Fi: channel/phy/mac/devices ----------------
        channel = ns.YansWifiChannelHelper()
        channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel")
        # Add some realism on losses/fading
        channel.AddPropagationLoss("ns3::LogDistancePropagationLossModel",
                                "Exponent", ns.DoubleValue(3.0))
        channel.AddPropagationLoss("ns3::NakagamiPropagationLossModel",
                                "m0", ns.DoubleValue(1.5))
        
        phy = ns.YansWifiPhyHelper()
        phy.SetChannel(channel.Create())

                
        wifi = ns.WifiHelper()
        try:
            wifi.SetStandard(ns.WIFI_STANDARD_80211n)
        except Exception:
            wifi.SetStandard(getattr(ns, "WIFI_STANDARD_80211n_2_4GHZ", ns.WIFI_STANDARD_80211n))
        wifi.SetRemoteStationManager("ns3::MinstrelHtWifiManager")

        ssid = ns.Ssid("FireNet")
        mac = ns.WifiMacHelper()

        # STA MACs (no active probing)
        mac.SetType("ns3::StaWifiMac",
                    "Ssid", ns.SsidValue(ssid),
                    "ActiveProbing", ns.BooleanValue(False))
        staDevices = wifi.Install(phy, mac, self.stas)

        # AP MAC
        mac.SetType("ns3::ApWifiMac", "Ssid", ns.SsidValue(ssid))
        apDevices = wifi.Install(phy, mac, self.apNode)

        # ---------------- Mobility ---------------

        mobility = ns.MobilityHelper()
        mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel")
        
        # Position nodes in a grid
        positions = ns.ListPositionAllocator()
        for r in range(Config.N_ROWS):
            for c in range(Config.N_COLS):
                idx = r * Config.N_COLS + c
                positions.Add(ns.Vector(c * 15.0, r * 15.0, 0.0))
        
        mobility.SetPositionAllocator(positions)
        mobility.Install(self.stas)

        apMob = ns.MobilityHelper()
        apMob.SetMobilityModel("ns3::ConstantPositionMobilityModel")
        apPos = ns.ListPositionAllocator()

        ap_x = (Config.N_COLS - 1) * 15.0 / 2.0
        ap_y = -10.0
        ap_z = 3.0
        apPos.Add(ns.Vector(ap_x, ap_y, ap_z))
        apMob.SetPositionAllocator(apPos)
        apMob.Install(self.apNode)

        self.ap_position = (ap_x, ap_y, ap_z)

        wifiAddr = ns.Ipv4AddressHelper()
        wifiAddr.SetBase(ns.Ipv4Address("10.0.0.0"), ns.Ipv4Mask("255.255.255.0"))
        staIfaces = wifiAddr.Assign(staDevices)
        apIface   = wifiAddr.Assign(apDevices)


        p2p = ns.PointToPointHelper()
        p2p.SetDeviceAttribute("DataRate", ns.StringValue("100Mbps"))
        p2p.SetChannelAttribute("Delay", ns.StringValue("2ms"))
        p2pDevices = p2p.Install(self.apNode.Get(0), self.cloud.Get(0))

        p2pAddr = ns.Ipv4AddressHelper()
        p2pAddr.SetBase(ns.Ipv4Address("10.0.1.0"), ns.Ipv4Mask("255.255.255.0"))
        cloudIfaces = p2pAddr.Assign(p2pDevices)

        self.CLOUD_IP = cloudIfaces.GetAddress(1)
        self.C2_IP    = self.CLOUD_IP

        ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()

        self.nodes = []
        for r in range(Config.N_ROWS):
            for c in range(Config.N_COLS):
                idx = r * Config.N_COLS + c
                node = SmartSensor(node_id=idx, position=(c * 15.0, r * 15.0, 0.0))
                self.nodes.append(node)
                self.node_grid[r][c] = node

        if Config.C2_ENABLED:
            attacker_ids = getattr(Config, "ATTACKER_IDS", [])

            for i, sensor in enumerate(self.nodes):
                sensor.is_attacker = (i in attacker_ids)
                if sensor.is_attacker:
                    sensor.covert_channel = CovertChannel(Config.C2_BITSTRING, Config.C2_TIMING_DELTA)
        else:
            for sensor in self.nodes:
                sensor.is_attacker = False

        attacker_count = sum(1 for node in self.nodes if node.is_attacker)
        attacker_indices = [i for i, node in enumerate(self.nodes) if node.is_attacker]
        print(f"✅ Successfully configured {attacker_count} attacker nodes: {attacker_indices}")

        self.CLOUD_IP_STR = str(self.CLOUD_IP)
        self.C2_IP_STR    = str(self.C2_IP)

        for idx, sensor in enumerate(self.nodes):
            try:
                sensor.ip = str(staIfaces.GetAddress(idx))
            except Exception:
                sensor.ip = f"10.0.0.{idx+1}"
        if hasattr(self, "nodes") and len(self.nodes) == n_total:
            for idx in range(n_total):
                try:
                    sta = self.stas.Get(idx)
                    data_sock = ns.Socket.CreateSocket(sta, ns.TypeId.LookupByName("ns3::UdpSocketFactory"))
                    data_sock.Connect(ns.InetSocketAddress(self.CLOUD_IP, int(Config.PORT)).ConvertTo())

                    node = self.nodes[idx]
                    setattr(node, "socket", data_sock)

                    if getattr(Config, "C2_ENABLED", True) and getattr(node, "is_attacker", False):
                        c2_sock = ns.Socket.CreateSocket(sta, ns.TypeId.LookupByName("ns3::UdpSocketFactory"))
                        c2_sock.Connect(ns.InetSocketAddress(self.C2_IP, int(Config.C2_PORT)).ConvertTo())
                        setattr(node, "c2_socket", c2_sock)

                        if not hasattr(node, "next_c2_beacon"):
                            node.next_c2_beacon = 2.5 + idx * 0.07
                        if not hasattr(node, "next_exfil"):
                            node.next_exfil = 6.0 + idx * 0.11

                except Exception as e:
                    print(f"[infra] socket setup failed for STA {idx}: {e}")

        self.flow_monitor = None
        print("ℹ️  Using position-based metrics (FlowMonitor disabled due to Python binding issues)")



    def _handle_c2_packet(self, sock):
        """
        Process incoming C2 packets from attacker nodes at the cloud server.

        Decodes covert channel payloads using LSB steganography extraction from
        temperature fields. Records both beacon (heartbeat) and exfil (data theft)
        messages for research analysis.

        Args:
            sock: ns-3 UDP socket receiving C2 traffic on Config.C2_PORT

        Packet Format (EXF protocol):
            - Magic: b'EXF' (3 bytes)
            - Node ID: uint8 (1 byte)
            - Flags: uint8 (1 byte) - 0x80 indicates beacon, 0x00 indicates exfil
            - Temperature: float32 (4 bytes) - LSB encodes covert bit
            - Length: uint16 (2 bytes)
            - Body: variable length payload

        Implementation Details:
            - Uses CovertChannel.decode_lsb() to extract embedded bit
            - Records timestamp, node_id, message_type, and extracted bit value
            - Processes all queued packets in single callback invocation
        """
        sim_time = ns.Simulator.Now().GetSeconds()

        pkt = sock.Recv()
        while pkt:
            size = pkt.GetSize()
            buf = (ctypes.c_ubyte * size)()
            pkt.CopyData(buf, size)
            data = bytes(buf)

            # EXF header: b'EXF' + node_id(1) + flags(1) + temp(float32) + len(uint16) + body
            if size >= 11 and data[:3] == b'EXF':
                node_id = data[3]
                flags   = data[4]
                temp_f  = struct.unpack_from("<f", data, 5)[0]

                # Decode the covert bit from the embedding (LSB of float)
                bit = int(self._covert_channel.decode_lsb(temp_f))
                kind = "BEACON" if (flags & 0x80) else "EXFIL"

                if Config.DATA_COLLECTION_ENABLED:
                    self.data_collector.record_covert_channel(
                        timestamp=sim_time,
                        node_id=node_id,
                        channel_type="c2_reception",
                        message_type=kind.lower(),
                        bit_sequence=getattr(Config, "C2_BITSTRING", ""),  # include pattern for parity
                        lsb_encoded_value=bit,
                        payload_size=size,
                        protocol_used="UDP/EXF"
                    )
            # Pull next queued packet, if any
            pkt = sock.Recv()

    def _schedule_transmissions(self) -> None:
        """
        Schedule initial transmission events for all sensor nodes.

        Staggers node startup with realistic delays to simulate asynchronous
        network initialization. Each node receives independent callback to
        prevent coupling and enable realistic temporal distribution.

        Timing Strategy:
            - Base delay: 1.0 second (network bootstrap)
            - Per-node offset: 0.2 seconds (prevents collision at startup)
            - Random jitter: 0-0.5 seconds (simulates varied boot times)

        Implementation:
            - Creates persistent callback references (prevents garbage collection)
            - Uses ns-3 event scheduler with pythonMakeEvent wrapper
            - Triggers first call to _handle_transmission() for each node
        """
        for node in self.nodes:
            def create_callback(n):
                return lambda: self._handle_transmission(n)

            cb = create_callback(node)
            self._event_refs.append(cb)

            delay = 1.0 + (node.id * 0.2) + random.uniform(0, 0.5)

            ns.Simulator.Schedule(ns.Seconds(delay),
                                ns.cppyy.gbl.pythonMakeEvent(cb))

    def _handle_transmission(self, node: SmartSensor):
        """
        Core transmission handler for individual sensor nodes.

        Orchestrates the complete lifecycle of a sensor transmission cycle including:
        temperature update, fire dynamics, packet generation, C2 backdoor activation,
        and comprehensive data collection.

        Args:
            node: SmartSensor instance triggering this transmission

        Transmission Flow:
            1. Record pre-transmission node state
            2. Check for C2 backdoor activation (temperature-based trigger)
            3. Apply packet loss simulation
            4. Update node temperature and fire dynamics
            5. Generate payload (legitimate or spoofed if attacker)
            6. Send packet via UDP socket
            7. Handle C2 communications if backdoor active
            8. Reschedule next transmission

        C2 Backdoor Activation:
            - Triggers when: is_attacker AND temp > FIRE_DETECT_THRESH AND time >= FIRE_START
            - Sets attack_mode to "C2_BACKDOOR"
            - Enables covert beacon/exfil traffic
            - Records attack activation event

        Data Collection:
            - Node state snapshots (temperature, position, neighbors)
            - Fire dynamics (heat level, spread, intensity)
            - Packet metadata (type, size, direction, RSSI, SINR)
            - Attack events and covert channel activity

        Network Metrics:
            - RSSI/SINR computed via position-based propagation model
            - TX power: 20 dBm (802.11n standard)
            - Data rate: 65 Mbps (MCS7 with Minstrel-HT)
        """
        sim_time = ns.Simulator.Now().GetSeconds()

        if Config.DATA_COLLECTION_ENABLED:
            self.data_collector.record_node_state(
                timestamp=sim_time,
                node=node,
                grid=self.node_grid,
                reported_temp=node.current_temp,
                coalition_active=self.c2_active,
                attack_pattern=node.attack_mode
            )

        if (node.is_attacker and not node.attack_triggered and
            sim_time >= Config.FIRE_START and node.current_temp > Config.FIRE_DETECT_THRESH):
            node.attack_triggered = True
            node.attack_mode = "C2_BACKDOOR"
            self.c2_active = True
            print(f"[C2_ACTIVATION] Node{node.id:02d} backdoor activated at {sim_time:.1f}s")

            if Config.DATA_COLLECTION_ENABLED:
                self.data_collector.record_attack_event(
                    timestamp=sim_time,
                    attack_type="c2_backdoor",
                    attacker_ids=[node.id],
                    duration=0,
                    intensity=1.0,
                    success_rate=1.0,
                    detection_status="undetected",
                    technique="covert_channel",
                    triggers=[f"temperature_threshold_{Config.FIRE_DETECT_THRESH}"]
                )

        if random.random() < Config.DROP_P:
            node.stats.drops += 1
            if Config.DATA_COLLECTION_ENABLED:
                self.data_collector.record_packet(
                    timestamp=sim_time,
                    node_id=node.id,
                    packet_type="DROPPED",
                    direction="tx",
                    size_bytes=0,
                    temperature_value=node.current_temp,
                    is_spoofed=False,
                    attack_pattern=node.attack_mode
                )
            self._reschedule_node(node)
            return

        node.update_temperature(sim_time, self.node_grid)

        if Config.DATA_COLLECTION_ENABLED:
            self.data_collector.record_fire_dynamics(
                timestamp=sim_time,
                node_id=node.id,
                fire_intensity=node.heat_level,                 # 0..1
                neighbor_influence=node.received_heat,          # what it accumulated this tick
                spread_rate=1.0 if node.on_fire else 0.0,       # simple proxy
                ignition_probability=1.0 if node.on_fire else node.heat_level,
                radiative_heat=node.heat_level * 0.6,           # simple split
                convective_heat=node.heat_level * 0.4,
                fuel_remaining=100 - node.heat_level * 100,     # toy model
                suppression_effect=0.0,
                reignition_count=0
            )

        payload, label = node.generate_payload()
        if node.socket:
            try:
                packet_size = len(payload)

                buf = (ctypes.c_ubyte * len(payload))(*payload)
                pkt = ns.Packet(buf, len(payload))
                node.socket.Send(pkt)
                node.stats.seq_tx += 1

                self.packet_tx_times[(node.id, node.stats.seq_tx)] = sim_time

                if node.stats.seq_tx % 50 == 0 or "FIRE" in label or node.is_attacker:
                    print(f"[{sim_time:6.1f}s] Node{node.id:02d} → Cloud ({label}, seq={node.stats.seq_tx})")

                is_spoofed = "SPOOF" in label
                is_c2 = "C2" in label

                rssi, sinr = self._compute_rssi_sinr(node.position)

                # Compute realistic network delay
                dx = node.position[0] - self.ap_position[0]
                dy = node.position[1] - self.ap_position[1]
                dist_m = math.sqrt(dx*dx + dy*dy)
                propagation_delay_s = dist_m / 3e8  # speed of light
                p2p_link_delay_s = 0.002  # configured P2P delay
                jitter_s = random.uniform(0.0001, 0.0005)  # 0.1-0.5ms random jitter
                network_delay = propagation_delay_s + p2p_link_delay_s + jitter_s

                if Config.DATA_COLLECTION_ENABLED:
                    self.data_collector.record_packet(
                        timestamp=sim_time,
                        node_id=node.id,
                        packet_type=label,
                        direction="tx",
                        size_bytes=len(payload),
                        temperature_value=node.current_temp,
                        sequence_number=node.stats.seq_tx,
                        is_spoofed=is_spoofed,
                        attack_pattern=node.attack_mode,
                        network_delay=network_delay,
                        packet_loss=Config.DROP_P * 100,
                        rssi=rssi,
                        sinr=sinr,
                        tx_power=20.0,
                        data_rate=65.0,
                        source_ip=getattr(node, "ip", ""),
                        dest_ip=getattr(self, "CLOUD_IP_STR", ""),
                        protocol="UDP"
                    )

            except Exception as e:
                print(f"Error sending packet from node {node.id}: {e}")
                node.stats.drops += 1

        if node.is_attacker and node.attack_triggered and Config.C2_ENABLED:
            self._handle_c2_communication(node, sim_time)

        self._reschedule_node(node)

    def _handle_c2_communication(self, node: SmartSensor, sim_time: float):
        """
        Execute covert C2 communications for activated attacker nodes.

        Implements dual-channel C2 protocol:
        1. Beacons: Periodic heartbeats with timing modulation
        2. Exfiltration: Sensor data theft with LSB steganography

        Args:
            node: SmartSensor instance with is_attacker=True
            sim_time: Current simulation time in seconds

        Protocol Details:
            - Packet format: 'EXF' header + node_id + flags + temp_LSB + length + data
            - Beacon flag: 0x80 (MSB set)
            - Exfil flag: 0x00
            - Temperature field: float32 with LSB encoding covert bit

        Timing Strategy (Equation 8):
            Δt = δ_base + b_i · δ_timing + jitter
            - δ_base: Config.C2_BEACON_INT (7.5s default)
            - b_i · δ_timing: Covert bit modulation (Config.C2_TIMING_DELTA)
            - jitter: ±Config.C2_JITTER for detection evasion

        Steganography:
            - Uses CovertChannel.build_payload() to embed covert bits
            - Encodes C2_BITSTRING pattern across multiple transmissions
            - LSB manipulation in temperature float provides ~0.01°C deviation
              (below sensor noise floor)

        Scheduling:
            - Beacons: Time-delayed with modulated intervals
            - Exfil: Immediate send, periodic rescheduling
            - Per-node timers: next_c2_beacon, next_exfil

        Data Collection:
            - Records packet metadata (size, timestamp, node_id)
            - Logs covert channel activity (bit value, timing delay)
            - Tracks stealth score and detection risk
        """
        if not getattr(node, "is_attacker", False):
            return
        if not getattr(node, "attack_triggered", False):
            return
        if getattr(node, "c2_socket", None) is None:
            return

        # --- Config fallbacks ---
        C2_BEACON_INT = getattr(Config, "C2_BEACON_INT", 7.5)
        C2_EXFIL_PERIOD = getattr(Config, "C2_EXFIL_PERIOD", 15.0)
        C2_JITTER = getattr(Config, "C2_JITTER", 1.0)

        # --- Ensure next_c2_beacon / next_exfil timers exist on node ---
        if not hasattr(node, "next_c2_beacon"):
            node.next_c2_beacon = sim_time + 2.5 + (node.id * 0.1)
        if not hasattr(node, "next_exfil"):
            node.next_exfil = sim_time + 6.0 + (node.id * 0.11)

        def _raw_beacon():
            on_fire = 1 if getattr(node, "on_fire", False) else 0
            heat = float(getattr(node, "heat_level", 0.0))
            return struct.pack("<fBf", float(node.current_temp), on_fire, heat)

        def _raw_exfil():
            hist = list(getattr(node, "temp_history", []))
            avg = (sum(hist) / len(hist)) if hist else float(node.current_temp)
            on_fire = 1 if getattr(node, "on_fire", False) else 0
            heat = float(getattr(node, "heat_level", 0.0))
            return struct.pack("<fBf", float(avg), on_fire, heat)

        if sim_time >= node.next_c2_beacon:
            raw = _raw_beacon()

            covert_ch = getattr(node, 'covert_channel', self._covert_channel)
            payload = covert_ch.build_payload(node, raw, is_beacon=True)

            delay = covert_ch.next_delay()

            def _send_beacon(n=node, pl=payload, ch=covert_ch):
                try:
                    buf = (ctypes.c_ubyte * len(pl))(*pl)
                    pkt = ns.Packet(buf, len(pl))
                    n.c2_socket.Send(pkt)
                    n.stats.seq_c2 += 1

                    temp_encoded = struct.unpack_from("<f", pl, 5)[0]
                    bit_tx = int(ch.decode_lsb(temp_encoded))

                    if Config.DATA_COLLECTION_ENABLED:
                        rssi, sinr = self._compute_rssi_sinr(n.position)
                        self.data_collector.record_packet(
                            timestamp=ns.Simulator.Now().GetSeconds(),
                            node_id=n.id,
                            packet_type="TX_C2_BEACON",
                            direction="tx_c2",
                            size_bytes=len(pl),
                            temperature_value=float(n.current_temp),
                            is_spoofed=True,
                            attack_pattern="c2",
                            rssi=rssi,
                            sinr=sinr,
                            tx_power=20.0,
                            data_rate=65.0
                        )
                        self.data_collector.record_covert_channel(
                            timestamp=ns.Simulator.Now().GetSeconds(),
                            node_id=n.id,
                            channel_type="c2_udp",
                            message_type="beacon",
                            bit_sequence=getattr(Config, "C2_BITSTRING", ""),
                            timing_delay=delay,
                            lsb_encoded_value=bit_tx,
                            payload_size=len(pl),
                            protocol_used="UDP/EXF"
                        )

                except Exception as e:
                    print(f"[C2] beacon send error (node {n.id}): {e}")

            jitter = random.uniform(-C2_JITTER, C2_JITTER)
            full_delay = C2_BEACON_INT + delay + jitter

            self._event_refs.append(_send_beacon)
            ns.Simulator.Schedule(ns.Seconds(full_delay), ns.cppyy.gbl.pythonMakeEvent(_send_beacon))

            node.next_c2_beacon = sim_time + full_delay

        if sim_time >= node.next_exfil:
            raw = _raw_exfil()

            covert_ch = getattr(node, 'covert_channel', self._covert_channel)
            payload = covert_ch.build_payload(node, raw, is_beacon=False)

            try:
                buf = (ctypes.c_ubyte * len(payload))(*payload)
                pkt = ns.Packet(buf, len(payload))
                node.c2_socket.Send(pkt)
                node.stats.seq_c2 += 1

                if Config.DATA_COLLECTION_ENABLED:
                    temp_encoded = struct.unpack_from("<f", payload, 5)[0]
                    bit_tx = int(covert_ch.decode_lsb(temp_encoded))

                    rssi, sinr = self._compute_rssi_sinr(node.position)
                    self.data_collector.record_packet(
                        timestamp=sim_time,
                        node_id=node.id,
                        packet_type="TX_C2_EXFIL",
                        direction="tx_c2",
                        size_bytes=len(payload),
                        temperature_value=float(node.current_temp),
                        is_spoofed=True,
                        attack_pattern="c2",
                        rssi=rssi,
                        sinr=sinr,
                        tx_power=20.0,
                        data_rate=65.0
                    )
                    self.data_collector.record_covert_channel(
                        timestamp=sim_time,
                        node_id=node.id,
                        channel_type="c2_udp",
                        message_type="exfil",
                        bit_sequence=getattr(Config, "C2_BITSTRING", ""),
                        lsb_encoded_value=bit_tx,
                        payload_size=len(payload),
                        protocol_used="UDP/EXF"
                    )

            except Exception as e:
                print(f"[C2] exfil send error (node {node.id}): {e}")

            node.next_exfil = sim_time + max(1.0, C2_EXFIL_PERIOD + random.uniform(-C2_JITTER, C2_JITTER))

    def _reschedule_node(self, node: SmartSensor):
        """
        Reschedule next transmission event for a sensor node.

        Implements jittered periodic transmissions to simulate realistic sensor
        behavior and prevent artificial synchronization artifacts.

        Args:
            node: SmartSensor instance to reschedule

        Timing Strategy:
            - Base interval: Config.SEND_INT (typically 5-10 seconds)
            - Jitter: ±Config.JITTER_MAX (prevents network storms)
            - Minimum interval: 0.1 seconds (safety bound)

        Memory Management:
            - Maintains event reference list to prevent Python GC issues
            - Periodically trims _event_refs when size exceeds 1000 (keeps last 500)
            - Critical for long-duration simulations (prevents memory leak)

        Implementation:
            - Creates closure to capture node reference
            - Schedules via ns-3 event system with pythonMakeEvent wrapper
        """
        jitter = random.uniform(-Config.JITTER_MAX, Config.JITTER_MAX)
        next_time = max(0.1, Config.SEND_INT + jitter)

        def create_callback(n):
            return lambda: self._handle_transmission(n)

        cb = create_callback(node)
        self._event_refs.append(cb)

        ns.Simulator.Schedule(ns.Seconds(next_time),
                            ns.cppyy.gbl.pythonMakeEvent(cb))

    def _setup_cloud_sink(self) -> None:
        """
        Set up cloud-side packet reception for legitimate sensor telemetry.

        Creates UDP sink socket listening on Config.PORT to receive temperature
        readings from all sensor nodes. Implements fire detection logic based on
        temperature thresholds.

        Socket Configuration:
            - Listens on: 0.0.0.0:Config.PORT (typically 9000)
            - Protocol: UDP (unreliable, simulates real IoT)
            - Callback: PythonRecvTrampoline (cppyy bridge for Python callbacks)

        Packet Processing:
            - Extracts node_id from first 2 bytes (header)
            - Reads temperature value from bytes 2-6 (float32)
            - Triggers fire alarms based on Config.FIRE_THRESH
            - Records all received packets if DATA_COLLECTION_ENABLED

        Fire Detection Thresholds:
            - FIRE_THRESH: Critical alarm (🚨)
            - FIRE_DETECT_THRESH: Warning level (⚠️)

        Data Collection:
            - Packet metadata (timestamp, size, node_id)
            - Temperature readings
            - Source/destination IPs
            - Protocol information

        Implementation Notes:
            - Processes all queued packets in single callback (while loop)
            - Robust error handling for malformed packets
            - Uses ns-3 cppyy bindings for Python-C++ interop
        """
        def packet_received(socket):
            try:
                packet = socket.Recv()
                while packet:
                    if packet.GetSize() > 0:
                        sim_time = ns.Simulator.Now().GetSeconds()

                        buffer = bytearray(packet.GetSize())
                        packet.CopyData(buffer, packet.GetSize())

                        source_node_id = -1
                        temp_val = None
                        if len(buffer) >= 2:
                            source_node_id = struct.unpack('<H', buffer[0:2])[0]

                        if len(buffer) >= 6:
                            temp_val = struct.unpack('f', buffer[2:6])[0]

                        if temp_val is not None:
                            if temp_val >= Config.FIRE_THRESH:
                                self.cloud_alarms += 1
                                print(f"🚨 FIRE ALARM at {sim_time:.1f}s (Temp: {temp_val:.1f}°C)")
                            elif temp_val > Config.FIRE_DETECT_THRESH:
                                print(f"⚠️  Fire detected at {sim_time:.1f}s (Temp: {temp_val:.1f}°C)")

                            if Config.DATA_COLLECTION_ENABLED:
                                self.data_collector.record_packet(
                                    timestamp=sim_time,
                                    node_id=source_node_id,
                                    packet_type="RX_CLOUD",
                                    direction="rx",
                                    size_bytes=packet.GetSize(),
                                    temperature_value=temp_val,
                                    sequence_number=-1,
                                    source_ip="",
                                    dest_ip=getattr(self, "CLOUD_IP_STR", ""),
                                    protocol="UDP",
                                    is_spoofed=False,
                                    attack_pattern="None"
                                )

                    packet = socket.Recv()

            except Exception as e:
                print(f"Error processing packet in cloud sink: {e}")
        self.cloud_sink_socket = ns.Socket.CreateSocket(
            self.cloud.Get(0), ns.UdpSocketFactory.GetTypeId()
        )
        local_addr = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), int(Config.PORT)).ConvertTo()
        self.cloud_sink_socket.Bind(local_addr)

        ns.cppyy.gbl._py_recv = packet_received
        self.cloud_sink_socket.SetRecvCallback(
            ns.MakeCallback(ns.cppyy.gbl.PythonRecvTrampoline)
        )

        print(f"✅ Cloud sink setup complete - listening on port {Config.PORT}")

    def _setup_c2_sink(self) -> None:
        """
        Set up cloud-side uplink C2 receiver for attacker traffic.

        Creates UDP sink socket listening on Config.C2_PORT to receive covert
        C2 communications (beacons and exfiltration) from compromised nodes.
        This simulates a malicious server controlled by the attacker.

        Socket Configuration:
            - Listens on: 0.0.0.0:Config.C2_PORT (typically 4444)
            - Protocol: UDP (covert channel transport)
            - Callback: PythonRecvTrampolineC2 (dedicated C2 callback)

        Processing:
            - Delegates to _handle_c2_packet() for payload decoding
            - Extracts LSB-encoded bits from temperature fields
            - Records beacon/exfil messages for research analysis

        Security Note:
            This represents the ATTACKER-controlled infrastructure. In a real
            deployment, this would be an external C2 server. Here it's co-located
            with the cloud for simulation purposes.
        """
        self.c2_sink_socket = ns.Socket.CreateSocket(
            self.cloud.Get(0), ns.TypeId.LookupByName("ns3::UdpSocketFactory")
        )
        self.c2_sink_socket.Bind(
            ns.InetSocketAddress(ns.Ipv4Address.GetAny(), int(Config.C2_PORT)).ConvertTo()
        )
        ns.cppyy.gbl._py_recv_c2 = self._handle_c2_packet
        self.c2_sink_socket.SetRecvCallback(
            ns.MakeCallback(ns.cppyy.gbl.PythonRecvTrampolineC2)
        )


    def _schedule_network_metrics(self):
        """
        Schedule periodic collection of network performance metrics.

        Samples global network statistics and per-node signal strength for research
        dataset generation. Uses position-based RSSI/SINR calculations instead of
        FlowMonitor (which has Python binding issues).

        Metrics Collected:
            Global (if FlowMonitor available):
                - Throughput (Mbps): Total network capacity utilization
                - Latency (ms): Average end-to-end delay
                - Packet loss rate (%): Fraction of dropped packets
                - Channel utilization (%): Relative to 802.11n MCS7 (65 Mbps)

            Per-Node Sampling:
                - RSSI (dBm): Received signal strength at random subset of nodes
                - SINR (dB): Signal quality metric
                - Noise floor: -95 dBm reference

        Sampling Strategy:
            - Interval: Config.NETWORK_METRICS_SAMPLE_RATE (typically 1-5 seconds)
            - Node sampling: 5 random nodes per cycle (reduces overhead)
            - First sample: 5 seconds into simulation (allow network stabilization)

        Implementation Notes:
            - FlowMonitor fallback: Gracefully handles binding failures
            - Position-based metrics: Equally realistic for signal strength
            - Recursive scheduling: Maintains periodic collection throughout simulation
        """
        def collect_metrics():
            sim_time = ns.Simulator.Now().GetSeconds()

            if Config.DATA_COLLECTION_ENABLED:
                # FlowMonitor section (disabled, flow_monitor=None)
                if self.flow_monitor is not None:
                    try:
                        # Query FlowMonitor stats
                        classifier = ns.Ipv4FlowClassifierHelper.GetClassifier(self.flow_monitor.GetClassifier())
                        stats = self.flow_monitor.GetFlowStats()

                        total_throughput = 0.0
                        total_delay = 0.0
                        total_packets = 0
                        total_lost = 0

                        for flow_id, flow_stats in stats.items():
                            if flow_stats.rxPackets > 0:
                                # Real throughput (bits/sec)
                                throughput = (flow_stats.rxBytes * 8.0) / max(0.001, sim_time)
                                total_throughput += throughput / 1e6  # Convert to Mbps

                                # Real delay (ms)
                                avg_delay_sec = flow_stats.delaySum.GetSeconds() / flow_stats.rxPackets
                                total_delay += avg_delay_sec * 1000  # Convert to ms

                                total_packets += flow_stats.txPackets
                                total_lost += flow_stats.lostPackets

                        # Compute averages
                        num_flows = len(stats) if len(stats) > 0 else 1
                        avg_throughput = total_throughput / num_flows if num_flows > 0 else 0.0
                        avg_latency = total_delay / num_flows if num_flows > 0 else 2.0
                        loss_rate = (total_lost / max(1, total_packets)) * 100 if total_packets > 0 else 0.0

                        self.data_collector.record_network_metrics(
                            timestamp=sim_time,
                            metric_type="global_throughput",
                            value=avg_throughput,
                            throughput_mbps=avg_throughput,
                            latency_ms=avg_latency,
                            packet_loss_rate=loss_rate,
                            utilization_percent=min(100, avg_throughput / 0.65)
                        )

                    except Exception as e:
                        print(f"[WARN] FlowMonitor query failed: {e}")
                        pass

                # Per-node RSSI sampling (always runs)
                try:
                    for node_id in random.sample(range(len(self.nodes)), min(5, len(self.nodes))):
                        node = self.nodes[node_id]
                        rssi, sinr = self._compute_rssi_sinr(node.position)
                        self.data_collector.record_network_metrics(
                            timestamp=sim_time,
                            metric_type="node_signal",
                            value=rssi,
                            node_id=node_id,
                            signal_strength=rssi,
                            noise_floor=-95.0
                        )
                except Exception as e:
                    print(f"[WARN] Per-node metrics sampling failed: {e}")

            self._event_refs.append(collect_metrics)
            ns.Simulator.Schedule(
                ns.Seconds(Config.NETWORK_METRICS_SAMPLE_RATE),
                ns.cppyy.gbl.pythonMakeEvent(collect_metrics)
            )

        self._event_refs.append(collect_metrics)
        ns.Simulator.Schedule(
            ns.Seconds(5.0),
            ns.cppyy.gbl.pythonMakeEvent(collect_metrics)
        )

    def _schedule_node_state_collection(self):
        """
        Schedule periodic collection of comprehensive node state snapshots.

        Samples ALL sensor nodes each cycle to provide complete temporal coverage
        of fire dynamics, network state, and attack progression. Critical for
        ML/IDS training datasets.

        Data Collected Per Node:
            - Timestamp and node ID
            - Current temperature reading
            - Spatial position (x, y, z)
            - Fire state (on_fire, heat_level)
            - Neighbor temperatures (grid context)
            - Coalition status (c2_active flag)
            - Attack pattern (C2_BACKDOOR, DORMANT, None)

        Sampling Strategy:
            - Frequency: Config.NODE_STATE_SAMPLE_RATE (typically 0.5-1.0 seconds)
            - Coverage: 100% of nodes (not sampled - ALL nodes each cycle)
            - First sample: 2 seconds into simulation
            - Continues until simulation end

        Research Rationale:
            Full node coverage enables:
            - Spatial fire spread analysis
            - Attack correlation across multiple nodes
            - Temporal pattern detection
            - Complete ground truth for supervised learning

        Performance Note:
            With 80 nodes @ 1Hz = 80 records/sec = ~5KB/sec (manageable overhead)
        """
        def collect_node_states():
            sim_time = ns.Simulator.Now().GetSeconds()

            if Config.DATA_COLLECTION_ENABLED:
                for node in self.nodes:
                    self.data_collector.record_node_state(
                        sim_time, node, self.node_grid,
                        coalition_active=self.c2_active,
                        attack_pattern=node.attack_mode
                    )

            self._event_refs.append(collect_node_states)
            ns.Simulator.Schedule(
                ns.Seconds(Config.NODE_STATE_SAMPLE_RATE),
                ns.cppyy.gbl.pythonMakeEvent(collect_node_states)
            )

        self.last_sample_index = 0
        self._event_refs.append(collect_node_states)
        ns.Simulator.Schedule(
            ns.Seconds(2.0),
            ns.cppyy.gbl.pythonMakeEvent(collect_node_states)
        )

    def _schedule_c2_commands(self):
        """
        Schedule periodic downlink C2 commands from cloud to attackers.

        Uses direct state manipulation (simulation-level injection) rather than
        ns-3 sockets. This is a valid modeling choice since the C2 controller
        and compromised nodes are in the same Python process.
        """
        self._c2_cmd_counter = 0


        def send_commands_wrapper():
            self._send_c2_command()


        self._event_refs.append(send_commands_wrapper)
        ns.Simulator.Schedule(ns.Seconds(20.0), ns.cppyy.gbl.pythonMakeEvent(send_commands_wrapper))

    def _send_c2_command(self):
        """Execute and schedule C2 downlink commands"""
        sim_time = ns.Simulator.Now().GetSeconds()

        if sim_time > Config.FIRE_START + 10.0:
            active = [n for n in self.nodes if n.is_attacker and n.attack_triggered]
            if active:
                target = random.choice(active)
                cmd_type = random.choice(['increase_exfil', 'decrease_exfil', 'go_dormant', 'resume'])

                # Execute command directly (simulation-level injection)
                if cmd_type == 'increase_exfil':
                    target.next_exfil = sim_time + 3.0
                elif cmd_type == 'decrease_exfil':
                    target.next_exfil = sim_time + 12.0
                elif cmd_type == 'go_dormant':
                    target.attack_mode = "DORMANT"
                elif cmd_type == 'resume':
                    if target.attack_mode == "DORMANT":
                        target.attack_mode = "C2_BACKDOOR"

                # Record downlink command in dataset
                if Config.DATA_COLLECTION_ENABLED:
                    self.data_collector.record_covert_channel(
                        timestamp=sim_time,
                        node_id=target.id,
                        channel_type="c2_downlink",
                        message_type="command",
                        bit_sequence=cmd_type,
                        payload_size=32,
                        protocol_used="SIMULATED_CMD"
                    )
                    self.data_collector.record_packet(
                        timestamp=sim_time,
                        node_id=-1,
                        packet_type="TX_C2_CMD",
                        direction="tx_c2_cmd",
                        size_bytes=32,
                        temperature_value=0.0,
                        is_spoofed=False,
                        attack_pattern="c2_downlink"
                    )

        # Schedule next command
        next_t = Config.C2_CMD_INTERVAL + random.uniform(-Config.C2_CMD_JITTER, Config.C2_CMD_JITTER)

        def next_cmd_wrapper():
            self._send_c2_command()


        self._event_refs.append(next_cmd_wrapper)
        ns.Simulator.Schedule(ns.Seconds(next_t), ns.cppyy.gbl.pythonMakeEvent(next_cmd_wrapper))

    def run(self) -> None:
        """
        Execute the complete simulation lifecycle.

        Orchestrates all simulation phases from initialization through execution
        to data collection and cleanup. Entry point for running Fire Alarm C2
        research scenarios.

        Execution Flow:
            1. Generate run_id (timestamp-based unique identifier)
            2. Initialize data collection files
            3. Schedule all event categories:
               - Node transmissions (staggered startup)
               - Cloud/C2 packet reception sinks
               - Network metrics collection
               - Node state snapshots
               - C2 command scheduling (if enabled)
            4. Populate routing tables
            5. Execute ns-3 event loop (runs until Config.STOP_TIME)
            6. Generate summary reports
            7. Clean up simulator state

        Error Handling:
            - Try-except around simulation execution
            - Graceful fallback for routing table population
            - Always destroys simulator in finally block (prevents state pollution)

        Data Collection:
            - Writes packet_data.csv, node_states.csv, etc.
            - Generates summary report with:
              * Total packets recorded
              * Total node states
              * Simulation time (ns-3 virtual seconds)
              * Wall-clock execution time

        Prints Statistics:
            - Benign vs malicious packet counts
            - Dropped packets
            - Fire alarms triggered
            - Packet accounting validation

        Returns:
            None (side effects: CSV files written, console output)
        """
        if not hasattr(self, 'run_id') or not self.run_id:
            import time as _t
            self.run_id = f"{_t.strftime('%Y%m%d_%H%M%S')}"

        self.data_collector.init_data_files(self.run_id, output_dir=Config.DATA_OUTPUT_DIR)

        self.verbose = False

        try:
            self._schedule_transmissions()
            self._setup_cloud_sink()
            self._setup_c2_sink()
            if getattr(Config, "C2_ENABLED", False):
                self._schedule_c2_commands()
            self._schedule_network_metrics()
            self._schedule_node_state_collection()

            try:
                ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()
            except Exception as e:
                print(f"Routing table warning: {e}")

            ns.Simulator.Stop(ns.Seconds(Config.STOP_TIME))

            print(f"Starting simulator run (stop time: {Config.STOP_TIME}s)...")
            ns.Simulator.Run()

            sim_end = ns.Simulator.Now().GetSeconds()
            print(f"Simulator finished at {sim_end}s")

        except Exception as e:
            print(f"Error during simulation execution: {e}")
            raise
        finally:
            try:
                ns.Simulator.Destroy()
                print("Simulator destroyed")
            except Exception as e:
                print(f"Warning during simulator destruction: {e}")

        if Config.DATA_COLLECTION_ENABLED:
            self.data_collector.sim_time_end_seconds = float(sim_end)
            summary = self.data_collector.generate_summary_report()
            print("\n=== DATASET SUMMARY ===")
            print(f"Total packets recorded: {summary['total_packets']}")
            print(f"Total node states: {summary['total_node_states']}")
            print(f"NS-3 sim time:       {summary['sim_time_seconds']:.2f}s")
            print(f"Wall-clock elapsed:  {summary['wall_clock_seconds']:.2f}s")

        self._print_stats()

    def _print_stats(self) -> None:
        """
        Print comprehensive simulation statistics and validation metrics.

        Outputs final performance summary including:
        - Packet transmission counts (benign/malicious/dropped)
        - Fire alarm triggers
        - Data collection validation (packet accounting)

        Validation Logic:
            - Compares transmitted packets (benign + malicious + drops) against
              total recorded packets
            - Accounts for RX packets (cloud-side reception) and C2 traffic
            - Reports accounting discrepancies for debugging

        Console Output:
            - Simulation Statistics: Transmission/alarm counts
            - Simple Validation: Packet count reconciliation
            - Success/failure indicators (✅/❌)
        """
        total_benign = sum(n.stats.benign_tx for n in self.nodes)
        total_malicious = sum(n.stats.malicious_tx for n in self.nodes)
        total_drops = sum(n.stats.drops for n in self.nodes)

        print(f"\n─── Simulation Statistics ───")
        print(f"Benign packets:    {total_benign:6d}")
        print(f"Malicious packets: {total_malicious:6d}")
        print(f"Dropped packets:   {total_drops:6d}")
        print(f"Cloud alarms:      {self.cloud_alarms:6d}")

        if Config.DATA_COLLECTION_ENABLED:
            recorded_packets = len(self.data_collector.packet_data)

            calculated_total_tx = total_benign + total_malicious + total_drops

            print(f"\n─── Simple Validation ───")
            print(f"Calculated TX packets: {calculated_total_tx}")
            print(f"Recorded packets:      {recorded_packets}")
            print(f"Difference:            {abs(calculated_total_tx - recorded_packets)}")

            rx_count = sum(1 for d in self.data_collector.packet_data
                        if d.get('direction') == 'rx')
            c2_count = sum(1 for d in self.data_collector.packet_data
                        if d.get('direction') == 'tx_c2')

            expected_difference = rx_count + c2_count
            actual_difference = recorded_packets - calculated_total_tx

            if actual_difference == expected_difference:
                print("✅ Packet accounting correct (difference = RX + C2 packets)")
            else:
                print(f"❌ Unexplained difference: {actual_difference} vs expected {expected_difference}")
