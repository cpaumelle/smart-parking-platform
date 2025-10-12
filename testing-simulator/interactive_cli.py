#!/usr/bin/env python3
"""
Interactive Simulator Control
CLI tool for controlling the parking simulator during runtime
"""

import cmd
import time
from simulator import ParkingSimulator


class SimulatorCLI(cmd.Cmd):
    """Interactive command-line interface for the simulator"""
    
    intro = """
╔══════════════════════════════════════════════════════════════╗
║          Smart Parking Simulator - Interactive CLI          ║
║                   100 Sensors + Busylights                   ║
╚══════════════════════════════════════════════════════════════╝

Type 'help' or '?' to list commands.
Type 'start' to begin simulation.
    """
    prompt = '(parking) '
    
    def __init__(self):
        super().__init__()
        self.simulator = None
    
    def do_init(self, arg):
        """Initialize the simulator: init [--mock]"""
        mock_mode = '--mock' in arg
        
        try:
            print("Initializing simulator...")
            self.simulator = ParkingSimulator(mock_mode=mock_mode)
            print("✓ Simulator initialized successfully!")
        except Exception as e:
            print(f"✗ Error initializing simulator: {e}")
    
    def do_start(self, arg):
        """Start the simulation"""
        if not self.simulator:
            print("✗ Simulator not initialized. Run 'init' first.")
            return
        
        self.simulator.start()
        print("✓ Simulation started!")
    
    def do_stop(self, arg):
        """Stop the simulation"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        self.simulator.stop()
        print("✓ Simulation stopped!")
    
    def do_status(self, arg):
        """Show current simulator status"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        print("\n" + "="*70)
        print("SIMULATOR STATUS")
        print("="*70)
        
        # Count states
        occupied = sum(1 for s in self.simulator.sensors if s.state.value == 'occupied')
        available = sum(1 for s in self.simulator.sensors if s.state.value == 'available')
        reserved = sum(1 for s in self.simulator.sensors if s.state.value == 'reserved')
        unknown = sum(1 for s in self.simulator.sensors if s.state.value == 'unknown')
        
        print(f"Total Spaces: {self.simulator.num_spaces}")
        print(f"Occupied: {occupied} ({occupied/self.simulator.num_spaces*100:.1f}%)")
        print(f"Available: {available} ({available/self.simulator.num_spaces*100:.1f}%)")
        print(f"Reserved: {reserved}")
        print(f"Unknown: {unknown}")
        
        if self.simulator.running:
            print(f"\nStatus: RUNNING ✓")
            print(f"Update Cycles: {self.simulator.total_updates}")
            print(f"State Changes: {self.simulator.total_state_changes}")
        else:
            print(f"\nStatus: STOPPED")
        
        stats = self.simulator.chirpstack.get_statistics()
        print(f"\nChirpStack:")
        print(f"  Uplinks: {stats['uplinks_sent']}")
        print(f"  Downlinks: {stats['downlinks_sent']}")
        print(f"  Errors: {stats['errors']}")
        print("="*70 + "\n")
    
    def do_show(self, arg):
        """Show parking lot visual status"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        self.simulator._print_parking_status()
    
    def do_sensor(self, arg):
        """Get sensor details: sensor <id>"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        try:
            sensor_id = int(arg)
            sensor = self.simulator.get_sensor_by_id(sensor_id)
            
            if not sensor:
                print(f"✗ Sensor {sensor_id} not found.")
                return
            
            print(f"\n{'='*70}")
            print(f"SENSOR {sensor_id} DETAILS")
            print(f"{'='*70}")
            print(f"DEV_EUI: {sensor.dev_eui}")
            print(f"State: {sensor.state.value}")
            print(f"Distance: {sensor.distance:.3f} m")
            print(f"Battery: {sensor.battery_level:.1f}%")
            print(f"Operational: {sensor.is_operational}")
            print(f"Message Count: {sensor.message_count}")
            print(f"Last Update: {sensor.last_update}")
            
            if sensor.state.value == 'occupied':
                duration = sensor._get_parking_duration_minutes()
                time_left = sensor.get_time_until_departure()
                print(f"\nParking Duration: {duration:.1f} minutes")
                if time_left is not None:
                    print(f"Expected Departure: {time_left} minutes")
            
            print(f"{'='*70}\n")
            
        except ValueError:
            print("✗ Invalid sensor ID. Use: sensor <id>")
    
    def do_busylight(self, arg):
        """Get busylight details: busylight <id>"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        try:
            light_id = int(arg)
            light = self.simulator.get_busylight_by_id(light_id)
            
            if not light:
                print(f"✗ Busylight {light_id} not found.")
                return
            
            print(f"\n{'='*70}")
            print(f"BUSYLIGHT {light_id} DETAILS")
            print(f"{'='*70}")
            print(f"DEV_EUI: {light.dev_eui}")
            print(f"Color: {light.current_color.value} {light.get_visual_representation()}")
            print(f"RGB: ({light.red}, {light.green}, {light.blue})")
            print(f"Blinking: {light.is_blinking}")
            print(f"Operational: {light.is_operational}")
            print(f"Downlink Count: {light.downlink_count}")
            print(f"Last Update: {light.last_update}")
            print(f"Associated Space: {light.associated_space_id}")
            print(f"{'='*70}\n")
            
        except ValueError:
            print("✗ Invalid busylight ID. Use: busylight <id>")
    
    def do_force(self, arg):
        """Force sensor state change: force <id> <state>
        States: occupied, available, reserved, maintenance"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        try:
            parts = arg.split()
            if len(parts) != 2:
                print("✗ Usage: force <sensor_id> <state>")
                return
            
            sensor_id = int(parts[0])
            state = parts[1].lower()
            
            valid_states = ['occupied', 'available', 'reserved', 'maintenance']
            if state not in valid_states:
                print(f"✗ Invalid state. Choose from: {', '.join(valid_states)}")
                return
            
            self.simulator.force_state_change(sensor_id, state)
            print(f"✓ Sensor {sensor_id} state changed to {state}")
            
        except ValueError:
            print("✗ Invalid sensor ID. Use: force <id> <state>")
    
    def do_scenario(self, arg):
        """Run test scenario: scenario <name>"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        if not arg:
            print("Available scenarios:")
            scenarios = self.simulator.config.get('test_scenarios', [])
            for s in scenarios:
                print(f"  - {s['name']} ({s['duration']}s)")
            return
        
        self.simulator.run_test_scenario(arg)
    
    def do_fill(self, arg):
        """Fill parking lot to specified occupancy: fill <percentage>"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        try:
            target_pct = float(arg)
            if not 0 <= target_pct <= 100:
                print("✗ Percentage must be between 0 and 100")
                return
            
            current_occupied = sum(1 for s in self.simulator.sensors 
                                 if s.state.value == 'occupied')
            target_occupied = int(self.simulator.num_spaces * target_pct / 100)
            
            if target_occupied > current_occupied:
                # Need to fill spaces
                available_sensors = [s for s in self.simulator.sensors 
                                   if s.state.value == 'available']
                to_fill = target_occupied - current_occupied
                
                for sensor in available_sensors[:to_fill]:
                    self.simulator.force_state_change(sensor.sensor_id, 'occupied')
                
                print(f"✓ Filled {to_fill} spaces. Occupancy: {target_pct:.1f}%")
                
            elif target_occupied < current_occupied:
                # Need to empty spaces
                occupied_sensors = [s for s in self.simulator.sensors 
                                  if s.state.value == 'occupied']
                to_empty = current_occupied - target_occupied
                
                for sensor in occupied_sensors[:to_empty]:
                    self.simulator.force_state_change(sensor.sensor_id, 'available')
                
                print(f"✓ Emptied {to_empty} spaces. Occupancy: {target_pct:.1f}%")
            else:
                print(f"✓ Already at target occupancy: {target_pct:.1f}%")
                
        except ValueError:
            print("✗ Invalid percentage. Use: fill <0-100>")
    
    def do_rush(self, arg):
        """Simulate rush hour (rapidly fill parking lot)"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        print("Simulating rush hour...")
        
        available = [s for s in self.simulator.sensors if s.state.value == 'available']
        
        for i, sensor in enumerate(available):
            if i % 10 == 0:
                print(f"  Filling spaces: {i}/{len(available)}")
                time.sleep(0.5)
            
            self.simulator.force_state_change(sensor.sensor_id, 'occupied')
        
        print("✓ Rush hour simulation complete!")
        self.do_status('')
    
    def do_clear(self, arg):
        """Clear all parking spaces (make all available)"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        print("Clearing all parking spaces...")
        
        occupied = [s for s in self.simulator.sensors if s.state.value == 'occupied']
        
        for sensor in occupied:
            self.simulator.force_state_change(sensor.sensor_id, 'available')
        
        print(f"✓ Cleared {len(occupied)} spaces!")
    
    def do_test(self, arg):
        """Test busylight patterns on a specific light: test <id>"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        try:
            light_id = int(arg)
            light = self.simulator.get_busylight_by_id(light_id)
            
            if not light:
                print(f"✗ Busylight {light_id} not found.")
                return
            
            print(f"Testing busylight {light_id} patterns...")
            light.test_pattern()
            print("✓ Test complete!")
            
        except ValueError:
            print("✗ Invalid busylight ID. Use: test <id>")
    
    def do_stats(self, arg):
        """Show detailed statistics"""
        if not self.simulator:
            print("✗ Simulator not initialized.")
            return
        
        stats = self.simulator.chirpstack.get_statistics()
        
        print("\n" + "="*70)
        print("DETAILED STATISTICS")
        print("="*70)
        print(f"Simulation Cycles: {self.simulator.total_updates}")
        print(f"Total State Changes: {self.simulator.total_state_changes}")
        
        if self.simulator.total_updates > 0:
            avg_changes = self.simulator.total_state_changes / self.simulator.total_updates
            print(f"Avg Changes per Cycle: {avg_changes:.2f}")
        
        print(f"\nChirpStack Messages:")
        print(f"  Uplinks Sent: {stats['uplinks_sent']}")
        print(f"  Downlinks Sent: {stats['downlinks_sent']}")
        print(f"  Total Messages: {stats['uplinks_sent'] + stats['downlinks_sent']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        
        if self.simulator.start_time:
            from datetime import datetime
            duration = (datetime.now() - self.simulator.start_time).total_seconds()
            print(f"\nUptime: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        print("="*70 + "\n")
    
    def do_exit(self, arg):
        """Exit the simulator"""
        if self.simulator and self.simulator.running:
            print("Stopping simulation...")
            self.simulator.stop()
        
        print("Goodbye!")
        return True
    
    def do_quit(self, arg):
        """Exit the simulator"""
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Handle Ctrl+D"""
        print()
        return self.do_exit(arg)


def main():
    """Main entry point for interactive CLI"""
    cli = SimulatorCLI()
    
    # Auto-initialize
    print("Auto-initializing simulator in mock mode...")
    cli.do_init('--mock')
    
    # Start command loop
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted!")
        cli.do_exit('')


if __name__ == '__main__':
    main()
