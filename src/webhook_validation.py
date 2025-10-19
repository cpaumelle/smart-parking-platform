"""
Webhook Signature Validation
Validates HMAC signatures for ChirpStack webhook requests
"""
import logging
import hmac
import hashlib
from typing import Optional
from uuid import UUID

from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


async def verify_webhook_signature(
    request: Request,
    tenant_id: Optional[UUID],
    db,
    body: bytes
) -> bool:
    """
    Verify webhook HMAC signature for a tenant

    Args:
        request: FastAPI request object
        tenant_id: Tenant UUID (None if device not yet assigned)
        db: Database connection pool
        body: Raw request body bytes

    Returns:
        True if signature is valid or no secret is configured

    Raises:
        HTTPException: 401 if signature is invalid

    Note:
        If no webhook secret is configured for the tenant, this logs a warning
        and allows the request (backward compatibility). In production, you may
        want to require secrets for all tenants.
    """
    signature_header = request.headers.get("X-Webhook-Signature")

    # If no signature provided
    if not signature_header:
        if tenant_id:
            logger.warning(f"No webhook signature provided for tenant {tenant_id}")
        else:
            logger.debug("No webhook signature provided (device not yet assigned)")
        # Allow for backward compatibility - you may want to change this
        return True

    # If no tenant (orphan device), we can't validate
    if not tenant_id:
        logger.warning("Webhook signature provided but device has no tenant - skipping validation")
        return True

    try:
        # Get tenant's webhook secret
        secret_row = await db.fetchrow("""
            SELECT secret_hash FROM webhook_secrets
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY created_at DESC
            LIMIT 1
        """, tenant_id)

        if not secret_row:
            # No secret configured for this tenant
            logger.warning(
                f"Webhook signature provided for tenant {tenant_id} "
                "but no secret is configured - allowing request"
            )
            return True

        # Compute expected signature
        secret = secret_row['secret_hash'].encode('utf-8')
        expected_signature = hmac.new(
            secret,
            body,
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(signature_header, expected_signature):
            logger.error(
                f"Invalid webhook signature for tenant {tenant_id}. "
                f"Expected: {expected_signature[:8]}..., Got: {signature_header[:8]}..."
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )

        logger.debug(f"Webhook signature verified for tenant {tenant_id}")
        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        # Fail closed - reject if verification fails unexpectedly
        raise HTTPException(
            status_code=500,
            detail="Failed to verify webhook signature"
        )


async def get_or_create_webhook_secret(
    tenant_id: UUID,
    db
) -> str:
    """
    Get or create a webhook secret for a tenant

    Args:
        tenant_id: Tenant UUID
        db: Database connection pool

    Returns:
        Secret string (for initial setup only - never expose after creation)
    """
    import secrets

    # Check if secret already exists
    existing = await db.fetchrow("""
        SELECT id FROM webhook_secrets
        WHERE tenant_id = $1 AND is_active = true
        LIMIT 1
    """, tenant_id)

    if existing:
        raise ValueError(
            "Webhook secret already exists for this tenant. "
            "Secrets cannot be retrieved after creation for security reasons."
        )

    # Generate new secret (32 bytes = 256 bits)
    new_secret = secrets.token_hex(32)

    # Store in database
    await db.execute("""
        INSERT INTO webhook_secrets (tenant_id, secret_hash, algorithm)
        VALUES ($1, $2, $3)
    """, tenant_id, new_secret, 'sha256')

    logger.info(f"Created new webhook secret for tenant {tenant_id}")

    return new_secret


async def rotate_webhook_secret(
    tenant_id: UUID,
    db
) -> str:
    """
    Rotate (replace) webhook secret for a tenant

    Args:
        tenant_id: Tenant UUID
        db: Database connection pool

    Returns:
        New secret string (save this securely - only shown once!)
    """
    import secrets

    # Deactivate old secrets
    await db.execute("""
        UPDATE webhook_secrets
        SET is_active = false
        WHERE tenant_id = $1
    """, tenant_id)

    # Generate new secret
    new_secret = secrets.token_hex(32)

    # Store in database
    await db.execute("""
        INSERT INTO webhook_secrets (tenant_id, secret_hash, algorithm)
        VALUES ($1, $2, $3)
    """, tenant_id, new_secret, 'sha256')

    logger.info(f"Rotated webhook secret for tenant {tenant_id}")

    return new_secret
