"""
SmartSensor: IoT fire alarm sensor node implementation

This module implements a smart sensor node with:
- Temperature sensing and fire detection
- Fire propagation dynamics with heat transfer
- C2 backdoor capability for compromised nodes
- Realistic packet generation with temporal correlation

Copyright (c) 2025 FIRE-C2 Research Team
Licensed under the MIT License
"""

import random
import struct
from collections import deque
from typing import List, Deque, Optional
from NodeStats import NodeStats
from Config import Config

class SmartSensor:
    """
    IoT sensor node with fire detection, heat dynamics, and optional C2 backdoor.

    Each node maintains:
    - Current temperature and temperature history
    - Fire state (on_fire, heat_level, received_heat)
    - Attack state (is_attacker, attack_triggered, attack_mode)
    - Network sockets for legitimate and C2 communication
    """
    def __init__(self, node_id: int, position: tuple):
        """
        Initialize sensor node with given ID and position.

        Args:
            node_id: Unique node identifier in network
            position: Tuple of (x, y) coordinates for spatial placement
        """
        self.id = node_id
        self.position = position
        self.is_attacker = (node_id in Config.ATTACKER_IDS)
        self.is_fire_node = (node_id == Config.FIRE_NODE_ID)
        self.stats = NodeStats()
        self.temp_history: Deque[float] = deque(maxlen=Config.TEMP_HISTORY_WINDOW)
        self.socket: Optional[object] = None
        self.current_temp = random.uniform(*Config.BENIGN_TEMP_RANGE)

        self.c2_socket: Optional[object] = None
        self.next_c2_beacon: float = 0.0
        self.next_exfil: float = 0.0
        self.attack_triggered = False
        self.attack_mode = "None"

        self.on_fire = False
        self.fire_start_time = 0.0
        self.heat_level = 0.0
        self.received_heat = 0.0
        self.drift_offset = 0.0

        self.last_spoofed_temp = random.gauss(Config.SPOOFED_TEMP_MEAN, Config.SPOOFED_TEMP_STD)

        self.spoofing_count = 0
        self.packets_received = 0
        self.sensor_health = 1.0
        self.battery_level = 100.0

    def _generate_spoofed_temp(self) -> float:
        """
        Generate temporally correlated spoofed temperature for attack concealment.

        Uses exponential smoothing to create realistic temporal correlation,
        preventing abrupt changes that would expose spoofing.

        Returns:
            Spoofed temperature value within configured benign range
        """
        base_temp = random.gauss(Config.SPOOFED_TEMP_MEAN, Config.SPOOFED_TEMP_STD)
        correlated_temp = self.last_spoofed_temp + random.uniform(
            -Config.MAX_TEMP_DELTA, Config.MAX_TEMP_DELTA
        )
        final_temp = 0.7 * correlated_temp + 0.3 * base_temp

        final_temp = max(min(final_temp, max(Config.SPOOFED_TEMP_RANGE)),
                        min(Config.SPOOFED_TEMP_RANGE))
        self.last_spoofed_temp = final_temp
        return final_temp
    
    def update_temperature(self, sim_time: float, grid: List[List['SmartSensor']]) -> None:
        """
        Update temperature with realistic fire dynamics and heat propagation.

        Implements a multi-step physical fire model:
        1. Fire ignition at configured start time
        2. Fire duration with automatic burnout
        3. Heat diffusion to neighboring nodes (inverse-distance decay)
        4. Probabilistic fire spread based on distance and heat level
        5. Temperature calculation based on node state (on_fire, spoofing, or normal)

        Args:
            sim_time: Current simulation time in seconds
            grid: 2D array of sensor nodes for neighbor access
        """
        if self.is_fire_node and (not self.on_fire) and sim_time >= Config.FIRE_START:
            self.on_fire = True
            self.fire_start_time = sim_time
            self.heat_level = 1.0

        if self.on_fire and sim_time > self.fire_start_time + Config.FIRE_DURATION:
            self.on_fire = False
            self.heat_level *= 0.5

        self.received_heat = 0.0

        if self.heat_level > 0.1:
            r, c = self.id // Config.N_COLS, self.id % Config.N_COLS

            for dr in range(-Config.MAX_HEAT_RADIUS, Config.MAX_HEAT_RADIUS + 1):
                for dc in range(-Config.MAX_HEAT_RADIUS, Config.MAX_HEAT_RADIUS + 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < Config.N_ROWS and 0 <= nc < Config.N_COLS:
                        neighbor = grid[nr][nc]
                        distance = max(1, abs(dr) + abs(dc))
                        if distance <= Config.MAX_HEAT_RADIUS:
                            influence = Config.HEAT_DIFFUSION_RATE / (distance ** 1.5)
                            neighbor.received_heat += self.heat_level * influence

        if self.on_fire:
            self.heat_level = 1.0
        else:
            self.heat_level = (self.heat_level * Config.RESIDUAL_HEAT_DECAY +
                             self.received_heat)
            self.heat_level = min(self.heat_level, 1.0)

        if (self.on_fire and
            sim_time > self.fire_start_time + Config.FIRE_SPREAD_DELAY):

            neighbors = self.get_neighbors(grid)
            for neighbor in neighbors:
                if not neighbor.on_fire:
                    r, c = self.id // Config.N_COLS, self.id % Config.N_COLS
                    nr, nc = neighbor.id // Config.N_COLS, neighbor.id % Config.N_COLS
                    distance = max(1, abs(r - nr) + abs(c - nc))

                    spread_prob = Config.FIRE_SPREAD_RATE / distance
                    heat_bonus = neighbor.heat_level * 0.3
                    spread_prob += heat_bonus

                    fire_tick = getattr(Config, 'FIRE_TICK_INTERVAL', 1.0)
                    if random.random() < spread_prob * fire_tick:
                        neighbor.on_fire = True
                        neighbor.fire_start_time = sim_time

        if self.is_attacker and self.attack_triggered:
            self.current_temp = self._generate_spoofed_temp()
        elif self.on_fire:
            self.current_temp = Config.FIRE_TEMP + random.uniform(-1.5, 1.5)
        else:
            base_temp = random.uniform(*Config.BENIGN_TEMP_RANGE)
            heat_effect = self.heat_level * (Config.FIRE_TEMP - base_temp) * 0.6
            self.current_temp = base_temp + heat_effect + random.uniform(-0.3, 0.3)

        self.temp_history.append(self.current_temp)

    def generate_payload(self) -> tuple:
        """
        Generate sensor data payload and traffic label.

        Packet structure:
        - 2-byte header: node ID for source identification
        - N float values: temperature readings (with noise/variance)

        Returns:
            Tuple of (payload_bytes, label_string)
            Labels: "BENIGN", "FIRE", "C2_SPOOF", "REACTIVE_SPOOF"
        """
        header = struct.pack("<H", self.id)

        if self.is_attacker and self.attack_triggered:
            base_temp = self._generate_spoofed_temp()
            vals = [base_temp + random.uniform(-0.5, 0.5)
                   for _ in range((Config.PKT_SIZE - 2) // 4)]
            self.stats.malicious_tx += 1
            label = "C2_SPOOF" if self.attack_mode == "C2_BACKDOOR" else "REACTIVE_SPOOF"

        elif self.on_fire:
            vals = [self.current_temp + random.uniform(-2.0, 2.0)
                   for _ in range((Config.PKT_SIZE - 2) // 4)]
            self.stats.benign_tx += 1
            label = "FIRE"

        else:
            vals = [self.current_temp + random.uniform(-0.1, 0.1)
                   for _ in range((Config.PKT_SIZE - 2) // 4)]
            self.stats.benign_tx += 1
            label = "BENIGN"

        payload_body = b"".join(struct.pack("f", v) for v in vals)
        return header + payload_body, label

    def get_neighbors(self, grid: List[List['SmartSensor']]) -> List['SmartSensor']:
        """
        Get adjacent nodes in 4-directional grid topology.

        Args:
            grid: 2D array of sensor nodes

        Returns:
            List of neighboring SmartSensor objects
        """
        r, c = self.id // Config.N_COLS, self.id % Config.N_COLS
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < Config.N_ROWS and 0 <= nc < Config.N_COLS:
                neighbors.append(grid[nr][nc])
        return neighbors

    def cleanup(self):
        """
        Clean up node resources and release references.

        Called during simulation teardown to prevent memory leaks and
        simulator state corruption.
        """
        self.socket = None
        self.c2_socket = None
        self.temp_history.clear()