"""Sensor reading model"""

from sqlalchemy import Column, String, Boolean, Integer, Float, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from ..core.database import Base


class SensorReading(Base):
    """Sensor reading from parking sensors"""
    __tablename__ = "sensor_readings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Device and space
    device_id = Column(UUID(as_uuid=True), ForeignKey("sensor_devices.id"), nullable=False, index=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True, index=True)
    
    # Reading data
    occupancy = Column(Boolean, nullable=False)
    confidence = Column(Float, nullable=True)  # 0.0-1.0
    
    # Raw sensor data
    raw_data = Column(JSON, default={})
    
    # LoRaWAN metadata
    rssi = Column(Integer, nullable=True)
    snr = Column(Float, nullable=True)
    gateway_id = Column(String(16), nullable=True)
    
    # Timestamp
    timestamp = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<SensorReading device={self.device_id} occupancy={self.occupancy}>"
