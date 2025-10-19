"""
Configuration management using Pydantic Settings
Single source of truth for all configuration
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
import os
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with validation"""

    # Database
    database_url: str = Field(
        default="postgresql://parking:parking@localhost:5432/parking",
        description="PostgreSQL connection URL"
    )
    db_pool_min_size: int = Field(default=5, ge=1, le=20)
    db_pool_max_size: int = Field(default=20, ge=5, le=100)

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(default=50, ge=10, le=200)

    # ChirpStack
    chirpstack_host: str = Field(default="localhost")
    chirpstack_port: int = Field(default=8080)
    chirpstack_api_key: str = Field(default="", description="ChirpStack API key")

    # Application
    app_name: str = Field(default="Smart Parking Platform v2")
    app_version: str = Field(default="2.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # CORS - stored as string, parsed to list
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        alias="cors_origins"
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    # Security
    secret_key: str = Field(
        default="change-this-in-production-minimum-32-characters",
        min_length=32
    )
    api_key_header: str = Field(default="X-API-Key")

    # Timeouts and Limits
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    max_request_size: int = Field(default=10_485_760, description="Max request size in bytes (10MB)")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Allow extra fields for forward compatibility
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Use lru_cache to ensure single instance
    """
    return Settings()

# Global settings instance
settings = get_settings()

# Export commonly used values
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url
DEBUG = settings.debug
LOG_LEVEL = settings.log_level
