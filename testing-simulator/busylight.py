"""
Busylight Simulator
Simulates Kuando Busylight IoT LoRaWAN devices (Class C)
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import struct


class BusylightColor(Enum):
    """Busylight color states"""
    OFF = "off"
    GREEN = "green"
    RED = "red"
    ORANGE = "orange"
    BLUE = "blue"
    WHITE = "white"


class Busylight:
    """
    Simulates a Kuando Busylight IoT LoRaWAN device (Class C)
    Receives downlink commands to change color/pattern
    """
    
    def __init__(self, light_id: int, dev_eui: str, config: dict):
        self.light_id = light_id
        self.dev_eui = dev_eui
        self.config = config
        
        # Current state
        self.current_color = BusylightColor.OFF
        self.red = 0
        self.green = 0
        self.blue = 0
        self.on_time = 0
        self.off_time = 255
        self.is_blinking = False
        
        # Device status
        self.is_operational = True
        self.last_update = datetime.now()
        self.downlink_count = 0
        self.battery_level = 100  # If battery powered
        
        # LoRaWAN Class C - always listening
        self.device_class = "C"
        self.fport = config['simulation']['lorawan']['busylight_fport']
        
        # Associated parking space
        self.associated_space_id = light_id  # 1:1 mapping
        
    def process_downlink(self, payload: bytes) -> bool:
        """
        Process downlink payload from ChirpStack
        Payload format (5 bytes): [R][G][B][On-time][Off-time]
        Returns True if successfully processed
        """
        if not self.is_operational:
            return False
        
        if len(payload) != 5:
            print(f"[Busylight {self.light_id}] Invalid payload length: {len(payload)}")
            return False
        
        try:
            # Unpack payload
            self.red, self.green, self.blue, self.on_time, self.off_time = struct.unpack('5B', payload)
            
            # Determine if blinking
            self.is_blinking = (self.off_time > 0 and self.on_time > 0)
            
            # Determine color name
            self.current_color = self._determine_color()
            
            self.last_update = datetime.now()
            self.downlink_count += 1
            
            return True
            
        except Exception as e:
            print(f"[Busylight {self.light_id}] Error processing downlink: {e}")
            return False
    
    def process_downlink_hex(self, hex_payload: str) -> bool:
        """
        Process downlink from hex string (convenient for testing)
        Example: "0064000FF00" for solid green
        """
        try:
            # Remove any spaces or formatting
            hex_payload = hex_payload.replace(' ', '').replace('0x', '')
            payload_bytes = bytes.fromhex(hex_payload)
            return self.process_downlink(payload_bytes)
        except Exception as e:
            print(f"[Busylight {self.light_id}] Error parsing hex payload: {e}")
            return False
    
    def _determine_color(self) -> BusylightColor:
        """Determine color name from RGB values"""
        if self.red == 0 and self.green == 0 and self.blue == 0:
            return BusylightColor.OFF
        elif self.green > self.red and self.green > self.blue:
            return BusylightColor.GREEN
        elif self.red > self.green and self.red > self.blue:
            return BusylightColor.RED
        elif self.red > 150 and self.green > 100 and self.blue < 50:
            return BusylightColor.ORANGE
        elif self.blue > self.red and self.blue > self.green:
            return BusylightColor.BLUE
        elif self.red > 200 and self.green > 200 and self.blue > 200:
            return BusylightColor.WHITE
        else:
            return BusylightColor.WHITE  # Mixed color
    
    def set_color_from_parking_state(self, state: str) -> bool:
        """
        Convenience method to set color based on parking state
        Uses configuration color scheme
        """
        colors = self.config.get('colors', {})
        
        color_map = {
            'available': colors.get('available', {}).get('payload', '0064000FF00'),
            'occupied': colors.get('occupied', {}).get('payload', '6400000FF00'),
            'reserved': colors.get('reserved', {}).get('payload', 'FFA5000FF00'),
            'expiring_soon': colors.get('expiring_soon', {}).get('payload', 'FFA5007F7F'),
            'maintenance': colors.get('maintenance', {}).get('payload', '0000640FF00'),
            'unknown': colors.get('unknown', {}).get('payload', 'FFFFFF7F7F')
        }
        
        payload_hex = color_map.get(state.lower())
        if payload_hex:
            return self.process_downlink_hex(payload_hex)
        else:
            print(f"[Busylight {self.light_id}] Unknown parking state: {state}")
            return False
    
    def turn_off(self):
        """Turn off the light"""
        self.process_downlink_hex("FFFFFF00FF")
    
    def test_pattern(self):
        """Run a test pattern (cycle through colors)"""
        import time
        colors_to_test = [
            ("0064000FF00", "Green"),
            ("6400000FF00", "Red"),
            ("FFA5000FF00", "Orange"),
            ("0000640FF00", "Blue"),
            ("FFFFFF0FF00", "White")
        ]
        
        for payload, name in colors_to_test:
            print(f"[Busylight {self.light_id}] Testing {name}")
            self.process_downlink_hex(payload)
            time.sleep(1)
        
        self.turn_off()
    
    def get_status_dict(self) -> dict:
        """Get busylight status as dictionary for monitoring"""
        return {
            'light_id': self.light_id,
            'dev_eui': self.dev_eui,
            'color': self.current_color.value,
            'rgb': f"({self.red},{self.green},{self.blue})",
            'blinking': self.is_blinking,
            'operational': self.is_operational,
            'downlink_count': self.downlink_count,
            'last_update': self.last_update.isoformat(),
            'associated_space': self.associated_space_id
        }
    
    def get_visual_representation(self) -> str:
        """Get a visual representation of the light for terminal display"""
        color_symbols = {
            BusylightColor.OFF: '⚫',
            BusylightColor.GREEN: '🟢',
            BusylightColor.RED: '🔴',
            BusylightColor.ORANGE: '🟠',
            BusylightColor.BLUE: '🔵',
            BusylightColor.WHITE: '⚪'
        }
        
        symbol = color_symbols.get(self.current_color, '⚫')
        
        if self.is_blinking:
            return f"{symbol}💫"  # Add sparkle for blinking
        else:
            return symbol
    
    def __repr__(self):
        blinking_str = " (blinking)" if self.is_blinking else ""
        return (f"Busylight(id={self.light_id}, dev_eui={self.dev_eui}, "
                f"color={self.current_color.value}{blinking_str})")
