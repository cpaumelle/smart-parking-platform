"""
API Key Generation and Management
==================================
Utilities for generating and managing tenant-scoped API keys.

API Key Format:
- Prefix: sp_live_ (production) or sp_test_ (testing)
- Random: 32 bytes URL-safe base64
- Total length: ~51 characters
- Example: sp_live_xK9zPmQ7vR3wL8nH4jF2sB6tY5uA1cD0eG

Security:
- Keys are generated with secrets.token_urlsafe (cryptographically secure)
- Keys are hashed with bcrypt before storage (never stored plaintext)
- Only the hash is stored in database
- Keys are only shown once during creation
"""

import secrets
import bcrypt
from typing import Tuple
import logging

logger = logging.getLogger("api_keys")


def generate_api_key(prefix: str = "sp_live_") -> str:
    """
    Generate a cryptographically secure API key.
    
    Args:
        prefix: Key prefix (sp_live_ for production, sp_test_ for testing)
    
    Returns:
        API key string (e.g., sp_live_xK9zPmQ7vR3wL8nH4jF2sB6tY5uA1cD0eG)
    """
    random_part = secrets.token_urlsafe(32)
    api_key = f"{prefix}{random_part}"
    return api_key


def hash_api_key(api_key: str) -> str:
    """
    Hash API key with bcrypt.
    
    Args:
        api_key: Plaintext API key
    
    Returns:
        bcrypt hash string
    """
    # Generate salt and hash
    salt = bcrypt.gensalt()
    key_hash = bcrypt.hashpw(api_key.encode('utf-8'), salt)
    return key_hash.decode('utf-8')


def generate_and_hash_api_key(prefix: str = "sp_live_") -> Tuple[str, str]:
    """
    Generate API key and its hash in one step.
    
    Args:
        prefix: Key prefix
    
    Returns:
        Tuple of (plaintext_key, bcrypt_hash)
    """
    api_key = generate_api_key(prefix)
    key_hash = hash_api_key(api_key)
    return api_key, key_hash


def extract_key_prefix(api_key: str, length: int = 8) -> str:
    """
    Extract the first N characters of API key for logging/identification.
    
    Args:
        api_key: Full API key
        length: Number of characters to extract (default 8)
    
    Returns:
        Key prefix (e.g., "sp_live_")
    """
    return api_key[:length]


# Example usage:
# api_key, key_hash = generate_and_hash_api_key("sp_live_")
# print(f"API Key: {api_key}")  # Show to user ONCE
# print(f"Hash: {key_hash}")     # Store in database
