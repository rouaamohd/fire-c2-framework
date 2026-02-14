"""
DataCollector: Multi-modal dataset generation for FIRE-C2 framework

This module manages comprehensive data collection across six modalities:
1. Packet-level network traffic
2. Node state time-series (temperature, fire, attack status)
3. Covert channel activity (C2 beacons, exfiltration)
4. Network performance metrics
5. Attack events and characteristics
6. Fire propagation dynamics

All data is exported as CSV files with synchronized timestamps for
multi-modal machine learning analysis.

Copyright (c) 2025 FIRE-C2 Research Team
Licensed under the MIT License
"""

import csv
from pathlib import Path
import time as time_module
import numpy as np
from Config import Config

class DataCollector:
    """
    Manages multi-modal dataset collection and CSV export.

    Maintains in-memory buffers for all data modalities and writes
    to disk incrementally to support large-scale simulations.
    """
    def __init__(self):
        self.packet_data = []
        self.node_state_data = []
        self.covert_channel_data = []
        self.network_metrics_data = []
        self.attack_events_data = []
        self.fire_dynamics_data = []
        
        # Metadata
        self.simulation_start_time = None
        self.data_files = {}

        self.sim_time_end_seconds = 0.0
        self.wall_clock_seconds = 0.0


        
    def init_data_files(self, run_id, output_dir="dataset"):
        """
        Initialize CSV files with headers for a new simulation run.

        Args:
            run_id: Unique identifier for this simulation run
            output_dir: Directory path for dataset output

        Creates six CSV files:
        - packets_{run_id}.csv: Network traffic data
        - node_states_{run_id}.csv: Time-series node telemetry
        - covert_channel_{run_id}.csv: C2 backdoor activity
        - network_metrics_{run_id}.csv: Performance statistics
        - attack_events_{run_id}.csv: Attack lifecycle events
        - fire_dynamics_{run_id}.csv: Fire propagation data
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self._headers = {}
        packet_headers = [
            'timestamp', 'node_id', 'packet_type', 'direction', 'size_bytes',
            'source_ip', 'dest_ip', 'protocol', 'sequence_number',
            'temperature_value', 'is_spoofed', 'attack_pattern',
            'network_delay', 'packet_loss', 'rssi', 'sinr',
            'tx_power', 'data_rate', 'retransmission_count',
            'congestion_window', 'queue_delay', 'hop_count'
        ]
        self.packet_file = self.output_dir / f"packets_{run_id}.csv"
        with open(self.packet_file, 'w', newline='') as f:
            csv.writer(f).writerow(packet_headers)
        self._headers[str(self.packet_file)] = packet_headers

        node_state_headers = [
            'timestamp', 'node_id', 'position_x', 'position_y',
            'actual_temperature', 'reported_temperature', 'temperature_variance',
            'is_on_fire', 'heat_level', 'received_heat', 'fire_start_time',
            'is_attacker', 'attack_triggered', 'attack_mode', 'coalition_active',
            'battery_level_reserved', 'sensor_health_reserved', 'neighbor_count',
            'packets_sent', 'packets_received', 'packets_dropped',
            'malicious_packets_sent', 'spoofing_count', 'drift_offset'
        ]
        self.node_state_file = self.output_dir / f"node_states_{run_id}.csv"
        with open(self.node_state_file, 'w', newline='') as f:
            csv.writer(f).writerow(node_state_headers)
        self._headers[str(self.node_state_file)] = node_state_headers

        covert_headers = [
            'timestamp', 'node_id', 'channel_type', 'message_type',
            'bit_sequence', 'timing_delay', 'lsb_encoded_value',
            'payload_size', 'protocol_used'
        ]
        self.covert_file = self.output_dir / f"covert_channel_{run_id}.csv"
        with open(self.covert_file, 'w', newline='') as f:
            csv.writer(f).writerow(covert_headers)
        self._headers[str(self.covert_file)] = covert_headers

        # ------------------------------ Network metrics -----------------------------
        network_headers = [
            'timestamp', 'metric_type', 'value', 'node_id', 'interface',
            'throughput_mbps', 'latency_ms', 'jitter_ms', 'packet_loss_rate',
            'utilization_percent', 'queue_length', 'collision_count',
            'signal_strength', 'noise_floor', 'channel_busy_time'
        ]
        self.network_file = self.output_dir / f"network_metrics_{run_id}.csv"
        with open(self.network_file, 'w', newline='') as f:
            csv.writer(f).writerow(network_headers)
        self._headers[str(self.network_file)] = network_headers

        # -------------------------------- Attack events -----------------------------
        attack_headers = [
            'timestamp', 'attack_type', 'attacker_ids', 'duration',
            'intensity', 'success_rate', 'detection_status',
            'impact_score', 'technique', 'target_nodes', 'triggers'
        ]
        self.attack_file = self.output_dir / f"attack_events_{run_id}.csv"
        with open(self.attack_file, 'w', newline='') as f:
            csv.writer(f).writerow(attack_headers)
        self._headers[str(self.attack_file)] = attack_headers

        # --------------------------------- Fire dynamics ----------------------------
        fire_headers = [
            'timestamp', 'node_id', 'fire_intensity', 'spread_rate',
            'wind_effect_x', 'wind_effect_y', 'neighbor_influence',
            'ignition_probability', 'radiative_heat', 'convective_heat',
            'fuel_remaining', 'suppression_effect', 'reignition_count'
        ]
        self.fire_file = self.output_dir / f"fire_dynamics_{run_id}.csv"
        with open(self.fire_file, 'w', newline='') as f:
            csv.writer(f).writerow(fire_headers)
        self._headers[str(self.fire_file)] = fire_headers

        # ---------------------------------------------------------------------------
        self.simulation_start_time = time_module.time()

        
    def record_packet(self, timestamp, node_id, packet_type, direction, size_bytes,
                     temperature_value, is_spoofed=False, attack_pattern="None", **kwargs):
        """Record packet-level data"""
        row = {
            'timestamp': timestamp,
            'node_id': node_id,
            'packet_type': packet_type,
            'direction': direction,
            'size_bytes': size_bytes,
            'temperature_value': temperature_value,
            'is_spoofed': is_spoofed,
            'attack_pattern': attack_pattern,
            'network_delay': kwargs.get('network_delay', 0),
            'packet_loss': kwargs.get('packet_loss', 0),
            'rssi': kwargs.get('rssi', ''),
            'sinr': kwargs.get('sinr', ''),
            'tx_power': kwargs.get('tx_power', ''),
            'data_rate': kwargs.get('data_rate', ''),
            'retransmission_count': kwargs.get('retransmission_count', 0),
            'congestion_window': kwargs.get('congestion_window', 10),
            'queue_delay': kwargs.get('queue_delay', 0),
            'hop_count': kwargs.get('hop_count', 1)
        }

        row.update({
            'source_ip': kwargs.get('source_ip', ''),
            'dest_ip':   kwargs.get('dest_ip', ''),
            'protocol':  kwargs.get('protocol', 'UDP'),
            'sequence_number': kwargs.get('sequence_number', 0),
        })

        
        self.packet_data.append(row)
        self._append_to_csv(self.packet_file, row)
        
    def record_node_state(self, timestamp, node, grid, **kwargs):
        """Record comprehensive node state"""
        # Calculate neighborhood metrics
        r = node.id // Config.N_COLS
        c = node.id % Config.N_COLS
        neighbor_count = 0
        neighbor_temps = []
        
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < Config.N_ROWS and 0 <= cc < Config.N_COLS:
                    neighbor = grid[rr][cc]
                    neighbor_count += 1
                    neighbor_temps.append(neighbor.current_temp)
        
        temp_variance = np.var(neighbor_temps) if neighbor_temps else 0
        
        row = {
            'timestamp': timestamp,
            'node_id': node.id,
            'position_x': node.position[0],
            'position_y': node.position[1],
            'actual_temperature': node.current_temp,
            'reported_temperature': kwargs.get('reported_temp', node.current_temp),
            'temperature_variance': temp_variance,
            'is_on_fire': node.on_fire,
            'heat_level': node.heat_level,
            'received_heat': node.received_heat,
            'fire_start_time': node.fire_start_time if node.on_fire else 0,
            'is_attacker': node.is_attacker,
            'attack_triggered': node.attack_triggered,
            'attack_mode': node.attack_mode,
            'coalition_active': kwargs.get('coalition_active', False),
            'battery_level_reserved': '',
            'sensor_health_reserved': '',
            'neighbor_count': neighbor_count,
            'packets_sent': node.stats.benign_tx + node.stats.malicious_tx,
            'packets_received': kwargs.get('packets_received', 0),
            'packets_dropped': node.stats.drops,
            'malicious_packets_sent': node.stats.malicious_tx,
            'spoofing_count': kwargs.get('spoofing_count', 0),
            'drift_offset': node.drift_offset if hasattr(node, 'drift_offset') else 0
        }
        
        self.node_state_data.append(row)
        self._append_to_csv(self.node_state_file, row)
        
    def record_covert_channel(self, timestamp, node_id, channel_type, **kwargs):
        """
        Record covert channel activity (C2 beacons, exfiltration).

        Args:
            timestamp: Simulation time of event
            node_id: Source node ID
            channel_type: Type of covert channel ("timing", "lsb", "hybrid")
            **kwargs: Additional channel-specific attributes
        """
        row = {
            'timestamp': timestamp,
            'node_id': node_id,
            'channel_type': channel_type,
            'message_type': kwargs.get('message_type', 'beacon'),
            'bit_sequence': kwargs.get('bit_sequence', ''),
            'timing_delay': kwargs.get('timing_delay', 0),
            'lsb_encoded_value': kwargs.get('lsb_encoded_value', 0),
            'payload_size': kwargs.get('payload_size', 0),
            'protocol_used': kwargs.get('protocol_used', 'UDP')
        }
        
        self.covert_channel_data.append(row)
        self._append_to_csv(self.covert_file, row)
        
    def record_network_metrics(self, timestamp, metric_type, value, **kwargs):
        """
        Record network performance metrics (throughput, latency, RSSI, etc.).

        Args:
            timestamp: Simulation time of measurement
            metric_type: Metric category (e.g., "throughput", "latency")
            value: Measured value
            **kwargs: Additional metric-specific attributes
        """
        row = {
            'timestamp': timestamp,
            'metric_type': metric_type,
            'value': value,
            'node_id': kwargs.get('node_id', -1),
            'interface': kwargs.get('interface', 'wifi'),
            'throughput_mbps': kwargs.get('throughput_mbps', 0),
            'latency_ms': kwargs.get('latency_ms', 0),
            'jitter_ms': kwargs.get('jitter_ms', 0),
            'packet_loss_rate': kwargs.get('packet_loss_rate', 0),
            'utilization_percent': kwargs.get('utilization_percent', 0),
            'queue_length': kwargs.get('queue_length', 0),
            'collision_count': kwargs.get('collision_count', 0),
            'signal_strength': kwargs.get('signal_strength', -80),
            'noise_floor': kwargs.get('noise_floor', -95),
            'channel_busy_time': kwargs.get('channel_busy_time', 0)
        }
        
        self.network_metrics_data.append(row)
        self._append_to_csv(self.network_file, row)
        
    def record_attack_event(self, timestamp, attack_type, **kwargs):
        """
        Record attack lifecycle events and metadata.

        Args:
            timestamp: Simulation time of attack event
            attack_type: Attack category (e.g., "C2_ACTIVATION", "SPOOFING")
            **kwargs: Attack-specific attributes (duration, intensity, etc.)
        """
        row = {
            'timestamp': timestamp,
            'attack_type': attack_type,
            'attacker_ids': kwargs.get('attacker_ids', []),
            'duration': kwargs.get('duration', 0),
            'intensity': kwargs.get('intensity', 1.0),
            'success_rate': kwargs.get('success_rate', 0.0),
            'detection_status': kwargs.get('detection_status', 'undetected'),
            'impact_score': kwargs.get('impact_score', 0.0),
            'technique': kwargs.get('technique', 'unknown'),
            'target_nodes': kwargs.get('target_nodes', []),
            'triggers': kwargs.get('triggers', [])
        }
        
        self.attack_events_data.append(row)
        self._append_to_csv(self.attack_file, row)
        
    def record_fire_dynamics(self, timestamp, node_id, **kwargs):
        """
        Record physical fire propagation and heat transfer dynamics.

        Args:
            timestamp: Simulation time
            node_id: Node experiencing fire/heat
            **kwargs: Fire-specific attributes (intensity, spread_rate, heat, etc.)
        """
        row = {
            'timestamp': timestamp,
            'node_id': node_id,
            'fire_intensity': kwargs.get('fire_intensity', 0),
            'spread_rate': kwargs.get('spread_rate', 0),
            'wind_effect_x': kwargs.get('wind_effect_x', 0),
            'wind_effect_y': kwargs.get('wind_effect_y', 0),
            'neighbor_influence': kwargs.get('neighbor_influence', 0),
            'ignition_probability': kwargs.get('ignition_probability', 0),
            'radiative_heat': kwargs.get('radiative_heat', 0),
            'convective_heat': kwargs.get('convective_heat', 0),
            'fuel_remaining': kwargs.get('fuel_remaining', 100),
            'suppression_effect': kwargs.get('suppression_effect', 0),
            'reignition_count': kwargs.get('reignition_count', 0)
        }
        
        self.fire_dynamics_data.append(row)
        self._append_to_csv(self.fire_file, row)
        
    def _append_to_csv(self, filename, row_dict):
        """
        Internal method: Append a single row to CSV file using DictWriter.

        Args:
            filename: Path to CSV file
            row_dict: Dictionary of column_name → value
        """
        try:
            fname = str(filename)
            headers = self._headers.get(fname)
            with open(filename, 'a', newline='') as f:
                if headers:
                    dw = csv.DictWriter(f, fieldnames=headers)
                    safe_row = {k: row_dict.get(k, "") for k in headers}
                    dw.writerow(safe_row)
                else:
                    csv.writer(f).writerow(list(row_dict.values()))
        except Exception as e:
            print(f"Error writing to {filename}: {e}")

    def generate_summary_report(self):
        """
        Generate comprehensive dataset statistics and metadata.

        Creates a JSON summary file containing:
        - Record counts across all modalities
        - Simulation timing (ns-3 sim time vs wall-clock time)
        - List of generated data files
        - Unique node count

        Returns:
            Dictionary containing summary statistics
        """
        self.wall_clock_seconds = time_module.time() - (self.simulation_start_time or time_module.time())
        summary = {
            'total_packets': len(self.packet_data),
            'total_node_states': len(self.node_state_data),
            'total_covert_events': len(self.covert_channel_data),
            'sim_time_seconds': self.sim_time_end_seconds,
            'wall_clock_seconds': self.wall_clock_seconds,
            'unique_nodes': len(set([d['node_id'] for d in self.node_state_data])),
            'attack_events_count': len(self.attack_events_data),
            'data_files': {
                'packets': str(self.packet_file),
                'node_states': str(self.node_state_file),
                'covert_channel': str(self.covert_file),
                'network_metrics': str(self.network_file),
                'attack_events': str(self.attack_file),
                'fire_dynamics': str(self.fire_file)
            }
        }

        import json
        summary_file = self.output_dir / "dataset_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        return summary