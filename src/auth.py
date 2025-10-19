"""
API Key Authentication
Secure authentication using API keys stored in database with bcrypt hashing
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import secrets

from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
import bcrypt

logger = logging.getLogger(__name__)

# API Key header configuration
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Global database pool reference (set by main.py)
_db_pool = None

def set_db_pool(pool):
    """Set the database pool for authentication"""
    global _db_pool
    _db_pool = pool

class APIKeyInfo:
    """Information about an authenticated API key"""
    def __init__(self, key_id: str, key_name: str, is_admin: bool = False):
        self.id = key_id
        self.name = key_name
        self.is_admin = is_admin
        self.authenticated_at = datetime.utcnow()

async def verify_api_key(api_key: str) -> Optional[APIKeyInfo]:
    """
    Verify API key against database

    Args:
        api_key: The API key to verify

    Returns:
        APIKeyInfo if valid, None otherwise
    """
    if not _db_pool:
        logger.error("Database pool not initialized for authentication")
        return None

    try:
        # Get all active API keys from database
        rows = await _db_pool.fetch("""
            SELECT id, key_hash, key_name, is_admin, last_used_at
            FROM api_keys
            WHERE is_active = true
        """)

        # Check each key (bcrypt comparison)
        for row in rows:
            try:
                key_hash = row['key_hash'].encode('utf-8') if isinstance(row['key_hash'], str) else row['key_hash']
                api_key_bytes = api_key.encode('utf-8')

                # Verify with bcrypt
                if bcrypt.checkpw(api_key_bytes, key_hash):
                    # Update last_used_at
                    await _db_pool.execute("""
                        UPDATE api_keys
                        SET last_used_at = NOW()
                        WHERE id = $1
                    """, row['id'])

                    logger.info(f"API key authenticated: {row['key_name']}")

                    return APIKeyInfo(
                        key_id=str(row['id']),
                        key_name=row['key_name'],
                        is_admin=row.get('is_admin', False)
                    )
            except Exception as e:
                # Continue checking other keys if one fails
                logger.warning(f"Error checking key {row['key_name']}: {e}")
                continue

        # No matching key found
        return None

    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return None

async def get_api_key(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER)
) -> APIKeyInfo:
    """
    FastAPI dependency for API key authentication

    Raises:
        HTTPException: 401 if no key provided or invalid
    """
    if not api_key:
        logger.warning(f"Missing API key from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Verify key
    key_info = await verify_api_key(api_key)

    if not key_info:
        logger.warning(f"Invalid API key from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Attach to request state for logging
    request.state.api_key_name = key_info.name
    request.state.api_key_id = key_info.id

    return key_info

async def get_admin_api_key(
    key_info: APIKeyInfo = Security(get_api_key)
) -> APIKeyInfo:
    """
    FastAPI dependency for admin-only endpoints

    Raises:
        HTTPException: 403 if not admin
    """
    if not key_info.is_admin:
        logger.warning(f"Non-admin key {key_info.name} attempted admin action")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return key_info

def generate_api_key() -> str:
    """
    Generate a secure API key

    Returns:
        A URL-safe random string suitable for use as an API key
    """
    # Generate 32 bytes = 256 bits of randomness
    # URL-safe base64 encoding gives ~43 characters
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using bcrypt

    Args:
        api_key: The plain text API key

    Returns:
        Bcrypt hash suitable for database storage
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(api_key.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# Optional: Webhook-specific authentication for ChirpStack
async def verify_webhook_source(request: Request) -> bool:
    """
    Verify webhook is coming from ChirpStack

    Can be enhanced with:
    - IP whitelist
    - Shared secret
    - HMAC signature verification
    """
    # For now, accept all internal traffic
    # In production, add IP whitelist or shared secret
    client_ip = request.client.host

    # Allow internal Docker network
    if client_ip.startswith("172.") or client_ip == "127.0.0.1":
        return True

    logger.warning(f"Webhook from untrusted source: {client_ip}")
    return False

async def get_optional_api_key(
    api_key: Optional[str] = Security(API_KEY_HEADER)
) -> Optional[APIKeyInfo]:
    """
    Optional authentication - returns None if no key provided
    Used for endpoints that have different behavior for authenticated users
    """
    if not api_key:
        return None

    return await verify_api_key(api_key)
