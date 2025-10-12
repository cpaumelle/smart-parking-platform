"""
Parking Sensor Simulator
Simulates ultrasonic LoRaWAN parking detection sensors with realistic behavior
"""

import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import struct


class ParkingState(Enum):
    """Parking space states"""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class ParkingSensor:
    """
    Simulates an ultrasonic LoRaWAN parking sensor
    Reports distance measurements that indicate parking occupancy
    """
    
    def __init__(self, sensor_id: int, dev_eui: str, config: dict):
        self.sensor_id = sensor_id
        self.dev_eui = dev_eui
        self.config = config
        
        # Physical sensor parameters
        self.ceiling_height = 2.5  # meters (typical parking garage)
        self.car_height_avg = 1.5  # meters (typical car)
        self.car_height_std = 0.2  # variation in car heights
        self.empty_distance = self.ceiling_height  # distance when empty
        
        # Current state
        self.state = ParkingState.AVAILABLE
        self.distance = self.empty_distance  # current measured distance in meters
        self.last_update = datetime.now()
        self.battery_level = 100  # percentage
        self.message_count = 0
        
        # Parking session tracking
        self.car_arrived_at: Optional[datetime] = None
        self.expected_departure: Optional[datetime] = None
        
        # Sensor reliability
        self.is_operational = True
        self.failure_rate = config.get('behavior', {}).get('failure_rate', 0.0)
        
        # LoRaWAN parameters
        self.fport = config['simulation']['lorawan']['sensor_fport']
        self.sf = config['simulation']['lorawan']['data_rate']
        self.frequency = config['simulation']['lorawan']['frequency']
        
        # Initialize with random state if configured
        initial_occupancy = config['behavior']['initial_occupancy']
        if random.random() < initial_occupancy:
            self._park_car()
    
    def update(self) -> bool:
        """
        Update sensor state based on simulation logic
        Returns True if state changed (requiring uplink message)
        """
        state_changed = False
        
        # Check if sensor failed
        if random.random() < self.failure_rate:
            if self.is_operational:
                self.is_operational = False
                self.state = ParkingState.UNKNOWN
                state_changed = True
                return state_changed
        else:
            if not self.is_operational:
                self.is_operational = True
                state_changed = True
        
        # Skip updates if not operational
        if not self.is_operational:
            return False
        
        current_time = datetime.now()
        
        # Handle reserved spaces (simplified - they don't get occupied in simulation)
        if self.sensor_id in self.config['behavior'].get('reserved_spaces', []):
            if self.state != ParkingState.RESERVED:
                self.state = ParkingState.RESERVED
                state_changed = True
            return state_changed
        
        # Check if current car is departing
        if self.state == ParkingState.OCCUPIED:
            if self.expected_departure and current_time >= self.expected_departure:
                self._car_departs()
                state_changed = True
        
        # Check for new car arrival (only if space is available)
        elif self.state == ParkingState.AVAILABLE:
            arrival_rate = self.config['behavior']['arrival_rate']
            
            # Apply scenario multipliers
            arrival_rate *= self._get_arrival_multiplier(current_time)
            
            # Check if car arrives (probability per update cycle)
            if random.random() < arrival_rate:
                self._park_car()
                state_changed = True
        
        # Simulate small distance variations (sensor noise)
        if self.is_operational:
            noise = random.gauss(0, 0.01)  # 1cm standard deviation
            self.distance = max(0.03, self.distance + noise)  # Min 3cm (sensor limit)
        
        # Battery drain (very slow for LoRaWAN devices)
        self.battery_level -= 0.0001  # Roughly 10 years battery life
        
        self.last_update = current_time
        return state_changed
    
    def _park_car(self):
        """Simulate a car parking in this space"""
        # Generate realistic car height
        car_height = random.gauss(self.car_height_avg, self.car_height_std)
        car_height = max(1.0, min(2.0, car_height))  # Clamp between 1m and 2m
        
        # Calculate distance to car roof
        self.distance = self.ceiling_height - car_height
        self.state = ParkingState.OCCUPIED
        self.car_arrived_at = datetime.now()
        
        # Calculate expected departure time
        avg_duration = self.config['behavior']['avg_parking_duration']
        std_duration = self.config['behavior']['parking_duration_std']
        parking_duration = random.gauss(avg_duration, std_duration)
        parking_duration = max(5, parking_duration)  # At least 5 minutes
        
        self.expected_departure = self.car_arrived_at + timedelta(minutes=parking_duration)
    
    def _car_departs(self):
        """Simulate a car departing from this space"""
        self.distance = self.empty_distance
        self.state = ParkingState.AVAILABLE
        self.car_arrived_at = None
        self.expected_departure = None
    
    def _get_arrival_multiplier(self, current_time: datetime) -> float:
        """Get arrival rate multiplier based on time-of-day scenarios"""
        multiplier = 1.0
        hour = current_time.hour
        
        scenarios = self.config.get('scenarios', {})
        
        # Rush hour
        if scenarios.get('rush_hour', {}).get('enabled', False):
            rush = scenarios['rush_hour']
            if rush['start_hour'] <= hour < rush['end_hour']:
                multiplier *= rush['arrival_multiplier']
        
        # Lunch time
        if scenarios.get('lunch_time', {}).get('enabled', False):
            lunch = scenarios['lunch_time']
            if lunch['start_hour'] <= hour < lunch['end_hour']:
                multiplier *= lunch['arrival_multiplier']
        
        return multiplier
    
    def get_uplink_payload(self) -> bytes:
        """
        Generate LoRaWAN uplink payload
        Format: [Distance (cm) - 2 bytes] [Battery %] [State] [Message Counter]
        """
        distance_cm = int(self.distance * 100)
        
        # Pack payload: distance (uint16), battery (uint8), state (uint8), counter (uint8)
        payload = struct.pack(
            '>HBBB',
            distance_cm,
            int(self.battery_level),
            self._state_to_byte(),
            self.message_count & 0xFF
        )
        
        self.message_count += 1
        return payload
    
    def _state_to_byte(self) -> int:
        """Convert state to byte representation"""
        state_map = {
            ParkingState.AVAILABLE: 0,
            ParkingState.OCCUPIED: 1,
            ParkingState.RESERVED: 2,
            ParkingState.MAINTENANCE: 3,
            ParkingState.UNKNOWN: 255
        }
        return state_map.get(self.state, 255)
    
    def get_status_dict(self) -> dict:
        """Get sensor status as dictionary for monitoring"""
        return {
            'sensor_id': self.sensor_id,
            'dev_eui': self.dev_eui,
            'state': self.state.value,
            'distance_m': round(self.distance, 3),
            'battery_pct': round(self.battery_level, 2),
            'operational': self.is_operational,
            'message_count': self.message_count,
            'last_update': self.last_update.isoformat(),
            'parking_duration_min': self._get_parking_duration_minutes()
        }
    
    def _get_parking_duration_minutes(self) -> Optional[float]:
        """Calculate how long current car has been parked (if occupied)"""
        if self.state == ParkingState.OCCUPIED and self.car_arrived_at:
            duration = (datetime.now() - self.car_arrived_at).total_seconds() / 60
            return round(duration, 1)
        return None
    
    def get_time_until_departure(self) -> Optional[int]:
        """Get minutes until expected departure (if occupied)"""
        if self.state == ParkingState.OCCUPIED and self.expected_departure:
            remaining = (self.expected_departure - datetime.now()).total_seconds() / 60
            return max(0, int(remaining))
        return None
    
    def __repr__(self):
        return (f"ParkingSensor(id={self.sensor_id}, dev_eui={self.dev_eui}, "
                f"state={self.state.value}, distance={self.distance:.2f}m)")
