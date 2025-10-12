# Setup Guide - Smart Parking Simulator

## 🎯 What You're Getting

A complete Python-based simulator that can test 100 parking sensors and 100 busylights simultaneously, with full ChirpStack integration.

## 📦 Package Contents

✅ **simulator.py** - Main simulation engine  
✅ **parking_sensor.py** - Ultrasonic sensor simulation (LoRaWAN Class A)  
✅ **busylight.py** - Busylight IoT simulation (LoRaWAN Class C)  
✅ **chirpstack_client.py** - ChirpStack API integration  
✅ **interactive_cli.py** - Interactive control interface  
✅ **demo.py** - Quick demonstration script  
✅ **config.yaml** - Configuration file  
✅ **requirements.txt** - Python dependencies  
✅ **README.md** - Complete documentation  
✅ **QUICK_REFERENCE.md** - Command cheat sheet  
✅ **ARCHITECTURE.txt** - System architecture diagrams  

## 🚀 Getting Started (5 Minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**That's it!** Just 2 dependencies: `pyyaml` and `requests`

### Step 2: Try the Demo

```bash
python demo.py
```

This runs a guided demo showing:
- 100 parking spaces initialized
- Morning rush hour simulation
- Evening departure simulation
- Busylight color testing
- Real-time statistics

### Step 3: Interactive Control

```bash
python interactive_cli.py
```

Then inside the CLI:
```
(parking) init --mock
(parking) start
(parking) fill 60
(parking) show
(parking) rush
(parking) stats
```

## 🔧 Configuration (Optional)

### Edit config.yaml

```yaml
simulation:
  num_parking_spaces: 100        # Change to test different sizes
  sensor_update_interval: 60     # Seconds between updates

behavior:
  avg_parking_duration: 45       # Average minutes parked
  arrival_rate: 0.01             # Probability of car arriving
  initial_occupancy: 0.3         # Start 30% full

# For rush hour, lunch time scenarios, etc.
scenarios:
  rush_hour:
    enabled: true
    start_hour: 8
    end_hour: 10
    arrival_multiplier: 5.0      # 5x more cars
```

## 🌐 Connecting to Real ChirpStack

### Prerequisites

You need:
1. ChirpStack v4 server running
2. API token
3. Tenant ID
4. Application ID

### Get Your Credentials

#### 1. Login to ChirpStack Web UI

#### 2. Create API Token
- Navigate to: API Keys
- Click: Add API Key
- Name: "Parking Simulator"
- Save the token (you'll only see it once!)

#### 3. Get Tenant ID
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://your-server:8080/api/tenants
```

#### 4. Get Application ID
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://your-server:8080/api/applications?tenantId=YOUR_TENANT_ID
```

### Update config.yaml

```yaml
chirpstack:
  api_url: "http://your-server:8080/api"
  api_token: "eyJ0eXAiOiJKV1QiLC..."     # Your actual token
  tenant_id: "52f14cd4-c6f1-4fbd-8f87-4025e1d49242"
  application_id: "b6754a3d-e3cf-4f4d-8e30-b6d1c0f8a01d"
```

### Test Connection

```bash
python interactive_cli.py
```

```
(parking) init          # Without --mock
```

If successful, you'll see:
```
[ChirpStack] Connection successful!
✓ Simulator initialized successfully!
```

## 📊 Usage Patterns

### Pattern 1: Quick Test
```bash
python demo.py
# Watch automated demo
```

### Pattern 2: Interactive Testing
```bash
python interactive_cli.py
(parking) init --mock
(parking) start
(parking) fill 80           # Test at 80% occupancy
(parking) sensor 25         # Inspect specific sensor
(parking) force 25 available
(parking) show
```

### Pattern 3: Long-Running Simulation
```bash
python simulator.py --mock --duration 3600
# Runs for 1 hour, then exits with statistics
```

### Pattern 4: Real ChirpStack Integration
```bash
python interactive_cli.py
(parking) init              # Use real ChirpStack
(parking) start
# Let it run continuously
# Check ChirpStack UI for device messages
```

## 🎮 Common Tasks

### Fill parking lot to X%
```
(parking) fill 75
```

### Simulate rush hour
```
(parking) rush
```

### Clear all spaces
```
(parking) clear
```

### Test individual busylight
```
(parking) test 10
```

### Force specific state
```
(parking) force 5 occupied
(parking) force 6 available
(parking) force 7 reserved
```

### Monitor specific sensor
```
(parking) sensor 42
```

### Get real-time stats
```
(parking) stats
```

### Visual parking display
```
(parking) show
```

## 🐛 Troubleshooting

### Problem: Can't install dependencies
**Solution:**
```bash
python3 -m pip install --user -r requirements.txt
```

### Problem: ChirpStack connection fails
**Solution:** Use mock mode while testing
```bash
python simulator.py --mock
```

### Problem: Permission denied on scripts
**Solution:**
```bash
chmod +x *.py
```

### Problem: Want to see debug info
**Solution:** Edit config.yaml
```yaml
monitoring:
  log_level: "DEBUG"
  log_file: "debug.log"
```

## 📚 Next Steps

### 1. Learn the CLI
```bash
python interactive_cli.py
(parking) help
```

### 2. Read the Docs
- **README.md** - Complete documentation
- **QUICK_REFERENCE.md** - Command cheat sheet
- **ARCHITECTURE.txt** - How it works

### 3. Customize Behavior
- Edit **config.yaml**
- Adjust parking durations
- Change arrival rates
- Add custom scenarios

### 4. Integrate with Your System
- Connect to real ChirpStack
- Process uplinks in your application
- Send downlinks to busylights
- Build your parking management logic

### 5. Extend the Simulator
- Modify **parking_sensor.py** for custom sensor behavior
- Edit **busylight.py** for custom light patterns
- Add scenarios to **config.yaml**
- Create custom test scripts

## 🎓 Learning Resources

### Understanding LoRaWAN Classes
- **Class A**: Sensors (send uplinks, receive in windows)
- **Class C**: Busylights (always listening for downlinks)

### Message Flow
1. Sensor detects car → Sends uplink → Your app processes
2. Your app decides color → Sends downlink → Busylight displays

### Testing Strategy
1. Start with mock mode
2. Test scenarios interactively
3. Verify statistics
4. Connect to real ChirpStack
5. Scale up gradually

## ✅ Verification Checklist

After setup, verify:

- [ ] Dependencies installed: `pip list | grep -E "pyyaml|requests"`
- [ ] Demo runs: `python demo.py`
- [ ] Interactive CLI works: `python interactive_cli.py`
- [ ] Config file present: `ls config.yaml`
- [ ] Can fill parking lot: `(parking) fill 50`
- [ ] Visual display works: `(parking) show`
- [ ] Stats are collected: `(parking) stats`
- [ ] ChirpStack connects (if using): `(parking) init` (without --mock)

## 🎉 You're Ready!

You now have a complete testing platform for:
- 100 parking sensors
- 100 busylights
- Realistic parking simulation
- ChirpStack integration
- Interactive control
- Automated testing

**Start with:**
```bash
python demo.py
```

**Then explore:**
```bash
python interactive_cli.py
```

**Questions?** Check README.md for detailed docs!

---

**Happy Testing!** 🚗🅿️💡
