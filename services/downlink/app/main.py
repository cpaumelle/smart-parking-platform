# main.py - Downlink Service
# Version: 1.0.0 - 2025-10-07
# Purpose: FastAPI wrapper for ChirpStack gRPC API to manage downlinks and device resources

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import logging
import grpc
from chirpstack_api import api

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("downlink-service")

app = FastAPI(
    title="ChirpStack Downlink Service",
    version="1.0.0",
    description="REST API for sending downlinks and managing ChirpStack resources"
)

# CORS - Restricted to allowed origins
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
CHIRPSTACK_API_URL = os.getenv("CHIRPSTACK_API_URL", "localhost:8080")
CHIRPSTACK_API_TOKEN = os.getenv("CHIRPSTACK_API_TOKEN", "")

# ================================================================
# gRPC Client Setup
# ================================================================

def get_grpc_channel():
    """Create gRPC channel with auth token"""
    channel = grpc.insecure_channel(CHIRPSTACK_API_URL)
    return channel

def get_auth_token():
    """Get authentication metadata for gRPC calls"""
    return [("authorization", f"Bearer {CHIRPSTACK_API_TOKEN}")]

# ================================================================
# Pydantic Models
# ================================================================

class DownlinkRequest(BaseModel):
    dev_eui: str
    fport: int
    data: str  # Base64 or hex string
    confirmed: bool = False

class DeviceListQuery(BaseModel):
    application_id: str
    limit: int = 100
    offset: int = 0

# ================================================================
# Health Check
# ================================================================

@app.get("/health")
async def health():
    return {"status": "downlink service healthy ✅"}

# ================================================================
# Downlink Endpoints
# ================================================================

@app.post("/downlink/send")
async def send_downlink(request: DownlinkRequest):
    """
    Send a downlink to a device

    Example payload:
    {
        "dev_eui": "58a0cb00001019bc",
        "fport": 1,
        "data": "AQIDBA==",  # Base64 encoded
        "confirmed": false
    }
    """
    try:
        channel = get_grpc_channel()
        client = api.DeviceServiceStub(channel)

        # Convert hex/base64 string to bytes with proper validation
        import base64
        import re

        data_str = request.data.strip()

        # Check if it's hex (only 0-9, a-f, A-F, even length)
        if re.match(r'^[0-9a-fA-F]+$', data_str) and len(data_str) % 2 == 0:
            # Decode as hex
            try:
                data_bytes = bytes.fromhex(data_str)
                logger.info(f"📦 Decoded as HEX: {data_str} -> {len(data_bytes)} bytes")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid hex string: {e}")
        else:
            # Try base64 decode
            try:
                data_bytes = base64.b64decode(data_str, validate=True)
                logger.info(f"📦 Decoded as Base64: {data_str} -> {len(data_bytes)} bytes")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid data format. Expected hex (0-9a-fA-F) or base64. Error: {e}"
                )

        # Create downlink queue item
        queue_item = api.DeviceQueueItem(
            dev_eui=request.dev_eui,
            confirmed=request.confirmed,
            f_port=request.fport,
            data=data_bytes,
        )

        req = api.EnqueueDeviceQueueItemRequest(
            queue_item=queue_item
        )

        response = client.Enqueue(req, metadata=get_auth_token())

        # Try to get f_cnt if available
        f_cnt = getattr(response, 'f_cnt', None) or getattr(response, 'fCnt', None)

        logger.info(f"✅ Downlink queued: DevEUI={request.dev_eui}, FPort={request.fport}")

        return {
            "status": "queued",
            "dev_eui": request.dev_eui,
            "f_cnt": f_cnt,
            "fport": request.fport,
            "confirmed": request.confirmed
        }

    except grpc.RpcError as e:
        logger.error(f"❌ gRPC error: {e.code()} - {e.details()}")
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        logger.error(f"❌ Error sending downlink: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/downlink/queue/{dev_eui}")
async def get_downlink_queue(dev_eui: str):
    """Get pending downlinks for a device"""
    try:
        channel = get_grpc_channel()
        client = api.DeviceServiceStub(channel)

        req = api.GetDeviceQueueItemsRequest(
            dev_eui=dev_eui,
            count_only=False
        )

        response = client.GetQueue(req, metadata=get_auth_token())

        items = []
        response_items = getattr(response, 'items', []) or getattr(response, 'result', [])
        for item in response_items:
            items.append({
                "f_cnt": getattr(item, 'f_cnt', None) or getattr(item, 'fCnt', None),
                "fport": getattr(item, 'f_port', None) or getattr(item, 'fPort', None),
                "confirmed": getattr(item, 'confirmed', False),
                "data": getattr(item, 'data', b'').hex(),
                "is_pending": getattr(item, 'is_pending', None) or getattr(item, 'isPending', None)
            })

        return {
            "dev_eui": dev_eui,
            "total_count": getattr(response, 'total_count', len(items)) or getattr(response, 'totalCount', len(items)),
            "items": items
        }

    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/downlink/queue/{dev_eui}")
async def flush_downlink_queue(dev_eui: str):
    """Clear all pending downlinks for a device"""
    try:
        channel = get_grpc_channel()
        client = api.DeviceServiceStub(channel)

        req = api.FlushDeviceQueueRequest(dev_eui=dev_eui)
        client.FlushQueue(req, metadata=get_auth_token())

        logger.info(f"✅ Queue flushed for DevEUI={dev_eui}")

        return {
            "status": "flushed",
            "dev_eui": dev_eui
        }

    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# Device Management Endpoints
# ================================================================

@app.get("/devices/{dev_eui}")
async def get_device(dev_eui: str):
    """Get device details"""
    try:
        channel = get_grpc_channel()
        client = api.DeviceServiceStub(channel)

        req = api.GetDeviceRequest(dev_eui=dev_eui)
        response = client.Get(req, metadata=get_auth_token())

        device = response.device
        return {
            "dev_eui": device.dev_eui,
            "name": device.name,
            "description": device.description,
            "application_id": device.application_id,
            "device_profile_id": device.device_profile_id,
            "is_disabled": device.is_disabled,
            "tags": dict(device.tags) if device.tags else {}
        }

    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Device not found")
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/{application_id}/devices")
async def list_devices(application_id: str, limit: int = 100, offset: int = 0):
    """List devices in an application"""
    try:
        channel = get_grpc_channel()
        client = api.DeviceServiceStub(channel)

        req = api.ListDevicesRequest(
            application_id=application_id,
            limit=limit,
            offset=offset
        )

        response = client.List(req, metadata=get_auth_token())

        devices = []
        for item in response.result:
            devices.append({
                "dev_eui": item.dev_eui,
                "name": item.name,
                "description": item.description,
                "device_profile_name": item.device_profile_name,
                "last_seen_at": item.last_seen_at.ToJsonString() if item.last_seen_at else None
            })

        return {
            "total_count": response.total_count,
            "devices": devices
        }

    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# Application Management Endpoints
# ================================================================

@app.get("/applications")
async def list_applications(limit: int = 100, offset: int = 0):
    """List all applications"""
    try:
        channel = get_grpc_channel()
        client = api.ApplicationServiceStub(channel)

        req = api.ListApplicationsRequest(
            limit=limit,
            offset=offset
        )

        response = client.List(req, metadata=get_auth_token())

        applications = []
        for item in response.result:
            applications.append({
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "tenant_id": item.tenant_id
            })

        return {
            "total_count": response.total_count,
            "applications": applications
        }

    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/{application_id}")
async def get_application(application_id: str):
    """Get application details"""
    try:
        channel = get_grpc_channel()
        client = api.ApplicationServiceStub(channel)

        req = api.GetApplicationRequest(id=application_id)
        response = client.Get(req, metadata=get_auth_token())

        app = response.application
        return {
            "id": app.id,
            "name": app.name,
            "description": app.description,
            "tenant_id": app.tenant_id,
            "tags": dict(app.tags) if app.tags else {}
        }

    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Application not found")
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# Gateway Management Endpoints
# ================================================================

@app.get("/gateways")
async def list_gateways(limit: int = 100, offset: int = 0):
    """List all gateways"""
    try:
        channel = get_grpc_channel()
        client = api.GatewayServiceStub(channel)

        req = api.ListGatewaysRequest(
            limit=limit,
            offset=offset
        )

        response = client.List(req, metadata=get_auth_token())

        gateways = []
        for item in response.result:
            gateways.append({
                "gateway_id": item.gateway_id,
                "name": item.name,
                "description": item.description,
                "last_seen_at": item.last_seen_at.ToJsonString() if item.last_seen_at else None,
                "tenant_id": item.tenant_id
            })

        return {
            "total_count": response.total_count,
            "gateways": gateways
        }

    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gateways/{gateway_id}")
async def get_gateway(gateway_id: str):
    """Get gateway details"""
    try:
        channel = get_grpc_channel()
        client = api.GatewayServiceStub(channel)

        req = api.GetGatewayRequest(gateway_id=gateway_id)
        response = client.Get(req, metadata=get_auth_token())

        gw = response.gateway
        return {
            "gateway_id": gw.gateway_id,
            "name": gw.name,
            "description": gw.description,
            "tenant_id": gw.tenant_id,
            "tags": dict(gw.tags) if gw.tags else {},
            "stats_interval_secs": gw.stats_interval_secs
        }

    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Gateway not found")
        raise HTTPException(status_code=500, detail=f"ChirpStack gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
