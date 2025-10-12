# Smart Parking Simulator
## 100 Parking Sensors + Busylights Testing Platform

A comprehensive Python-based simulator for testing smart parking systems with 100 ultrasonic LoRaWAN parking sensors and Kuando Busylight IoT devices integrated with ChirpStack.

---

## 🎯 Features

- **100 Simultaneous Devices**: Simulates 100 parking spaces with paired sensors and busylights
- **ChirpStack Integration**: Full integration with ChirpStack LoRaWAN Network Server API
- **Realistic Behavior**: Simulates realistic parking patterns, sensor readings, and timing
- **Multiple Scenarios**: Rush hour, normal operation, sensor failures, network issues
- **Interactive Control**: CLI for real-time control and monitoring
- **Mock Mode**: Test without actual ChirpStack connection
- **Visual Dashboard**: Terminal-based visualization of parking lot status
- **Comprehensive Logging**: Detailed logs of all sensor and busylight activities

---

## 📋 System Requirements

- Python 3.8+
- ChirpStack v4 instance (optional - can run in mock mode)
- Linux/macOS/Windows with Python

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure ChirpStack Connection

Edit `config.yaml`:

```yaml
chirpstack:
  api_url: "http://your-chirpstack-server:8080/api"
  api_token: "your_api_token_here"
  tenant_id: "your_tenant_id"
  application_id: "your_application_id"
```

### 3. Run Simulator

**Option A: Interactive Mode (Recommended)**

```bash
python interactive_cli.py
```

**Option B: Direct Mode**

```bash
# With ChirpStack
python simulator.py

# Mock mode (no ChirpStack needed)
python simulator.py --mock

# Run for specific duration
python simulator.py --mock --duration 300  # 5 minutes
```

---

## 🎮 Interactive CLI Commands

Once in the interactive CLI:

```
(parking) help              # Show all commands
(parking) init              # Initialize simulator (with ChirpStack)
(parking) init --mock       # Initialize in mock mode
(parking) start             # Start simulation
(parking) status            # Show current status
(parking) show              # Visual parking lot display
(parking) sensor 5          # Details for sensor #5
(parking) busylight 10      # Details for busylight #10
(parking) force 5 occupied  # Force sensor 5 to occupied
(parking) fill 75           # Fill to 75% occupancy
(parking) rush              # Simulate rush hour
(parking) clear             # Clear all spaces
(parking) test 3            # Test busylight #3 patterns
(parking) stats             # Detailed statistics
(parking) stop              # Stop simulation
(parking) exit              # Exit program
```

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Parking Simulator                         │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  100 Sensors     │         │  100 Busylights  │         │
│  │  (Class A)       │         │  (Class C)       │         │
│  └────────┬─────────┘         └────────▲─────────┘         │
│           │                             │                    │
│           │ Uplinks                     │ Downlinks         │
│           │                             │                    │
│           ▼                             │                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           ChirpStack API Client                       │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
            ┌─────────────────────┐
            │  ChirpStack Server  │
            │  (LoRaWAN NS/AS)    │
            └─────────────────────┘
```

### Device Simulation

**Parking Sensor**
- Simulates ultrasonic distance measurements
- Reports occupancy changes via LoRaWAN uplinks
- Realistic parking duration with statistical variation
- Battery level tracking
- Sensor failure simulation
- Time-of-day behavior (rush hour, lunch time)

**Busylight**
- Receives LoRaWAN downlinks (Class C)
- 6 color states: Green, Red, Orange, Blue, White, Off
- Blinking patterns for alerts
- Immediate response to downlink commands

### Payload Formats

**Sensor Uplink (5 bytes)**
```
Byte 0-1: Distance in cm (uint16, big-endian)
Byte 2:   Battery level (0-100)
Byte 3:   State (0=Available, 1=Occupied, 2=Reserved, 3=Maintenance, 255=Unknown)
Byte 4:   Message counter
```

**Busylight Downlink (5 bytes)**
```
Byte 0: Red (0-255)
Byte 1: Green (0-255)
Byte 2: Blue (0-255)
Byte 3: On-time (0-255)
Byte 4: Off-time (0-255)
```

---

## 🎨 Color Schemes

### Default Parking States

| State          | Color           | Hex Payload    | Visual |
|----------------|-----------------|----------------|--------|
| Available      | Green           | 0064000FF00    | 🟢     |
| Occupied       | Red             | 6400000FF00    | 🔴     |
| Reserved       | Orange          | FFA5000FF00    | 🟠     |
| Expiring Soon  | Blinking Orange | FFA5007F7F     | 🟠💫   |
| Maintenance    | Blue            | 0000640FF00    | 🔵     |
| Unknown/Error  | Blinking White  | FFFFFF7F7F     | ⚪💫   |

---

## ⚙️ Configuration

### Key Configuration Options

**Simulation Parameters** (`config.yaml`)

```yaml
simulation:
  num_parking_spaces: 100
  sensor_update_interval: 60  # seconds
  sensor_update_jitter: 10    # random variation
```

**Parking Behavior**

```yaml
behavior:
  avg_parking_duration: 45    # minutes
  parking_duration_std: 15    # standard deviation
  arrival_rate: 0.01          # probability per minute
  initial_occupancy: 0.3      # 30% initially occupied
```

**Scenarios**

```yaml
scenarios:
  rush_hour:
    enabled: true
    start_hour: 8
    end_hour: 10
    arrival_multiplier: 5.0   # 5x normal arrival rate
```

---

## 📊 Testing Scenarios

### Predefined Test Scenarios

1. **Normal Operation**
   - Standard parking behavior
   - No failures
   - Realistic occupancy patterns

2. **High Load**
   - 10x arrival rate
   - Stress test ChirpStack communication
   - Maximum message throughput

3. **Network Issues**
   - 15% packet loss simulation
   - Tests retry mechanisms
   - Validates error handling

4. **Sensor Failures**
   - 5% random sensor failures
   - Tests unknown state handling
   - Validates monitoring alerts

### Running Scenarios

```python
# In interactive CLI
(parking) scenario "High Load"

# Or programmatically
simulator.run_test_scenario("Network Issues")
```

---

## 🔍 Monitoring & Debugging

### Real-time Status Display

```bash
(parking) status
```

Output:
```
======================================================================
SIMULATOR STATUS
======================================================================
Total Spaces: 100
Occupied: 67 (67.0%)
Available: 28 (28.0%)
Reserved: 5
Unknown: 0

Status: RUNNING ✓
Update Cycles: 45
State Changes: 123

ChirpStack:
  Uplinks: 123
  Downlinks: 123
  Errors: 0
======================================================================
```

### Visual Parking Lot

```bash
(parking) show
```

Output:
```
[Parking Lot Status]
  IDs:      0    1    2    3    4    5    6    7    8    9
  Lights: 🟠  🟠  🟠  🟠  🟠  🟢  🔴  🟢  🔴  🔴
  States: res  res  res  res  res  ava  occ  ava  occ  occ
```

### Individual Device Inspection

```bash
(parking) sensor 42
```

Output:
```
======================================================================
SENSOR 42 DETAILS
======================================================================
DEV_EUI: PARK00000042
State: occupied
Distance: 0.987 m
Battery: 99.8%
Operational: True
Message Count: 15
Last Update: 2025-10-12 14:23:45

Parking Duration: 23.4 minutes
Expected Departure: 18 minutes
======================================================================
```

---

## 🧪 Testing Workflows

### 1. Basic Functionality Test

```bash
python interactive_cli.py
```

```
(parking) init --mock
(parking) start
(parking) fill 50        # Fill to 50%
(parking) show           # Verify visual display
(parking) sensor 10      # Check individual sensor
(parking) stats          # Review statistics
(parking) stop
```

### 2. Rush Hour Simulation

```
(parking) clear          # Start with empty lot
(parking) rush           # Rapid fill simulation
(parking) show           # See full lot
(parking) clear          # Empty again
```

### 3. Manual State Testing

```
(parking) force 5 occupied
(parking) force 6 occupied
(parking) force 7 occupied
(parking) show
(parking) force 5 available
(parking) show
```

### 4. Busylight Pattern Testing

```
(parking) test 10        # Test all colors on busylight 10
```

---

## 🔌 ChirpStack Integration

### Setting Up ChirpStack

1. **Get API Token**
   - Login to ChirpStack web interface
   - Navigate to API Keys
   - Generate new key with read/write permissions

2. **Get IDs**
   ```bash
   # Get Tenant ID
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8080/api/tenants
   
   # Get Application ID
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8080/api/applications?tenantId=TENANT_ID
   ```

3. **Update Config**
   Edit `config.yaml` with your IDs and token

4. **Test Connection**
   ```python
   from chirpstack_client import ChirpStackClient
   import yaml
   
   with open('config.yaml') as f:
       config = yaml.safe_load(f)
   
   client = ChirpStackClient(config)
   client.test_connection()
   ```

### Integration Points

- **Uplink Handling**: Sensors send uplinks → ChirpStack → Your Application
- **Downlink Queueing**: Your Application → ChirpStack → Busylights
- **Device Management**: Automated device registration/deregistration
- **Statistics**: Real-time message counting and error tracking

---

## 📈 Performance Characteristics

### Expected Load

- **100 sensors** updating every 60 seconds = ~1.67 uplinks/second
- **100 busylights** receiving downlinks = ~1.67 downlinks/second
- **Total throughput**: ~3.3 messages/second (sustained)
- **Peak load** (rush hour): ~16 messages/second

### LoRaWAN Considerations

- **Duty Cycle (EU868)**: 1% per sub-band
- **Time-on-Air**: ~50ms per message (SF7)
- **Gateway Capacity**: Single gateway can handle this load easily
- **Collision Risk**: Very low at this message rate

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: `Connection refused to ChirpStack`
```bash
# Solution: Use mock mode or check ChirpStack URL
python simulator.py --mock
```

**Issue**: `Devices not appearing in ChirpStack`
```bash
# Verify devices are registered
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8080/api/applications/APP_ID/devices
```

**Issue**: `High error rate`
```bash
# Check ChirpStack logs
docker logs chirpstack
```

### Debug Mode

Enable detailed logging:
```yaml
monitoring:
  log_level: "DEBUG"
  log_file: "parking_simulation.log"
```

---

## 📚 API Reference

### ParkingSensor Class

```python
sensor = ParkingSensor(sensor_id=0, dev_eui="PARK00000000", config=config)

# Methods
sensor.update()                          # Update sensor state
payload = sensor.get_uplink_payload()    # Get LoRaWAN payload
status = sensor.get_status_dict()        # Get status as dict
sensor._park_car()                       # Simulate car arrival
sensor._car_departs()                    # Simulate car departure
```

### Busylight Class

```python
light = Busylight(light_id=0, dev_eui="BUSY00000000", config=config)

# Methods
light.process_downlink(payload_bytes)              # Process binary payload
light.process_downlink_hex("0064000FF00")         # Process hex string
light.set_color_from_parking_state("available")   # Set by state name
light.turn_off()                                  # Turn off
light.test_pattern()                              # Test all colors
```

### ChirpStackClient Class

```python
client = ChirpStackClient(config)

# Methods
client.send_uplink(dev_eui, fport, payload)       # Send uplink
client.enqueue_downlink(dev_eui, fport, payload)  # Queue downlink
client.get_device_queue(dev_eui)                  # Get downlink queue
client.flush_device_queue(dev_eui)                # Clear queue
client.test_connection()                          # Test API connection
```

---

## 🎯 Use Cases

### 1. Application Development
Test your parking management application logic without physical hardware.

### 2. Load Testing
Verify ChirpStack configuration handles 100+ devices simultaneously.

### 3. Integration Testing
Test integration between sensors, busylights, and your backend.

### 4. UI/UX Development
Generate realistic data for dashboard development.

### 5. Training & Demos
Demonstrate smart parking system capabilities without physical deployment.

---

## 🔮 Future Enhancements

- [ ] Web-based dashboard
- [ ] Real-time metrics export (Prometheus/Grafana)
- [ ] MQTT integration for alternative messaging
- [ ] Advanced failure scenarios (gateway failures, network splits)
- [ ] Multi-floor parking garage simulation
- [ ] Payment/reservation system integration
- [ ] Historical data playback
- [ ] Performance benchmarking suite

---

## 📝 License

This simulator is provided as-is for testing and development purposes.

---

## 🤝 Contributing

Based on our previous ChirpStack and smart parking discussions. Feedback and improvements welcome!

---

## 📞 Support

For issues related to:
- **ChirpStack**: https://www.chirpstack.io/docs/
- **Kuando Busylight**: https://busylight.com/
- **LoRaWAN**: https://lora-alliance.org/

---

## 🎓 Getting Started Example

```bash
# 1. Install
pip install -r requirements.txt

# 2. Start interactive CLI
python interactive_cli.py

# 3. Initialize in mock mode
(parking) init --mock

# 4. Start simulation
(parking) start

# 5. Fill parking lot to 60%
(parking) fill 60

# 6. Watch it run
(parking) show
(parking) status

# 7. Simulate rush hour
(parking) rush

# 8. Check final stats
(parking) stats

# 9. Exit
(parking) exit
```

**That's it! You now have 100 simulated parking sensors and busylights running!** 🎉
