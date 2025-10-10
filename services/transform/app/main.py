# main.py - transform
# Version: 0.1.6 - 2025-08-03 08:05 UTC
# Changelog:
# - Use .env CORS_ORIGINS variable for dynamic origin configuration
# - Added verbose request logging middleware for debugging frontend API requests

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import sys
import os
import logging

# Load .env file
load_dotenv()
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from routers.uplinks import router as uplink_router
from routers.locations import router as locations_router
from routers.devices import router as devices_router
from routers.gateways import router as gateways_router

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transform-service")

app = FastAPI(
    title="Transform Service",
    version="0.1.6",
)

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────
# Middleware: log method, path, body, and status code
# ──────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    logger.info(f"⬅️ {request.method} {request.url.path} - Body: {body.decode('utf-8')}")
    response = await call_next(request)
    logger.info(f"➡️ {response.status_code} for {request.method} {request.url.path}")
    return response

# Health
@app.get("/health")
async def health():
    return {"status": "transform service healthy ✅"}

# Routers
app.include_router(uplink_router, prefix="/process-uplink")
app.include_router(locations_router, prefix="/v1/locations")
app.include_router(devices_router, prefix="/v1/devices")
app.include_router(gateways_router, prefix="/v1/gateways")
