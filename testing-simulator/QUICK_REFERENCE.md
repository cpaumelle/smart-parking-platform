# Quick Reference Guide

## Installation

```bash
pip install -r requirements.txt
```

## Running Options

### 1. Interactive CLI (Recommended)
```bash
python interactive_cli.py
```

### 2. Quick Demo
```bash
python demo.py
```

### 3. Direct Simulation
```bash
# Mock mode (no ChirpStack)
python simulator.py --mock

# With ChirpStack
python simulator.py

# Timed run
python simulator.py --mock --duration 300
```

## Common CLI Commands

| Command | Description |
|---------|-------------|
| `init --mock` | Initialize in mock mode |
| `start` | Start simulation |
| `stop` | Stop simulation |
| `status` | Show status summary |
| `show` | Visual parking display |
| `sensor <id>` | Inspect sensor |
| `busylight <id>` | Inspect busylight |
| `force <id> <state>` | Force state change |
| `fill <pct>` | Fill to percentage |
| `rush` | Simulate rush hour |
| `clear` | Clear all spaces |
| `stats` | Detailed statistics |
| `exit` | Exit program |

## Testing Workflow

```bash
# 1. Start
python interactive_cli.py

# 2. In CLI
(parking) init --mock
(parking) start
(parking) fill 50
(parking) show
(parking) rush
(parking) stats
(parking) exit
```

## Configuration Quick Edit

```yaml
# config.yaml
simulation:
  num_parking_spaces: 100
  sensor_update_interval: 60  # How often to check

behavior:
  avg_parking_duration: 45    # Minutes
  arrival_rate: 0.01          # Per minute probability
  initial_occupancy: 0.3      # 30%

chirpstack:
  api_url: "http://localhost:8080/api"
  api_token: "YOUR_TOKEN"
```

## Busylight Color Payloads

| State | Hex Payload | Visual |
|-------|-------------|--------|
| Green (Available) | `0064000FF00` | 🟢 |
| Red (Occupied) | `6400000FF00` | 🔴 |
| Orange (Reserved) | `FFA5000FF00` | 🟠 |
| Blinking Orange | `FFA5007F7F` | 🟠💫 |
| Blue (Maintenance) | `0000640FF00` | 🔵 |
| White (Unknown) | `FFFFFF7F7F` | ⚪💫 |
| Off | `FFFFFF00FF` | ⚫ |

## Troubleshooting

**Can't connect to ChirpStack?**
→ Use `--mock` mode

**Want to see what's happening?**
→ Use `show` and `status` commands

**Need to test specific scenarios?**
→ Use `force` and `fill` commands

**Want realistic simulation?**
→ Just `start` and let it run

## Files Overview

- `simulator.py` - Main simulator engine
- `parking_sensor.py` - Sensor simulation logic
- `busylight.py` - Busylight simulation logic
- `chirpstack_client.py` - ChirpStack API client
- `interactive_cli.py` - Interactive control interface
- `demo.py` - Quick demonstration script
- `config.yaml` - Configuration file
- `requirements.txt` - Python dependencies
- `README.md` - Complete documentation
- `QUICK_REFERENCE.md` - This file

## Example Python Usage

```python
from simulator import ParkingSimulator

# Create and start
sim = ParkingSimulator(mock_mode=True)
sim.start()

# Force state changes
sim.force_state_change(5, 'occupied')

# Get sensor info
sensor = sim.get_sensor_by_id(10)
print(sensor.get_status_dict())

# Get busylight info
light = sim.get_busylight_by_id(10)
print(light.get_status_dict())

# Stop when done
sim.stop()
```

## Architecture Summary

```
100 Sensors → Uplinks → ChirpStack API
                            ↓
                       Your Logic
                            ↓
ChirpStack API → Downlinks → 100 Busylights
```

## Key Features

✅ 100 simultaneous devices  
✅ Realistic parking behavior  
✅ ChirpStack integration  
✅ Mock mode for testing  
✅ Interactive control  
✅ Visual monitoring  
✅ Comprehensive logging  
✅ Multiple test scenarios  

## Need Help?

1. Check `README.md` for detailed docs
2. Run `python interactive_cli.py` and type `help`
3. Try `python demo.py` to see it in action
4. Review the code - it's well commented!

---

**Happy Testing!** 🚗🅿️
