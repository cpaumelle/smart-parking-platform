# Kuando Busylight - Tested Color Results

**Device EUI:** 2020203705250102
**Test Date:** 2025-10-12
**Location:** /opt/smart-parking

---

## Canonical Parking Colors

These are the verified, production-ready colors for the smart parking system.

### Available (Green)
| Property | Value |
|----------|-------|
| **Color Name** | Green |
| **Use Case** | Parking spot available |
| **RGB Values** | (0, 0, 255) |
| **Hex Payload** | `0000FFFF00` |
| **Byte Order** | R=0, B=0, G=255, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |

### Occupied (Red)
| Property | Value |
|----------|-------|
| **Color Name** | Red |
| **Use Case** | Parking spot occupied |
| **RGB Values** | (255, 0, 0) |
| **Hex Payload** | `FF0000FF00` |
| **Byte Order** | R=255, B=0, G=0, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |

### Reserved (Orange) - CANONICAL
| Property | Value |
|----------|-------|
| **Color Name** | Orange (Deep Red-Orange) |
| **Use Case** | Parking spot reserved |
| **RGB Values** | (255, 0, 50) |
| **Hex Payload** | `FF0032FF00` |
| **Byte Order** | R=255, B=0, G=50, On=255, Off=0 |
| **Status** | ✅ Tested & Approved - CANONICAL ORANGE |
| **Notes** | Perfect balance - not too yellow, rich orange tone |

### VIP/Premium (Purple) - CANONICAL
| Property | Value |
|----------|-------|
| **Color Name** | Purple (Blue-Violet) |
| **Use Case** | VIP or premium parking spot |
| **RGB Values** | (100, 180, 0) |
| **Hex Payload** | `64B400FF00` |
| **Byte Order** | R=100, B=180, G=0, On=255, Off=0 |
| **Status** | ✅ Tested & Approved - CANONICAL PURPLE |
| **Notes** | Nice blue-violet tone, distinct from other colors |

### Maintenance (Blue)
| Property | Value |
|----------|-------|
| **Color Name** | Blue |
| **Use Case** | Spot disabled / under maintenance |
| **RGB Values** | (0, 255, 0) |
| **Hex Payload** | `00FF00FF00` |
| **Byte Order** | R=0, B=255, G=0, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |

### EV Charging (Cyan)
| Property | Value |
|----------|-------|
| **Color Name** | Cyan (Aqua) |
| **Use Case** | Electric vehicle charging spot |
| **RGB Values** | (0, 255, 255) |
| **Hex Payload** | `00FFFFFF00` |
| **Byte Order** | R=0, B=255, G=255, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |
| **Notes** | Blue + Green mix, perfect for EV charging |

### Warning/Expiring (Yellow)
| Property | Value |
|----------|-------|
| **Color Name** | Yellow |
| **Use Case** | Reservation expiring soon / Warning |
| **RGB Values** | (255, 0, 255) |
| **Hex Payload** | `FF00FFFF00` |
| **Byte Order** | R=255, B=0, G=255, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |
| **Notes** | Red + Green mix, high visibility for warnings |

### Handicap/Special (Pink)
| Property | Value |
|----------|-------|
| **Color Name** | Pink |
| **Use Case** | Handicap or special needs spot |
| **RGB Values** | (255, 100, 0) |
| **Hex Payload** | `FF6400FF00` |
| **Byte Order** | R=255, B=100, G=0, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |
| **Notes** | Red + Blue mix, soft and distinctive |

### System Active (White)
| Property | Value |
|----------|-------|
| **Color Name** | White |
| **Use Case** | System testing / active |
| **RGB Values** | (255, 255, 255) |
| **Hex Payload** | `FFFFFFFF00` |
| **Byte Order** | R=255, B=255, G=255, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |

### Off
| Property | Value |
|----------|-------|
| **Color Name** | Off |
| **Use Case** | Light turned off |
| **RGB Values** | (0, 0, 0) |
| **Hex Payload** | `000000FF00` |
| **Byte Order** | R=0, B=0, G=0, On=255, Off=0 |
| **Status** | ✅ Tested & Approved |

---

## Color Testing History

### Orange Iteration Testing (2025-10-12)

We tested multiple orange values to find the perfect balance:

| Test # | RGB Values | Green Value | Hex Payload | Result |
|--------|-----------|-------------|-------------|---------|
| 1 | (255, 0, 165) | 165 | `FF00A5FF00` | ❌ Too yellow |
| 2 | (255, 0, 100) | 100 | `FF0064FF00` | ⚠️ Still yellowish |
| 3 | (255, 0, 50) | 50 | `FF0032FF00` | ✅ **Perfect\!** |

**Conclusion:** Green value of 50 provides the ideal red-orange color that clearly distinguishes from both pure red and yellow.

### Purple Iteration Testing (2025-10-12)

We tested multiple purple values to find the right balance:

| Test # | RGB Values | Red/Blue Ratio | Hex Payload | Result |
|--------|-----------|----------------|-------------|---------|
| 1 | (128, 128, 0) | Equal | `808000FF00` | ⚠️ Too balanced |
| 2 | (100, 180, 0) | More blue | `64B400FF00` | ✅ **Perfect\!** |

**Conclusion:** RGB(100, 180, 0) provides a nice blue-violet purple that is distinct and appealing.

---

## Complete Color Palette Summary

| Color | Payload | Use Case |
|-------|---------|----------|
| 🟢 Green | `0000FFFF00` | Available |
| 🔴 Red | `FF0000FF00` | Occupied |
| 🟠 Orange | `FF0032FF00` | Reserved |
| 🟣 Purple | `64B400FF00` | VIP/Premium |
| 🔵 Blue | `00FF00FF00` | Maintenance |
| 🔷 Cyan | `00FFFFFF00` | EV Charging |
| 🟡 Yellow | `FF00FFFF00` | Warning/Expiring |
| 🩷 Pink | `FF6400FF00` | Handicap/Special |
| ⚪ White | `FFFFFFFF00` | System Active |
| ⚫ Off | `000000FF00` | Light Off |

---

## Payload Format Reference

Byte 0: Red intensity (0-255)
Byte 1: Blue intensity (0-255)
Byte 2: Green intensity (0-255)
Byte 3: On duration (255 = solid, 0-254 = custom)
Byte 4: Off duration (0 = no flashing, 1-255 = flash off time)

**Important Notes:**
- FPort: **15** (required for Kuando Busylight)
- Byte order is **R-B-G** (NOT R-G-B\!)
- Device is **Class C** - receives downlinks immediately
- All colors use solid pattern: On=255, Off=0

---

## Quick Reference Commands

### Python Command Template
```python
import requests

DEVICE_EUI = "2020203705250102"
DOWNLINK_URL = "http://localhost:8000/downlink/send"
FPORT = 15

# Example: Send canonical orange
payload = bytes([255, 0, 50, 255, 0]).hex().upper()  # FF0032FF00

response = requests.post(
    DOWNLINK_URL,
    json={
        "dev_eui": DEVICE_EUI,
        "fport": FPORT,
        "data": payload,
        "confirmed": False
    }
)
```

### Docker Command Template
```bash
sudo docker compose exec -T downlink-service python3 << 'EOF'
import requests

requests.post(
    "http://localhost:8000/downlink/send",
    json={
        "dev_eui": "2020203705250102",
        "fport": 15,
        "data": "FF0032FF00",  # Canonical orange
        "confirmed": False
    }
)
EOF
```

---

## Testing Complete Color Cycle

To test all colors in sequence:

```python
import requests
import time

DEVICE_EUI = "2020203705250102"
DOWNLINK_URL = "http://localhost:8000/downlink/send"
FPORT = 15

colors = [
    ("Green", "0000FFFF00"),
    ("Red", "FF0000FF00"),
    ("Orange", "FF0032FF00"),
    ("Purple", "64B400FF00"),
    ("Blue", "00FF00FF00"),
    ("Cyan", "00FFFFFF00"),
    ("Yellow", "FF00FFFF00"),
    ("Pink", "FF6400FF00"),
    ("White", "FFFFFFFF00"),
    ("Off", "000000FF00"),
]

for name, payload in colors:
    print(f"Sending {name}...")
    requests.post(DOWNLINK_URL, json={
        "dev_eui": DEVICE_EUI,
        "fport": FPORT,
        "data": payload,
        "confirmed": False
    })
    time.sleep(3)
```

---

**Last Updated:** 2025-10-12
**Device:** Kuando Busylight IoT Omega LoRaWAN
**Tested By:** Claude Code + User
**Total Colors Tested:** 10
