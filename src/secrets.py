"""
Docker Secrets Loader

Provides secure secret management with fallback chain:
1. Docker secrets (/run/secrets/<secret_name>)
2. Environment variable with _FILE suffix pointing to file
3. Direct environment variable
4. Default value (if provided)

This approach allows:
- Production: Use Docker secrets (most secure)
- Development: Use environment variables or .env file
- Testing: Use defaults or mock values

Example:
    # In config.py
    jwt_secret_key: str = Field(
        default_factory=lambda: load_secret(
            "jwt_secret_key",
            default="dev-secret-key-change-in-production"
        )
    )

Security Notes:
- Docker secrets are stored in tmpfs (RAM) at /run/secrets/
- Never commit secrets to version control
- Use .gitignore to exclude ./secrets/ directory
- In production, use docker-compose secrets or Kubernetes secrets
"""
import os
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()


def load_secret(
    secret_name: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Load secret from Docker secrets, file, or environment variable

    Fallback chain:
    1. /run/secrets/{secret_name} (Docker swarm secrets)
    2. Path from {SECRET_NAME}_FILE env var (file-based secrets)
    3. {SECRET_NAME} env var (direct value)
    4. default parameter (development/testing)

    Args:
        secret_name: Name of the secret (e.g., "jwt_secret_key")
        default: Default value if secret not found
        required: If True, raises ValueError when secret not found and no default

    Returns:
        Secret value as string, or None if not found and not required

    Raises:
        ValueError: If required=True and secret not found with no default
        FileNotFoundError: If _FILE env var points to non-existent file

    Example:
        >>> load_secret("jwt_secret_key", required=True)
        'my-super-secret-jwt-key'

        >>> load_secret("optional_api_key", default="dev-key")
        'dev-key'
    """
    # Normalize secret name (lowercase with underscores)
    secret_name_normalized = secret_name.lower().replace("-", "_")
    env_var_name = secret_name_normalized.upper()

    # 1. Try Docker secrets first (/run/secrets/)
    docker_secret_path = Path(f"/run/secrets/{secret_name_normalized}")
    if docker_secret_path.exists():
        try:
            secret_value = docker_secret_path.read_text().strip()
            logger.debug(
                "secret_loaded",
                secret_name=secret_name_normalized,
                source="docker_secret"
            )
            return secret_value
        except Exception as e:
            logger.error(
                "secret_read_error",
                secret_name=secret_name_normalized,
                path=str(docker_secret_path),
                error=str(e)
            )

    # 2. Try environment variable with _FILE suffix (file path)
    env_file_var = f"{env_var_name}_FILE"
    env_file_path_str = os.getenv(env_file_var)
    if env_file_path_str:
        env_file_path = Path(env_file_path_str)
        if env_file_path.exists():
            try:
                secret_value = env_file_path.read_text().strip()
                logger.debug(
                    "secret_loaded",
                    secret_name=secret_name_normalized,
                    source="env_file",
                    path=str(env_file_path)
                )
                return secret_value
            except Exception as e:
                logger.error(
                    "secret_read_error",
                    secret_name=secret_name_normalized,
                    path=str(env_file_path),
                    error=str(e)
                )
        else:
            raise FileNotFoundError(
                f"Secret file specified by {env_file_var}={env_file_path_str} does not exist"
            )

    # 3. Try direct environment variable
    env_value = os.getenv(env_var_name)
    if env_value:
        logger.debug(
            "secret_loaded",
            secret_name=secret_name_normalized,
            source="env_var"
        )
        return env_value

    # 4. Use default if provided
    if default is not None:
        logger.debug(
            "secret_loaded",
            secret_name=secret_name_normalized,
            source="default",
            is_production_safe=False
        )
        return default

    # 5. Secret not found
    if required:
        raise ValueError(
            f"Required secret '{secret_name_normalized}' not found. "
            f"Checked: /run/secrets/{secret_name_normalized}, "
            f"{env_file_var}, {env_var_name}"
        )

    logger.warning(
        "secret_not_found",
        secret_name=secret_name_normalized,
        required=False
    )
    return None


def load_secrets(secret_names: list[str], required: bool = False) -> dict[str, Optional[str]]:
    """
    Load multiple secrets at once

    Args:
        secret_names: List of secret names to load
        required: If True, raises ValueError if any secret not found

    Returns:
        Dictionary mapping secret names to their values

    Example:
        >>> load_secrets(["jwt_secret_key", "database_password"], required=True)
        {'jwt_secret_key': '...', 'database_password': '...'}
    """
    secrets = {}
    for secret_name in secret_names:
        secrets[secret_name] = load_secret(secret_name, required=required)
    return secrets


def validate_secret_strength(
    secret_value: str,
    min_length: int = 32,
    secret_name: str = "secret"
) -> bool:
    """
    Validate secret meets minimum security requirements

    Args:
        secret_value: Secret to validate
        min_length: Minimum required length
        secret_name: Name for error messages

    Returns:
        True if valid

    Raises:
        ValueError: If secret doesn't meet requirements

    Example:
        >>> validate_secret_strength("my-jwt-secret", min_length=32)
        ValueError: Secret 'secret' is too short (13 chars, minimum 32)
    """
    if not secret_value:
        raise ValueError(f"Secret '{secret_name}' is empty")

    if len(secret_value) < min_length:
        raise ValueError(
            f"Secret '{secret_name}' is too short "
            f"({len(secret_value)} chars, minimum {min_length})"
        )

    # Check if it's a common weak value
    weak_secrets = [
        "change-me",
        "changeme",
        "password",
        "secret",
        "admin",
        "test",
        "dev",
        "development"
    ]

    secret_lower = secret_value.lower()
    for weak in weak_secrets:
        if weak in secret_lower and len(secret_value) < 40:
            logger.warning(
                "weak_secret_detected",
                secret_name=secret_name,
                reason=f"contains '{weak}'"
            )

    return True


def get_secret_or_fail(secret_name: str, min_length: int = 0) -> str:
    """
    Load secret and fail loudly if not found or invalid

    Convenience function for required secrets with validation.

    Args:
        secret_name: Name of the secret
        min_length: Minimum length requirement (0 = no check)

    Returns:
        Secret value

    Raises:
        ValueError: If secret not found or too short

    Example:
        >>> jwt_key = get_secret_or_fail("jwt_secret_key", min_length=32)
    """
    secret_value = load_secret(secret_name, required=True)

    if min_length > 0:
        validate_secret_strength(secret_value, min_length, secret_name)

    return secret_value


# ============================================================================
# Convenience Functions for Common Secrets
# ============================================================================

def get_database_password() -> str:
    """Get database password (required)"""
    return get_secret_or_fail("database_password", min_length=16)


def get_jwt_secret() -> str:
    """Get JWT secret key (required, min 32 chars)"""
    return get_secret_or_fail("jwt_secret_key", min_length=32)


def get_chirpstack_api_token() -> str:
    """Get ChirpStack API token (required)"""
    return get_secret_or_fail("chirpstack_api_token", min_length=16)
