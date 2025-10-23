"""Configuration management using Pydantic Settings"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
import os

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Application
    app_name: str = "Smart Parking Platform V6"
    app_version: str = "6.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Database
    database_url: str
    db_pool_size: int = 20
    db_pool_max_overflow: int = 40
    enable_rls: bool = True
    
    # Redis
    redis_url: str
    redis_pool_size: int = 10
    
    # ChirpStack
    chirpstack_host: str = "chirpstack"
    chirpstack_port: int = 8080
    chirpstack_api_key: str = ""
    chirpstack_sync_interval: int = 300
    
    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    refresh_token_expiry_days: int = 30
    
    # Platform Tenant
    platform_tenant_id: str = "00000000-0000-0000-0000-000000000000"
    platform_tenant_name: str = "Platform"
    platform_tenant_slug: str = "platform"
    
    # CORS
    cors_origins: List[str] = Field(default_factory=list)
    
    # Feature Flags
    use_v6_api: bool = True
    enable_audit_log: bool = True
    enable_metrics: bool = True
    enable_graphql: bool = False
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_tenant: int = 100
    
    # Webhook
    webhook_secret_key: str = ""
    webhook_signature_header: str = "X-Webhook-Signature"
    webhook_spool_dir: str = "/var/spool/parking-uplinks"
    
    # Downlink Queue
    downlink_queue_name: str = "parking:downlinks"
    downlink_max_retries: int = 5
    downlink_retry_backoff_base: int = 2
    downlink_rate_limit_gateway: int = 30
    downlink_rate_limit_tenant: int = 100
    
    # Monitoring
    prometheus_enabled: bool = True
    sentry_dsn: Optional[str] = None
    jaeger_enabled: bool = False
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Create global settings instance
settings = get_settings()
