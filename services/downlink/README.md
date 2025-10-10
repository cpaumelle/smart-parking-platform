# ChirpStack Downlink Service

FastAPI-based REST API wrapper for ChirpStack v4 gRPC API, enabling easy management of downlinks and device resources.

## Features

- 📤 **Send Downlinks**: Queue downlink messages to LoRaWAN devices
- 📋 **Manage Queue**: View and flush downlink queues
- 🔍 **Browse Resources**: List and get details for devices, applications, and gateways
- 📚 **Auto-generated Docs**: Available at `/docs` endpoint
- 🔒 **Secure**: Token-based authentication via ChirpStack API tokens

## Configuration

### 1. Generate ChirpStack API Token

1. Access ChirpStack UI at `https://chirpstack.${DOMAIN}`
2. Navigate to **API Keys** (under tenant or global settings)
3. Click **Add API Key**
4. Set name: `Downlink Service`
5. Enable required permissions:
   - Device: Read, Write (for downlinks and device info)
   - Application: Read (for listing devices)
   - Gateway: Read (for gateway info)
6. Copy the generated token

### 2. Update Environment Variables

Edit `/opt/smart-parking/.env`:

```bash
CHIRPSTACK_API_TOKEN=your_generated_token_here
```

### 3. Start the Service

```bash
cd /opt/smart-parking
sudo docker compose up -d downlink-service
```

## API Endpoints

### Downlink Management

**Send Downlink**
```bash
POST /downlink/send
{
  "dev_eui": "58a0cb00001019bc",
  "fport": 1,
  "data": "AQIDBA==",  # Base64 or hex
  "confirmed": false
}
```

**Get Queue**
```bash
GET /downlink/queue/{dev_eui}
```

**Flush Queue**
```bash
DELETE /downlink/queue/{dev_eui}
```

### Device Management

**Get Device**
```bash
GET /devices/{dev_eui}
```

**List Devices**
```bash
GET /applications/{application_id}/devices?limit=100&offset=0
```

### Application Management

**List Applications**
```bash
GET /applications?limit=100&offset=0
```

**Get Application**
```bash
GET /applications/{application_id}
```

### Gateway Management

**List Gateways**
```bash
GET /gateways?limit=100&offset=0
```

**Get Gateway**
```bash
GET /gateways/{gateway_id}
```

## Usage Examples

### Send Downlink (Base64)

```bash
curl -X POST "https://downlink.${DOMAIN}/downlink/send" \
  -H "Content-Type: application/json" \
  -d '{
    "dev_eui": "58a0cb00001019bc",
    "fport": 1,
    "data": "AQIDBA==",
    "confirmed": false
  }'
```

### Send Downlink (Hex)

```bash
curl -X POST "https://downlink.${DOMAIN}/downlink/send" \
  -H "Content-Type: application/json" \
  -d '{
    "dev_eui": "58a0cb00001019bc",
    "fport": 1,
    "data": "01020304",
    "confirmed": true
  }'
```

### List All Devices

```bash
curl "https://downlink.${DOMAIN}/applications/345b028b-9f0a-4c56-910c-6a05dc2dc22f/devices"
```

### Check Queue Status

```bash
curl "https://downlink.${DOMAIN}/downlink/queue/58a0cb00001019bc"
```

## Interactive Documentation

Once running, access the auto-generated API docs at:

- **Swagger UI**: `https://downlink.${DOMAIN}/docs`
- **ReDoc**: `https://downlink.${DOMAIN}/redoc`

## Architecture

```
Frontend/API
    ↓
downlink.${DOMAIN} (FastAPI REST)
    ↓
ChirpStack gRPC API
    ↓
ChirpStack Network Server
    ↓
Gateway
    ↓
LoRaWAN Device
```

## Logs

```bash
docker logs -f parking-downlink
```

## Troubleshooting

### "ChirpStack gRPC error: Unauthenticated"
- Verify `CHIRPSTACK_API_TOKEN` is set correctly in `.env`
- Check token has required permissions in ChirpStack UI
- Restart service: `docker compose restart downlink-service`

### "Device not found"
- Verify DevEUI is correct (16 hex characters)
- Check device exists in ChirpStack UI

### Connection errors
- Ensure ChirpStack is running: `docker ps | grep chirpstack`
- Check network connectivity: `docker exec parking-downlink ping parking-chirpstack`

## Future Enhancements

- [ ] Database logging of sent downlinks
- [ ] Downlink scheduling and queuing
- [ ] Rate limiting per device
- [ ] Webhook notifications on downlink ack/nack
- [ ] Batch downlink operations
