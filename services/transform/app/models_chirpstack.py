# models_chirpstack.py
# ChirpStack database models
# Version: 1.0.0 - 2025-10-13

from sqlalchemy import Column, String, TIMESTAMP, Text, Boolean, SMALLINT, Integer, ForeignKey, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB, NUMERIC
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class ChirpStackDevice(Base):
    """ChirpStack LoRaWAN Device"""
    __tablename__ = "device"
    
    dev_eui = Column(LargeBinary, primary_key=True)
    application_id = Column(UUID, ForeignKey("application.id"), nullable=False)
    device_profile_id = Column(UUID, ForeignKey("device_profile.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    join_eui = Column(LargeBinary, nullable=False)
    enabled_class = Column(String(1), nullable=False, default="A")
    skip_fcnt_check = Column(Boolean, nullable=False, default=False)
    is_disabled = Column(Boolean, nullable=False, default=False)
    external_power_source = Column(Boolean, nullable=False, default=False)
    battery_level = Column(NUMERIC(5, 2), nullable=True)
    tags = Column(JSONB, nullable=False, default={})
    variables = Column(JSONB, nullable=False, default={})
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_seen_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Location fields
    latitude = Column(NUMERIC, nullable=True)
    longitude = Column(NUMERIC, nullable=True)
    altitude = Column(NUMERIC, nullable=True)
    
    # Network fields
    dev_addr = Column(LargeBinary, nullable=True)
    secondary_dev_addr = Column(LargeBinary, nullable=True)
    margin = Column(Integer, nullable=True)
    dr = Column(SMALLINT, nullable=True)
    
    # Session data
    device_session = Column(LargeBinary, nullable=True)
    app_layer_params = Column(JSONB, nullable=False, default={})


class ChirpStackDeviceKeys(Base):
    """ChirpStack Device OTAA Keys"""
    __tablename__ = "device_keys"
    
    dev_eui = Column(LargeBinary, ForeignKey("device.dev_eui"), primary_key=True)
    nwk_key = Column(LargeBinary, nullable=False)
    app_key = Column(LargeBinary, nullable=False)
    dev_nonces = Column(LargeBinary, nullable=True)
    join_nonce = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ChirpStackApplication(Base):
    """ChirpStack Application"""
    __tablename__ = "application"
    
    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenant.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    mqtt_tls_cert = Column(LargeBinary, nullable=True)
    tags = Column(JSONB, nullable=False, default={})
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ChirpStackDeviceProfile(Base):
    """ChirpStack Device Profile"""
    __tablename__ = "device_profile"
    
    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenant.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    region = Column(String(20), nullable=False)
    mac_version = Column(String(20), nullable=False)
    reg_params_revision = Column(String(20), nullable=False)
    supports_otaa = Column(Boolean, nullable=False, default=True)
    supports_class_b = Column(Boolean, nullable=False, default=False)
    supports_class_c = Column(Boolean, nullable=False, default=False)
    tags = Column(JSONB, nullable=False, default={})
    payload_codec_runtime = Column(String(20), nullable=False, default="NONE")
    payload_codec_script = Column(Text, nullable=False, default="")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
