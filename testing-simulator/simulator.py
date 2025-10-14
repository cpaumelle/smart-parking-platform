"""
Parking System Simulator
Main orchestrator for simulating 100 parking sensors and busylights
"""

import yaml
import time
import threading
from datetime import datetime
from typing import List, Dict
import signal
import sys

from parking_sensor import ParkingSensor, ParkingState
from busylight import Busylight
from chirpstack_mqtt_client import ChirpStackMQTTClient, MockChirpStackClient


class ParkingSimulator:
    """
    Main simulator class that orchestrates sensors, busylights, and ChirpStack communication
    """
    
    def __init__(self, config_path: str = 'config.yaml', mock_mode: bool = False):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.num_spaces = self.config['simulation']['num_parking_spaces']
        self.mock_mode = mock_mode
        
        # Initialize ChirpStack client
        if mock_mode:
            print("[Simulator] Running in MOCK mode (no real ChirpStack connection)")
            self.chirpstack = MockChirpStackClient(self.config)
        else:
            print("[Simulator] Connecting to ChirpStack...")
            self.chirpstack = ChirpStackMQTTClient(self.config)
            if not self.chirpstack.connect():
                print("[Simulator] WARNING: MQTT connection failed!")
                print("[Simulator] Continuing in mock mode...")
                self.mock_mode = True
                self.chirpstack.disconnect()
                self.chirpstack = MockChirpStackClient(self.config)
            if not self.chirpstack.test_connection():
                print("[Simulator] WARNING: ChirpStack connection failed!")
                print("[Simulator] Continuing in mock mode...")
                self.mock_mode = True
                self.chirpstack = MockChirpStackClient(self.config)
        
        # Create devices
        print(f"[Simulator] Creating {self.num_spaces} parking spaces...")
        self.sensors: List[ParkingSensor] = []
        self.busylights: List[Busylight] = []
        
        self._create_devices()
        
        # Simulation control
        self.running = False
        self.simulation_thread = None
        
        # Statistics
        self.start_time = None
        self.total_state_changes = 0
        self.total_updates = 0
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        
        print(f"[Simulator] Initialization complete!")
        print(f"[Simulator] Sensors: {len(self.sensors)}")
        print(f"[Simulator] Busylights: {len(self.busylights)}")
    
    def _create_devices(self):
        """Create all sensor and busylight instances"""
        sensor_prefix = self.config['simulation']['sensor_dev_eui_prefix']
        busylight_prefix = self.config['simulation']['busylight_dev_eui_prefix']
        
        for i in range(self.num_spaces):
            # Create sensor
            sensor_eui = f"{sensor_prefix}{i:08d}"
            sensor = ParkingSensor(
                sensor_id=i,
                dev_eui=sensor_eui,
                config=self.config
            )
            self.sensors.append(sensor)
            
            # Create busylight
            busylight_eui = f"{busylight_prefix}{i:08d}"
            busylight = Busylight(
                light_id=i,
                dev_eui=busylight_eui,
                config=self.config
            )
            self.busylights.append(busylight)
    
    def start(self):
        """Start the simulation"""
        if self.running:
            print("[Simulator] Already running!")
            return
        
        print("[Simulator] Starting simulation...")
        self.running = True
        self.start_time = datetime.now()
        
        # Start simulation thread
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        
        print("[Simulator] Simulation started!")
    
    def stop(self):
        """Stop the simulation"""
        if not self.running:
            return
        
        print("\n[Simulator] Stopping simulation...")
        self.running = False
        
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
        
        self._print_final_statistics()
        print("[Simulator] Simulation stopped.")
    
    def _simulation_loop(self):
        """Main simulation loop"""
        update_interval = self.config['simulation']['sensor_update_interval']
        
        while self.running:
            try:
                self._update_cycle()
                time.sleep(update_interval)
            except Exception as e:
                print(f"[Simulator] Error in simulation loop: {e}")
                import traceback
                traceback.print_exc()
    
    def _update_cycle(self):
        """Execute one update cycle"""
        self.total_updates += 1
        
        print(f"\n{'='*80}")
        print(f"[Cycle {self.total_updates}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        state_changes_this_cycle = 0
        
        # Update all sensors
        for sensor in self.sensors:
            state_changed = sensor.update()
            
            if state_changed:
                state_changes_this_cycle += 1
                self.total_state_changes += 1
                
                # Send uplink to ChirpStack
                payload = sensor.get_uplink_payload()
                self.chirpstack.send_uplink(
                    dev_eui=sensor.dev_eui,
                    fport=sensor.fport,
                    payload=payload
                )
                
                # Update corresponding busylight
                self._update_busylight(sensor)
        
        # Print cycle summary
        self._print_cycle_summary(state_changes_this_cycle)
        
        # Print parking lot status
        if self.total_updates % 5 == 0:  # Every 5 cycles
            self._print_parking_status()
    
    def _update_busylight(self, sensor: ParkingSensor):
        """Update busylight based on sensor state"""
        busylight = self.busylights[sensor.sensor_id]
        
        # Determine color based on sensor state
        if sensor.state == ParkingState.AVAILABLE:
            state_name = 'available'
        elif sensor.state == ParkingState.OCCUPIED:
            # Check if expiring soon (less than 5 minutes remaining)
            time_left = sensor.get_time_until_departure()
            if time_left is not None and time_left < 5:
                state_name = 'expiring_soon'
            else:
                state_name = 'occupied'
        elif sensor.state == ParkingState.RESERVED:
            state_name = 'reserved'
        elif sensor.state == ParkingState.MAINTENANCE:
            state_name = 'maintenance'
        else:
            state_name = 'unknown'
        
        # Get payload from config
        colors = self.config['colors']
        payload_hex = colors[state_name]['payload']
        
        # Convert hex to bytes and send downlink
        payload_bytes = bytes.fromhex(payload_hex)
        self.chirpstack.enqueue_downlink(
            dev_eui=busylight.dev_eui,
            fport=busylight.fport,
            payload=payload_bytes
        )
        
        # Update busylight internal state
        busylight.process_downlink(payload_bytes)
    
    def _print_cycle_summary(self, state_changes: int):
        """Print summary of current cycle"""
        occupied = sum(1 for s in self.sensors if s.state == ParkingState.OCCUPIED)
        available = sum(1 for s in self.sensors if s.state == ParkingState.AVAILABLE)
        reserved = sum(1 for s in self.sensors if s.state == ParkingState.RESERVED)
        unknown = sum(1 for s in self.sensors if s.state == ParkingState.UNKNOWN)
        
        occupancy_rate = (occupied / self.num_spaces) * 100
        
        print(f"\n[Summary]")
        print(f"  State Changes: {state_changes}")
        print(f"  Occupied: {occupied}/{self.num_spaces} ({occupancy_rate:.1f}%)")
        print(f"  Available: {available}")
        print(f"  Reserved: {reserved}")
        print(f"  Unknown: {unknown}")
        
        # ChirpStack stats
        stats = self.chirpstack.get_statistics()
        print(f"\n[ChirpStack Stats]")
        print(f"  Uplinks: {stats['uplinks_sent']}")
        print(f"  Downlinks: {stats['downlinks_sent']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Success Rate: {stats['success_rate']:.1f}%")
    
    def _print_parking_status(self):
        """Print visual parking lot status"""
        print(f"\n[Parking Lot Status]")
        
        # Print in rows of 10
        for row in range(0, self.num_spaces, 10):
            row_sensors = self.sensors[row:row+10]
            row_lights = self.busylights[row:row+10]
            
            # Print sensor IDs
            ids = "  ".join(f"{s.sensor_id:3d}" for s in row_sensors)
            print(f"  IDs:    {ids}")
            
            # Print light status (visual)
            lights = "   ".join(light.get_visual_representation() for light in row_lights)
            print(f"  Lights: {lights}")
            
            # Print states
            states = "  ".join(f"{s.state.value[:3]:3s}" for s in row_sensors)
            print(f"  States: {states}")
            
            print()
    
    def _print_final_statistics(self):
        """Print final statistics when simulation ends"""
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        print(f"\n{'='*80}")
        print("[Final Statistics]")
        print(f"{'='*80}")
        print(f"Simulation Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"Total Update Cycles: {self.total_updates}")
        print(f"Total State Changes: {self.total_state_changes}")
        print(f"Average Changes per Cycle: {self.total_state_changes/max(1, self.total_updates):.2f}")
        
        stats = self.chirpstack.get_statistics()
        print(f"\nChirpStack Messages:")
        print(f"  Total Uplinks: {stats['uplinks_sent']}")
        print(f"  Total Downlinks: {stats['downlinks_sent']}")
        print(f"  Total Errors: {stats['errors']}")
        print(f"  Success Rate: {stats['success_rate']:.1f}%")
        
        # Final occupancy
        occupied = sum(1 for s in self.sensors if s.state == ParkingState.OCCUPIED)
        print(f"\nFinal Occupancy: {occupied}/{self.num_spaces} ({occupied/self.num_spaces*100:.1f}%)")
    
    def get_sensor_by_id(self, sensor_id: int) -> ParkingSensor:
        """Get sensor by ID"""
        if 0 <= sensor_id < len(self.sensors):
            return self.sensors[sensor_id]
        return None
    
    def get_busylight_by_id(self, light_id: int) -> Busylight:
        """Get busylight by ID"""
        if 0 <= light_id < len(self.busylights):
            return self.busylights[light_id]
        return None
    
    def force_state_change(self, sensor_id: int, new_state: str):
        """Manually force a sensor state change (for testing)"""
        sensor = self.get_sensor_by_id(sensor_id)
        if sensor:
            old_state = sensor.state
            
            if new_state.lower() == 'occupied':
                sensor._park_car()
            elif new_state.lower() == 'available':
                sensor._car_departs()
            elif new_state.lower() == 'reserved':
                sensor.state = ParkingState.RESERVED
            elif new_state.lower() == 'maintenance':
                sensor.state = ParkingState.MAINTENANCE
            
            print(f"[Manual] Changed sensor {sensor_id}: {old_state.value} -> {sensor.state.value}")
            
            # Send uplink and update busylight
            payload = sensor.get_uplink_payload()
            self.chirpstack.send_uplink(sensor.dev_eui, sensor.fport, payload)
            self._update_busylight(sensor)
    
    def run_test_scenario(self, scenario_name: str):
        """Run a predefined test scenario"""
        scenarios = self.config.get('test_scenarios', [])
        scenario = next((s for s in scenarios if s['name'] == scenario_name), None)
        
        if not scenario:
            print(f"[Simulator] Scenario '{scenario_name}' not found!")
            return
        
        print(f"[Simulator] Running test scenario: {scenario_name}")
        print(f"[Simulator] Duration: {scenario['duration']} seconds")
        
        # Apply scenario parameters
        # This would modify behavior temporarily
        # Implementation depends on specific scenario requirements
        
        time.sleep(scenario['duration'])
        print(f"[Simulator] Scenario '{scenario_name}' complete!")
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n[Simulator] Received interrupt signal...")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Parking Simulator')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode (no ChirpStack)')
    parser.add_argument('--duration', type=int, help='Run for specified seconds then exit')
    
    args = parser.parse_args()
    
    # Create simulator
    simulator = ParkingSimulator(config_path=args.config, mock_mode=args.mock)
    
    # Start simulation
    simulator.start()
    
    # Run for specified duration or indefinitely
    if args.duration:
        print(f"[Simulator] Running for {args.duration} seconds...")
        time.sleep(args.duration)
        simulator.stop()
    else:
        print("[Simulator] Running indefinitely. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            simulator.stop()


if __name__ == '__main__':
    main()
