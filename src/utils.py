"""
Utility functions used across the application
Keep these pure functions without side effects
"""
import hashlib
import secrets
import base64
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import re
import uuid
import logging

logger = logging.getLogger(__name__)

# ============================================================
# ID Generation
# ============================================================

def generate_request_id() -> str:
    """Generate unique request ID for tracing"""
    return f"req_{uuid.uuid4().hex[:12]}"

def get_request_id() -> str:
    """Get or generate request ID"""
    # In production, get from context/header
    return generate_request_id()

# ============================================================
# String Manipulation
# ============================================================

def normalize_deveui(deveui: str) -> str:
    """
    Normalize DevEUI to UPPERCASE hex without separators (database standard)

    Why UPPERCASE:
    - PostgreSQL stores EUIs in uppercase for consistency
    - ChirpStack device tables use uppercase
    - Makes case-insensitive queries unnecessary

    Examples:
        "00:11:22:33:44:55:66:77" -> "0011223344556677"
        "00-11-22-33-44-55-66-77" -> "0011223344556677"
        "0011223344556677" -> "0011223344556677"
        "e8e1e1000103c3f8" -> "E8E1E1000103C3F8"
    """
    if not deveui:
        return ""

    # Remove common separators
    cleaned = deveui.replace(":", "").replace("-", "").replace(" ", "")

    # Validate hex and length (16 hex chars = 8 bytes for LoRaWAN DevEUI)
    if not re.match(r"^[0-9a-fA-F]{16}$", cleaned):
        raise ValueError(f"Invalid DevEUI format: {deveui} (must be 16 hex characters)")

    return cleaned.upper()  # Database standard: UPPERCASE


def normalize_gateway_eui(gw_eui: str) -> str:
    """
    Normalize Gateway EUI to UPPERCASE hex without separators (database standard)

    Examples:
        "7076ff0064030456" -> "7076FF0064030456"
        "70:76:ff:00:64:03:04:56" -> "7076FF0064030456"
    """
    if not gw_eui:
        return ""

    # Remove common separators
    cleaned = gw_eui.replace(":", "").replace("-", "").replace(" ", "")

    # Validate hex and length (16 hex chars = 8 bytes for LoRaWAN Gateway EUI)
    if not re.match(r"^[0-9a-fA-F]{16}$", cleaned):
        raise ValueError(f"Invalid Gateway EUI format: {gw_eui} (must be 16 hex characters)")

    return cleaned.upper()  # Database standard: UPPERCASE

def generate_space_code(building: str, floor: str, number: int) -> str:
    """
    Generate a space code from components
    Example: Building "A", Floor "1", Number 5 -> "A1-005"
    """
    building_code = (building or "X")[:1].upper()
    floor_code = (floor or "0")[:2]
    return f"{building_code}{floor_code}-{number:03d}"

# ============================================================
# Data Encoding/Decoding
# ============================================================

def hex_to_base64(hex_string: str) -> str:
    """Convert hex string to base64"""
    try:
        bytes_data = bytes.fromhex(hex_string)
        return base64.b64encode(bytes_data).decode('ascii')
    except Exception as e:
        logger.error(f"Failed to convert hex to base64: {e}")
        raise ValueError(f"Invalid hex string: {hex_string}")

def base64_to_hex(base64_string: str) -> str:
    """Convert base64 string to hex"""
    try:
        bytes_data = base64.b64decode(base64_string)
        return bytes_data.hex()
    except Exception as e:
        logger.error(f"Failed to convert base64 to hex: {e}")
        raise ValueError(f"Invalid base64 string: {base64_string}")

def detect_encoding(payload: str) -> str:
    """
    Detect if payload is hex or base64 encoded
    Returns: 'hex', 'base64', or 'unknown'
    """
    # Check for hex (only hex chars, even length)
    if re.match(r"^[0-9a-fA-F]+$", payload) and len(payload) % 2 == 0:
        return "hex"

    # Check for base64 (contains base64 chars)
    if re.match(r"^[A-Za-z0-9+/]+=*$", payload):
        return "base64"

    return "unknown"

# ============================================================
# Time Utilities
# ============================================================

def utcnow() -> datetime:
    """Get current UTC time with timezone info"""
    return datetime.now(timezone.utc)

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human readable
    Examples:
        65 -> "1m 5s"
        3665 -> "1h 1m 5s"
        0.5 -> "500ms"
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")

    return " ".join(parts) or "0s"

# ============================================================
# Validation Helpers
# ============================================================

def is_valid_email(email: str) -> bool:
    """Basic email validation"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def is_valid_phone(phone: str) -> bool:
    """Basic phone validation (international format)"""
    # Remove spaces and dashes
    cleaned = phone.replace(" ", "").replace("-", "")
    # Check if starts with + and has 10-15 digits
    return bool(re.match(r"^\+?[1-9]\d{9,14}$", cleaned))

# ============================================================
# Security Helpers
# ============================================================

def generate_api_key() -> str:
    """Generate a secure random API key"""
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage
    Note: In production, use bcrypt from the bcrypt library
    """
    # Simple example - use bcrypt in production!
    return hashlib.sha256(api_key.encode()).hexdigest()

# ============================================================
# Color Mappings (for parking displays)
# ============================================================

def get_display_color(state: str) -> str:
    """
    Get hex color for parking state
    Returns 6-character hex string (RGB)
    """
    color_map = {
        "FREE": "00FF00",      # Green
        "OCCUPIED": "FF0000",   # Red
        "RESERVED": "FFFF00",   # Yellow
        "MAINTENANCE": "FFA500", # Orange
        "ERROR": "0000FF"       # Blue
    }
    return color_map.get(state.upper(), "FFFFFF")  # White for unknown

def parse_rgb_hex(hex_color: str) -> tuple:
    """
    Parse hex color to RGB tuple
    Example: "FF0000" -> (255, 0, 0)
    """
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    raise ValueError(f"Invalid hex color: {hex_color}")

# ============================================================
# Debugging Helpers
# ============================================================

def truncate_string(s: str, max_length: int = 100) -> str:
    """Truncate string for logging"""
    if len(s) <= max_length:
        return s
    return s[:max_length] + "..."

def safe_dict_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value
    Example: safe_dict_get(data, "deviceInfo.devEui")
    """
    keys = path.split(".")
    value = d

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default

    return value

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging
    Example: "secret-api-key-123" -> "secr************"
    """
    if len(data) <= visible_chars:
        return "*" * len(data)

    return data[:visible_chars] + "*" * (len(data) - visible_chars)
