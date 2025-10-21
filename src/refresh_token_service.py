"""
Refresh Token Service - Manages JWT refresh tokens with rotation and reuse detection

Security features:
- Cryptographically secure token generation (32-byte URL-safe)
- Token rotation on every refresh (old token invalidated)
- Reuse detection (revokes entire token family if reused token detected)
- Device fingerprinting (detects stolen tokens used from different devices)
- Automatic cleanup of expired tokens
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class RefreshTokenService:
    """Manages refresh tokens with rotation and reuse detection"""

    EXPIRY_DAYS = 30
    REUSE_DETECTION_WINDOW_MINUTES = 5  # Grace period for race conditions

    @staticmethod
    def generate_token() -> str:
        """Generate cryptographically secure refresh token (32 bytes = 43 chars base64)"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash token for secure storage (SHA-256)"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_refresh_token(
        self,
        db,
        user_id: UUID,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Create a new refresh token for a user

        Args:
            db: Database connection pool
            user_id: User UUID
            device_fingerprint: Optional device identifier (combination of browser/OS/screen)
            ip_address: Client IP address
            user_agent: Client User-Agent header

        Returns:
            Plaintext refresh token (only returned once, never stored in plaintext)
        """
        token = self.generate_token()
        token_hash = self.hash_token(token)
        expires_at = datetime.utcnow() + timedelta(days=self.EXPIRY_DAYS)

        query = """
            INSERT INTO refresh_tokens (
                user_id,
                token_hash,
                device_fingerprint,
                ip_address,
                user_agent,
                expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        try:
            result = await db.fetchrow(
                query,
                user_id,
                token_hash,
                device_fingerprint,
                ip_address,
                user_agent,
                expires_at
            )

            logger.info(
                f"Created refresh token for user_id={user_id}, "
                f"token_id={result['id']}, expires_at={expires_at}"
            )

            return token  # Return plaintext token (only time it's available)

        except Exception as e:
            logger.error(f"Failed to create refresh token for user_id={user_id}: {e}")
            raise

    async def validate_and_rotate(
        self,
        db,
        token: str,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[Optional[UUID], Optional[str]]:
        """
        Validate refresh token and rotate it (issue new token, revoke old)

        Implements reuse detection:
        - If token is revoked but recently used, attacker may have stolen it
        - Revoke all tokens in the family (all tokens for that user from that device)
        - Prevents token replay attacks

        Args:
            db: Database connection pool
            token: Plaintext refresh token
            device_fingerprint: Optional device identifier for reuse detection
            ip_address: Client IP address
            user_agent: Client User-Agent header

        Returns:
            Tuple of (user_id, new_refresh_token) or (None, None) if invalid
        """
        token_hash = self.hash_token(token)

        # Fetch token details
        query = """
            SELECT
                id,
                user_id,
                device_fingerprint,
                expires_at,
                revoked_at,
                last_used_at
            FROM refresh_tokens
            WHERE token_hash = $1
        """

        token_record = await db.fetchrow(query, token_hash)

        if not token_record:
            logger.warning(f"Refresh token not found (hash={token_hash[:16]}...)")
            return None, None

        token_id = token_record['id']
        user_id = token_record['user_id']
        stored_fingerprint = token_record['device_fingerprint']
        expires_at = token_record['expires_at']
        revoked_at = token_record['revoked_at']
        last_used_at = token_record['last_used_at']

        # Check if token is expired
        if datetime.utcnow() > expires_at:
            logger.warning(f"Refresh token expired for user_id={user_id}, token_id={token_id}")
            return None, None

        # REUSE DETECTION: Token is revoked but being used again (possible attack)
        if revoked_at:
            time_since_revoke = (datetime.utcnow() - revoked_at).total_seconds() / 60

            # If token was revoked recently (within grace period), might be race condition
            if time_since_revoke < self.REUSE_DETECTION_WINDOW_MINUTES:
                logger.warning(
                    f"Refresh token reuse detected (within grace period) for user_id={user_id}, "
                    f"token_id={token_id}, revoked {time_since_revoke:.1f}m ago"
                )
                return None, None
            else:
                # Token reuse detected outside grace period - SECURITY BREACH
                logger.error(
                    f"SECURITY ALERT: Refresh token reuse detected for user_id={user_id}, "
                    f"token_id={token_id}, revoked {time_since_revoke:.1f}m ago. "
                    f"Revoking all tokens for this user/device."
                )

                # Revoke all tokens for this user + device fingerprint
                await self.revoke_token_family(
                    db,
                    user_id=user_id,
                    device_fingerprint=stored_fingerprint
                )

                return None, None

        # Check device fingerprint mismatch (possible token theft)
        if stored_fingerprint and device_fingerprint and stored_fingerprint != device_fingerprint:
            logger.warning(
                f"Device fingerprint mismatch for user_id={user_id}, token_id={token_id}. "
                f"Expected: {stored_fingerprint[:16]}..., Got: {device_fingerprint[:16]}..."
            )
            # Don't auto-revoke on fingerprint mismatch (user might have new device)
            # But log it for security monitoring

        # Token is valid - rotate it
        # 1. Revoke old token
        await self.revoke_token(db, token_id)

        # 2. Create new token
        new_token = await self.create_refresh_token(
            db,
            user_id=user_id,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info(
            f"Rotated refresh token for user_id={user_id}, "
            f"old_token_id={token_id}, new_token_id=(new)"
        )

        return user_id, new_token

    async def revoke_token(self, db, token_id: int) -> None:
        """Revoke a single refresh token"""
        query = """
            UPDATE refresh_tokens
            SET revoked_at = NOW()
            WHERE id = $1
        """
        await db.execute(query, token_id)
        logger.info(f"Revoked refresh token_id={token_id}")

    async def revoke_token_family(
        self,
        db,
        user_id: UUID,
        device_fingerprint: Optional[str] = None
    ) -> int:
        """
        Revoke all refresh tokens for a user (optionally filtered by device)

        Used when:
        - Token reuse detected (revoke all tokens from that device)
        - User logs out from all devices
        - User changes password (security measure)

        Returns:
            Number of tokens revoked
        """
        if device_fingerprint:
            query = """
                UPDATE refresh_tokens
                SET revoked_at = NOW()
                WHERE user_id = $1
                  AND device_fingerprint = $2
                  AND revoked_at IS NULL
            """
            result = await db.execute(query, user_id, device_fingerprint)
        else:
            query = """
                UPDATE refresh_tokens
                SET revoked_at = NOW()
                WHERE user_id = $1
                  AND revoked_at IS NULL
            """
            result = await db.execute(query, user_id)

        # Extract count from result (format: "UPDATE N")
        count = int(result.split()[-1]) if result else 0

        logger.warning(
            f"Revoked {count} refresh tokens for user_id={user_id}, "
            f"device_fingerprint={device_fingerprint[:16] + '...' if device_fingerprint else 'all'}"
        )

        return count

    async def cleanup_expired_tokens(self, db) -> int:
        """
        Delete expired refresh tokens (housekeeping task)

        Should be run periodically (e.g., daily cron job or background task)

        Returns:
            Number of tokens deleted
        """
        query = """
            DELETE FROM refresh_tokens
            WHERE expires_at < NOW()
        """

        result = await db.execute(query)
        count = int(result.split()[-1]) if result else 0

        logger.info(f"Cleaned up {count} expired refresh tokens")

        return count

    async def get_user_tokens(
        self,
        db,
        user_id: UUID,
        include_revoked: bool = False
    ) -> list[Dict[str, Any]]:
        """
        Get all refresh tokens for a user (for admin/user management UI)

        Args:
            db: Database connection pool
            user_id: User UUID
            include_revoked: Include revoked tokens in results

        Returns:
            List of token records (without token_hash for security)
        """
        if include_revoked:
            query = """
                SELECT
                    id,
                    device_fingerprint,
                    ip_address,
                    user_agent,
                    created_at,
                    expires_at,
                    revoked_at,
                    last_used_at
                FROM refresh_tokens
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
        else:
            query = """
                SELECT
                    id,
                    device_fingerprint,
                    ip_address,
                    user_agent,
                    created_at,
                    expires_at,
                    last_used_at
                FROM refresh_tokens
                WHERE user_id = $1
                  AND revoked_at IS NULL
                  AND expires_at > NOW()
                ORDER BY created_at DESC
            """

        results = await db.fetch(query, user_id)

        return [dict(row) for row in results]


# Global singleton instance
_refresh_token_service: Optional[RefreshTokenService] = None


def get_refresh_token_service() -> RefreshTokenService:
    """Get global RefreshTokenService instance"""
    global _refresh_token_service
    if _refresh_token_service is None:
        _refresh_token_service = RefreshTokenService()
    return _refresh_token_service
