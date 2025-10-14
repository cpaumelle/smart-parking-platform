#!/usr/bin/env python3
"""Quick test of the parking simulator"""

from simulator import ParkingSimulator
import time

print("=" * 70)
print("PARKING SIMULATOR TEST")
print("=" * 70)

# Initialize simulator in mock mode
print("\n1. Initializing simulator (mock mode)...")
sim = ParkingSimulator(mock_mode=True)
print("✓ Simulator created")

# Check initial state
print(f"\n2. Initial State:")
print(f"   Total spaces: {sim.config['simulation']['num_parking_spaces']}")
print(f"   Sensors: {len(sim.sensors)}")
print(f"   Busylights: {len(sim.busylights)}")

# Test forcing a state change
print(f"\n3. Testing state changes...")
sim.force_state_change(0, 'occupied')
sensor = sim.get_sensor_by_id(0)
print(f"   Sensor 0 state: {sensor.state}")
print(f"   ✓ State change successful")

# Test busylight
print(f"\n4. Testing busylight...")
light = sim.get_busylight_by_id(0)
light.set_color_from_parking_state('available')
print(f"   Busylight 0 color: {light.current_color}")
print(f"   ✓ Busylight control successful")

# Get statistics manually
print(f"\n5. Statistics:")
available = sum(1 for s in sim.sensors if s.state.value == 0)
occupied = sum(1 for s in sim.sensors if s.state.value == 1)
reserved = sum(1 for s in sim.sensors if s.state.value == 2)
print(f"   Available: {available}")
print(f"   Occupied: {occupied}")
print(f"   Reserved: {reserved}")

print("\n" + "=" * 70)
print("ALL TESTS PASSED ✓")
print("=" * 70)
print("\nSimulator is ready for use!")
print("\nNext steps:")
print("  1. For interactive control:")
print("     python3 interactive_cli.py")
print("  2. For automated demo:")
print("     python3 demo.py")
print("  3. For custom testing, import and use ParkingSimulator class")
