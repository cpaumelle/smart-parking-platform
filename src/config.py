"""
Centralized configuration management using Pydantic Settings
Single source of truth for all application configuration

Supports Docker secrets and environment variables with automatic fallback.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
import os
from functools import lru_cache
from .secrets import load_secret


class Settings(BaseSettings):
    """Application settings with environment variable support and validation"""

    # ========================================================================
    # Application
    # ========================================================================
    app_name: str = Field(
        default="Smart Parking Platform v5",
        description="Application name"
    )
    app_version: str = Field(
        default="5.8.0",
        description="Application version"
    )
    environment: str = Field(
        default="production",
        description="Environment: development, staging, production"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )

    # ========================================================================
    # API Server
    # ========================================================================
    api_host: str = Field(
        default="0.0.0.0",
        description="API server bind host"
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port"
    )
    api_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of Uvicorn workers"
    )
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds"
    )
    max_request_size: int = Field(
        default=10_485_760,
        description="Max request size in bytes (10MB)"
    )

    # ========================================================================
    # Database (PostgreSQL)
    # ========================================================================
    database_url: str = Field(
        default="postgresql://parking:parking@postgres:5432/parking",
        description="PostgreSQL connection URL"
    )
    database_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Database pool max overflow connections"
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Database pool connection timeout in seconds"
    )
    database_pool_recycle: int = Field(
        default=3600,
        ge=300,
        le=7200,
        description="Database connection recycle time in seconds"
    )
    db_pool_min_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Minimum database pool size"
    )
    db_pool_max_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Maximum database pool size"
    )

    # ========================================================================
    # Redis
    # ========================================================================
    redis_url: str = Field(
        default="redis://parking-redis:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Redis connection pool size"
    )
    redis_ttl_seconds: int = Field(
        default=86400,
        ge=60,
        le=604800,
        description="Default Redis TTL in seconds (24 hours)"
    )

    # ========================================================================
    # ChirpStack (LoRaWAN Network Server)
    # ========================================================================
    chirpstack_host: str = Field(
        default="parking-chirpstack",
        description="ChirpStack server hostname"
    )
    chirpstack_port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="ChirpStack gRPC port"
    )
    # ChirpStack API credentials: Support Docker secrets
    chirpstack_api_key: str = Field(
        default_factory=lambda: load_secret("chirpstack_api_key", default=""),
        description="ChirpStack API key"
    )
    chirpstack_api_url: str = Field(
        default="http://parking-chirpstack:8080",
        description="ChirpStack API base URL"
    )
    chirpstack_api_token: str = Field(
        default_factory=lambda: load_secret("chirpstack_api_token", default=""),
        description="ChirpStack API token (alias for api_key)"
    )

    # ========================================================================
    # Background Tasks & Scheduling
    # ========================================================================
    scheduler_enabled: bool = Field(
        default=True,
        description="Enable background task scheduler"
    )
    reconciliation_interval_minutes: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Display reconciliation interval in minutes"
    )
    materialized_view_refresh_hours: int = Field(
        default=1,
        ge=1,
        le=24,
        description="Materialized view refresh interval in hours"
    )

    # ========================================================================
    # Multi-Tenancy & Authentication
    # ========================================================================
    require_api_key: bool = Field(
        default=True,
        description="Require API key for all requests"
    )
    default_tenant_id: Optional[str] = Field(
        default=None,
        description="Default tenant ID (for development)"
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="HTTP header name for API key"
    )

    # ========================================================================
    # Security (JWT)
    # ========================================================================
    # Secret key: Supports Docker secrets, environment variables, or default
    # Priority: 1) /run/secrets/secret_key, 2) SECRET_KEY_FILE, 3) SECRET_KEY env
    secret_key: str = Field(
        default_factory=lambda: load_secret(
            "secret_key",
            default="change-this-in-production-minimum-32-characters-long"
        ),
        min_length=32,
        description="Application secret key (for JWT signing)"
    )

    # JWT secret: Optional override for JWT-specific key
    jwt_secret_key: Optional[str] = Field(
        default_factory=lambda: load_secret("jwt_secret_key"),
        description="JWT secret key (if different from secret_key)"
    )

    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    access_token_expire_minutes: int = Field(
        default=15,
        ge=5,
        le=1440,
        description="Access token expiration in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Refresh token expiration in days"
    )

    # ========================================================================
    # Rate Limiting
    # ========================================================================
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    rate_limit_per_minute: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Rate limit per minute per tenant"
    )
    rate_limit_per_hour: int = Field(
        default=1000,
        ge=100,
        le=100000,
        description="Rate limit per hour per tenant"
    )

    # ========================================================================
    # Monitoring & Observability
    # ========================================================================
    prometheus_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    sentry_environment: Optional[str] = Field(
        default=None,
        description="Sentry environment name"
    )
    sentry_traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Sentry traces sample rate (0.0-1.0)"
    )

    # ========================================================================
    # CORS (Cross-Origin Resource Sharing)
    # ========================================================================
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        alias="cors_origins",
        description="Comma-separated list of allowed CORS origins"
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    # ========================================================================
    # Feature Flags
    # ========================================================================
    enable_webhooks: bool = Field(
        default=True,
        description="Enable webhook functionality"
    )
    enable_downlink: bool = Field(
        default=True,
        description="Enable downlink queue for displays"
    )
    enable_reservations: bool = Field(
        default=True,
        description="Enable reservation system"
    )

    # ========================================================================
    # Validators
    # ========================================================================

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment"""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v.lower()

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Validate JWT algorithm"""
        valid_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in valid_algorithms:
            raise ValueError(f"Invalid JWT algorithm: {v}. Must be one of {valid_algorithms}")
        return v

    def get_effective_jwt_secret(self) -> str:
        """Get effective JWT secret key (prefers jwt_secret_key over secret_key)"""
        if self.jwt_secret_key and len(self.jwt_secret_key) >= 32:
            return self.jwt_secret_key
        return self.secret_key

    def get_effective_chirpstack_token(self) -> str:
        """Get effective ChirpStack token (prefers chirpstack_api_token over chirpstack_api_key)"""
        return self.chirpstack_api_token if self.chirpstack_api_token else self.chirpstack_api_key

    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields for forward compatibility


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Uses lru_cache to ensure singleton pattern
    """
    return Settings()


# Global settings instance for convenience
settings = get_settings()


# Export commonly used values for backward compatibility
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url
DEBUG = settings.debug
LOG_LEVEL = settings.log_level
