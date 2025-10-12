#!/usr/bin/env python3
"""
Quick Start Demo
Demonstrates the parking simulator with a simple automated scenario
"""

import time
import yaml
from simulator import ParkingSimulator


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          Smart Parking Simulator - Quick Demo               ║
║                100 Sensors + 100 Busylights                  ║
╚══════════════════════════════════════════════════════════════╝
    """)


def demo_scenario():
    """Run a demonstration scenario"""
    
    print_banner()
    
    print("📋 Initializing simulator in MOCK mode...")
    print("   (No ChirpStack connection needed for this demo)\n")
    
    # Initialize simulator
    simulator = ParkingSimulator(mock_mode=True)
    
    print("✓ Simulator initialized successfully!")
    print(f"  - {len(simulator.sensors)} parking sensors created")
    print(f"  - {len(simulator.busylights)} busylights created")
    
    input("\nPress ENTER to start the simulation...")
    
    # Start simulation
    simulator.start()
    print("\n🚀 Simulation started!\n")
    
    time.sleep(2)
    
    # Scenario 1: Show initial state
    print("="*70)
    print("SCENARIO 1: Initial State (30% occupied)")
    print("="*70)
    simulator._print_parking_status()
    time.sleep(3)
    
    input("\nPress ENTER to simulate morning rush hour...")
    
    # Scenario 2: Rush hour
    print("\n" + "="*70)
    print("SCENARIO 2: Morning Rush Hour (filling to 90%)")
    print("="*70)
    
    print("\n🚗 Cars arriving rapidly...")
    available = [s for s in simulator.sensors if s.state.value == 'available']
    target = int(simulator.num_spaces * 0.9) - sum(1 for s in simulator.sensors if s.state.value == 'occupied')
    
    for i, sensor in enumerate(available[:target]):
        if i % 20 == 0:
            print(f"  Cars parked: {i}/{target}")
        simulator.force_state_change(sensor.sensor_id, 'occupied')
        if i % 10 == 0:
            time.sleep(0.5)
    
    print(f"\n✓ Rush hour complete! {target} cars parked")
    simulator._print_parking_status()
    
    time.sleep(2)
    
    input("\nPress ENTER to see statistics...")
    
    # Scenario 3: Statistics
    print("\n" + "="*70)
    print("SCENARIO 3: System Statistics")
    print("="*70)
    
    stats = simulator.chirpstack.get_statistics()
    occupied = sum(1 for s in simulator.sensors if s.state.value == 'occupied')
    
    print(f"\nParking Status:")
    print(f"  Occupied: {occupied}/100 ({occupied}%)")
    print(f"  Available: {100-occupied}/100")
    
    print(f"\nMessages Sent:")
    print(f"  Uplinks (sensors): {stats['uplinks_sent']}")
    print(f"  Downlinks (busylights): {stats['downlinks_sent']}")
    print(f"  Total messages: {stats['uplinks_sent'] + stats['downlinks_sent']}")
    
    print(f"\nSimulation Metrics:")
    print(f"  Update cycles: {simulator.total_updates}")
    print(f"  State changes: {simulator.total_state_changes}")
    
    time.sleep(2)
    
    input("\nPress ENTER to simulate evening departure...")
    
    # Scenario 4: Evening departure
    print("\n" + "="*70)
    print("SCENARIO 4: Evening Departure (clearing to 20%)")
    print("="*70)
    
    print("\n🚗 Cars departing...")
    occupied = [s for s in simulator.sensors if s.state.value == 'occupied']
    target = len(occupied) - int(simulator.num_spaces * 0.2)
    
    for i, sensor in enumerate(occupied[:target]):
        if i % 20 == 0:
            print(f"  Cars departed: {i}/{target}")
        simulator.force_state_change(sensor.sensor_id, 'available')
        if i % 10 == 0:
            time.sleep(0.5)
    
    print(f"\n✓ Evening departure complete! {target} cars departed")
    simulator._print_parking_status()
    
    time.sleep(2)
    
    input("\nPress ENTER to test individual busylight...")
    
    # Scenario 5: Busylight test
    print("\n" + "="*70)
    print("SCENARIO 5: Busylight Color Test")
    print("="*70)
    
    print("\nTesting busylight patterns on space #10...")
    light = simulator.busylights[10]
    
    colors = [
        ("available", "Green - Space Available"),
        ("occupied", "Red - Space Occupied"),
        ("reserved", "Orange - Space Reserved"),
        ("expiring_soon", "Blinking Orange - Expiring Soon"),
        ("unknown", "Blinking White - Sensor Error")
    ]
    
    for state, description in colors:
        print(f"\n  Setting: {description}")
        light.set_color_from_parking_state(state)
        print(f"  Visual: {light.get_visual_representation()}")
        print(f"  RGB: ({light.red}, {light.green}, {light.blue})")
        time.sleep(1.5)
    
    light.turn_off()
    print(f"\n  Turned off: {light.get_visual_representation()}")
    
    time.sleep(2)
    
    # Final statistics
    print("\n" + "="*70)
    print("DEMO COMPLETE - Final Statistics")
    print("="*70)
    
    simulator.stop()
    
    print("\n✨ Demo finished!")
    print("\nNext steps:")
    print("  1. Run 'python interactive_cli.py' for full control")
    print("  2. Edit 'config.yaml' to customize behavior")
    print("  3. Connect to real ChirpStack for production testing")
    print("\nFor more information, see README.md")


if __name__ == '__main__':
    try:
        demo_scenario()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted!")
    except Exception as e:
        print(f"\n\nError during demo: {e}")
        import traceback
        traceback.print_exc()
