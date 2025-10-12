#!/usr/bin/env python3
"""
Kuando Busylight Color Testing Script
Device EUI: 2020203705250102

This script helps test and document different color combinations for the Kuando IoT Busylight.

Payload Format (5 bytes):
- Byte 0: Red intensity (0-255)
- Byte 1: Blue intensity (0-255)
- Byte 2: Green intensity (0-255)
- Byte 3: On duration (255 = solid, 0-254 = custom)
- Byte 4: Off duration (0 = no flashing, 1-255 = flash off time)
"""

import requests
import time
from typing import Tuple, Optional

# Configuration
DEVICE_EUI = "2020203705250102"
DOWNLINK_SERVICE_URL = "http://localhost:8000"
FPORT = 15  # Kuando Busylight uses FPort 15

class KuandoBusylightTester:
    def __init__(self, dev_eui: str = DEVICE_EUI):
        self.dev_eui = dev_eui
        self.results = []

    def create_payload(self, red: int, blue: int, green: int, on_duration: int = 255, off_duration: int = 0) -> str:
        """
        Create hex payload for Kuando Busylight

        Args:
            red: Red intensity (0-255)
            blue: Blue intensity (0-255)
            green: Green intensity (0-255)
            on_duration: On duration (255 = solid)
            off_duration: Off duration (0 = no flashing)

        Returns:
            Hex string payload
        """
        payload_bytes = bytes([red, blue, green, on_duration, off_duration])
        return payload_bytes.hex().upper()

    def send_color(self, red: int, blue: int, green: int,
                   on_duration: int = 255, off_duration: int = 0,
                   confirmed: bool = False) -> dict:
        """Send color command to Kuando Busylight"""
        payload = self.create_payload(red, blue, green, on_duration, off_duration)

        print(f"\n{'='*60}")
        print(f"Sending: RGB({red}, {blue}, {green})")
        print(f"Payload: {payload}")
        print(f"On/Off:  {on_duration}/{off_duration}")

        try:
            response = requests.post(
                f"{DOWNLINK_SERVICE_URL}/downlink/send",
                json={
                    "dev_eui": self.dev_eui,
                    "fport": FPORT,
                    "data": payload,
                    "confirmed": confirmed
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result}")
                return {
                    "success": True,
                    "rgb": (red, blue, green),
                    "payload": payload,
                    "response": result
                }
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "rgb": (red, blue, green),
                    "payload": payload,
                    "error": response.text
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            return {
                "success": False,
                "rgb": (red, blue, green),
                "payload": payload,
                "error": str(e)
            }

    def test_primary_colors(self, intensity: int = 255):
        """Test primary colors at specified intensity"""
        print(f"\n{'#'*60}")
        print(f"# TESTING PRIMARY COLORS (Intensity: {intensity})")
        print(f"{'#'*60}")

        tests = [
            ("Red", intensity, 0, 0),
            ("Green", 0, 0, intensity),
            ("Blue", 0, intensity, 0),
        ]

        for name, r, b, g in tests:
            result = self.send_color(r, b, g)
            self.results.append({
                "category": "Primary Colors",
                "name": name,
                "intensity": intensity,
                **result
            })

            # Ask user to confirm what they see
            observed = input(f"\nWhat color do you see for {name} RGB({r},{b},{g})? Press Enter to continue... ")
            self.results[-1]["observed"] = observed or name
            time.sleep(1)

    def test_secondary_colors(self, intensity: int = 255):
        """Test secondary colors at specified intensity"""
        print(f"\n{'#'*60}")
        print(f"# TESTING SECONDARY COLORS (Intensity: {intensity})")
        print(f"{'#'*60}")

        tests = [
            ("Yellow", intensity, 0, intensity),  # Red + Green
            ("Cyan", 0, intensity, intensity),    # Blue + Green
            ("Magenta", intensity, intensity, 0), # Red + Blue
        ]

        for name, r, b, g in tests:
            result = self.send_color(r, b, g)
            self.results.append({
                "category": "Secondary Colors",
                "name": name,
                "intensity": intensity,
                **result
            })

            observed = input(f"\nWhat color do you see for {name} RGB({r},{b},{g})? Press Enter to continue... ")
            self.results[-1]["observed"] = observed or name
            time.sleep(1)

    def test_white(self, intensity: int = 255):
        """Test white color (all LEDs on)"""
        print(f"\n{'#'*60}")
        print(f"# TESTING WHITE (Intensity: {intensity})")
        print(f"{'#'*60}")

        result = self.send_color(intensity, intensity, intensity)
        self.results.append({
            "category": "White",
            "name": "White",
            "intensity": intensity,
            **result
        })

        observed = input(f"\nWhat color do you see for White RGB({intensity},{intensity},{intensity})? Press Enter to continue... ")
        self.results[-1]["observed"] = observed or "White"
        time.sleep(1)

    def test_brightness_levels(self, color: str = "red"):
        """Test different brightness levels for a color"""
        print(f"\n{'#'*60}")
        print(f"# TESTING BRIGHTNESS LEVELS FOR {color.upper()}")
        print(f"{'#'*60}")

        levels = [25, 51, 102, 153, 204, 255]  # ~10%, 20%, 40%, 60%, 80%, 100%

        color_map = {
            "red": (1, 0, 0),
            "green": (0, 0, 1),
            "blue": (0, 1, 0),
        }

        if color.lower() not in color_map:
            print(f"Invalid color: {color}")
            return

        r_mult, b_mult, g_mult = color_map[color.lower()]

        for level in levels:
            r = level * r_mult
            b = level * b_mult
            g = level * g_mult

            result = self.send_color(r, b, g)
            percentage = int((level / 255) * 100)

            self.results.append({
                "category": f"Brightness - {color}",
                "name": f"{color} {percentage}%",
                "intensity": level,
                **result
            })

            observed = input(f"\nBrightness at {percentage}% - what do you observe? Press Enter to continue... ")
            self.results[-1]["observed"] = observed or f"{percentage}%"
            time.sleep(1)

    def test_off(self):
        """Turn off the light"""
        print(f"\n{'#'*60}")
        print(f"# TURNING OFF LIGHT")
        print(f"{'#'*60}")

        result = self.send_color(0, 0, 0)
        self.results.append({
            "category": "Off",
            "name": "Off",
            "intensity": 0,
            **result
        })
        print("Light should be OFF")
        time.sleep(1)

    def generate_markdown_report(self, filename: str = "KUANDO_COLOR_RESULTS.md"):
        """Generate markdown documentation from test results"""

        with open(filename, 'w') as f:
            f.write("# Kuando Busylight - Color Testing Results\n\n")
            f.write(f"**Device EUI:** {self.dev_eui}\n\n")
            f.write(f"**Test Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            # Group by category
            categories = {}
            for result in self.results:
                cat = result.get("category", "Other")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(result)

            for category, items in categories.items():
                f.write(f"## {category}\n\n")
                f.write("| Color | RGB Values | Hex Payload | Observed Result |\n")
                f.write("|-------|-----------|-------------|------------------|\n")

                for item in items:
                    name = item.get("name", "Unknown")
                    rgb = item.get("rgb", (0, 0, 0))
                    payload = item.get("payload", "N/A")
                    observed = item.get("observed", "Not recorded")

                    f.write(f"| {name} | RGB{rgb} | `{payload}` | {observed} |\n")

                f.write("\n")

            # Add payload format reference
            f.write("---\n\n")
            f.write("## Payload Format\n\n")
            f.write("```\n")
            f.write("Byte 0: Red intensity (0-255)\n")
            f.write("Byte 1: Blue intensity (0-255)\n")
            f.write("Byte 2: Green intensity (0-255)\n")
            f.write("Byte 3: On duration (255 = solid)\n")
            f.write("Byte 4: Off duration (0 = no flashing)\n")
            f.write("```\n\n")

            f.write("## Notes\n\n")
            f.write("- FPort: 15\n")
            f.write("- Payload is sent as HEX string\n")
            f.write("- Color byte order: R-B-G (not R-G-B!)\n")

        print(f"\n✅ Report saved to: {filename}")

def interactive_test():
    """Interactive testing mode"""
    tester = KuandoBusylightTester()

    print(f"""
╔════════════════════════════════════════════════════════════╗
║        Kuando Busylight Color Testing Tool                ║
║        Device EUI: {DEVICE_EUI}                ║
╚════════════════════════════════════════════════════════════╝

This tool will help you test and document color combinations.
After each test, you'll be asked to confirm what you observe.
""")

    while True:
        print(f"\n{'='*60}")
        print("MENU:")
        print("  1. Test Primary Colors (Red, Green, Blue)")
        print("  2. Test Secondary Colors (Yellow, Cyan, Magenta)")
        print("  3. Test White")
        print("  4. Test Brightness Levels")
        print("  5. Test Custom Color")
        print("  6. Turn Off")
        print("  7. Generate Report")
        print("  8. Run Full Test Suite")
        print("  0. Exit")
        print("="*60)

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            intensity = int(input("Intensity (0-255, default 255): ") or "255")
            tester.test_primary_colors(intensity)

        elif choice == "2":
            intensity = int(input("Intensity (0-255, default 255): ") or "255")
            tester.test_secondary_colors(intensity)

        elif choice == "3":
            intensity = int(input("Intensity (0-255, default 255): ") or "255")
            tester.test_white(intensity)

        elif choice == "4":
            color = input("Color (red/green/blue): ").strip().lower()
            tester.test_brightness_levels(color)

        elif choice == "5":
            r = int(input("Red (0-255): "))
            b = int(input("Blue (0-255): "))
            g = int(input("Green (0-255): "))
            result = tester.send_color(r, b, g)
            observed = input("What do you observe? ")
            tester.results.append({
                "category": "Custom",
                "name": f"RGB({r},{b},{g})",
                "rgb": (r, b, g),
                "observed": observed,
                **result
            })

        elif choice == "6":
            tester.test_off()

        elif choice == "7":
            filename = input("Filename (default: KUANDO_COLOR_RESULTS.md): ").strip()
            tester.generate_markdown_report(filename or "KUANDO_COLOR_RESULTS.md")

        elif choice == "8":
            print("\n🚀 Running full test suite...")
            tester.test_primary_colors(255)
            tester.test_secondary_colors(255)
            tester.test_white(255)
            tester.test_brightness_levels("red")
            tester.test_off()
            tester.generate_markdown_report()

        elif choice == "0":
            print("\n👋 Goodbye!")
            break

        else:
            print("Invalid option!")

if __name__ == "__main__":
    interactive_test()
