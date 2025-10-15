"""
Configuration settings for Parking Display Service
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # ChirpStack
    CHIRPSTACK_GRPC_URL: str = "parking-chirpstack:8080"
    CHIRPSTACK_API_TOKEN: str = ""
    
    # APScheduler settings
    APSCHEDULER_JOBSTORE_URL: Optional[str] = None  # Defaults to DATABASE_URL
    APSCHEDULER_TIMEZONE: str = "UTC"
    APSCHEDULER_THREAD_POOL_MAX_WORKERS: int = 10
    APSCHEDULER_MISFIRE_GRACE_TIME: int = 300  # 5 minutes
    
    # Robustness settings
    ENABLE_IDEMPOTENCY: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60
    
    # Redis
    REDIS_URL: str = "redis://parking-redis:6379/0"
    
    # Intervals (for backward compatibility with existing background tasks)
    RECONCILIATION_INTERVAL_MINUTES: int = 10
    RESERVATION_EXPIRY_CHECK_MINUTES: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
