#!/usr/bin/env python3
"""
EP1 CLI Flasher - A command-line tool to flash Everything Presence One devices

This tool mimics the functionality of the web-based ESP Web Tools flasher,
allowing users to select their configuration options and flash the firmware
directly from the command line.
"""

import os
import sys
import json
import time
import shutil
import subprocess
import tempfile
import signal
import serial
import serial.tools.list_ports

# Try to import esptool as a Python module
try:
    import esptool

    ESPROG = "esptool"  # Will use -m esptool to invoke
except ImportError:
    ESPROG = None

# Base URL for firmware manifests
BASE_URL = "https://everythingsmarthome.github.io/everything-presence-one"


# Color codes for terminal output
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


# Signal handling for clean exit
def signal_handler(signum, frame):
    """Handle SIGINT and SIGTERM for clean exit"""
    print("\n")
    # print(f"\n\n{Colors.YELLOW}Interrupted by signal ({signum}). Exiting cleanly...{Colors.END}")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def print_header(text):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{Colors.END}\n")


def print_option(num, text, desc=""):
    print(f"  {Colors.BOLD}{num}.{Colors.END} {text}")
    if desc:
        print(f"     {Colors.YELLOW}{desc}{Colors.END}")


def get_selection(max_val, prompt="Enter your choice"):
    while True:
        try:
            choice = int(input(f"{prompt} (1-{max_val}): ").strip())
            if 1 <= choice <= max_val:
                return choice
            print(
                f"{Colors.RED}Please enter a number between 1 and {max_val}{Colors.END}"
            )
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number{Colors.END}")


def get_yes_no(prompt):
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print(f"{Colors.RED}Please enter 'y' or 'n'{Colors.END}")


def get_wifi_credentials():
    """Prompt user for WiFi SSID and password"""
    print("Enter your WiFi network details to configure the device.")

    ssid = input("WiFi SSID: ").strip()
    while not ssid:
        print(f"{Colors.RED}SSID cannot be empty{Colors.END}")
        ssid = input("WiFi SSID: ").strip()

    import getpass

    password = getpass.getpass("WiFi Password (press Enter for open network): ").strip()

    return ssid, password


def check_dependencies():
    """Check if required dependencies are available"""
    errors = []

    # Check for Python
    print("Checking dependencies...")

    # Check for esptool
    if ESPROG:
        print(f"  {Colors.GREEN}✓{Colors.END} esptool found (Python module)")
    else:
        print(f"  {Colors.RED}✗{Colors.END} esptool not found")
        print(f"    Install with: pip install esptool")
        errors.append("esptool")

    # Check for pyserial
    try:
        import serial

        print(f"  {Colors.GREEN}✓{Colors.END} pyserial found")
    except ImportError:
        print(f"  {Colors.RED}✗{Colors.END} pyserial not found")
        print(f"    Install with: pipx install pyserial")
        errors.append("pyserial")

    # Check for requests
    try:
        import requests

        print(f"  {Colors.GREEN}✓{Colors.END} requests found")
    except ImportError:
        print(f"  {Colors.RED}✗{Colors.END} requests not found")
        print(f"    Install with: pipx install requests")
        errors.append("requests")

    if errors:
        print(
            f"\n{Colors.RED}Missing dependencies. Please install them before continuing.{Colors.END}"
        )
        return False
    return True


def select_platform():
    """Step 1: Select Smart Home Platform"""
    print_header("Step 1: Select Integration Type")
    print_option(1, "Home Assistant", "Integrate with Home Assistant")
    print_option(2, "SmartThings", "Integrate with Samsung SmartThings")

    choice = get_selection(2)
    return "Home Assistant" if choice == 1 else "SmartThings"


def select_board_revision():
    """Step 2: Select Board Revision"""
    print_header("Step 2: Select Main Board Version")
    print_option(1, "Revision 1.6", "April 2025+")
    print_option(2, "Revision 1.5", "March 2024 - April 2025")
    print_option(3, "Revision 1.3/1.4", "Oct 2022 - Feb 2024")

    choice = get_selection(3)
    if choice == 3:
        return "1.3/1.4"
    elif choice == 2:
        return "1.5"
    else:
        return "1.6"


def select_mmwave_sensor(board_revision):
    """Step 3: Select mmWave Sensor - depends on board revision"""
    print_header("Step 3: Select mmWave Sensor")

    # Board revision 1.3/1.4 only supports SEN0395
    if board_revision == "1.3/1.4":
        print_option(
            1, "DFRobot SEN0395", "6-pin mmWave sensor (required for Rev 1.3/1.4)"
        )
        choice = get_selection(1)
        return "SEN0395"

    # Board revision 1.5 and 1.6 support both
    print_option(1, "DFRobot SEN0609", "5-pin mmWave sensor (after March 2024)")
    print_option(2, "DFRobot SEN0395", "6-pin mmWave sensor (before March 2024)")

    choice = get_selection(2)
    return "SEN0395" if choice == 2 else "SEN0609"


def select_co2_module():
    """Step 4: Select CO2 Module"""
    print_header("Step 4: Select CO2 Sensor")
    print_option(1, "No CO2 Sensor", "Base EP1 only")
    print_option(2, "CO2 Sensor", "Add CO2 add-on module")

    choice = get_selection(2)
    return None if choice == 1 else "CO2"


def select_ble_option(platform):
    """Step 5: Select BLE Option - only for Home Assistant"""
    if platform != "Home Assistant":
        return None  # SmartThings always has BLE

    print_header("Step 5: Select Bluetooth Option")
    print_option(
        1,
        "Yes - Bluetooth Proxy",
        "Enable Bluetooth and Improv for easy WiFi setup and proxy of BLE devices",
    )
    print_option(
        2, "No - Standalone", "Disable Bluetooth if WiFi stability issues arise"
    )

    choice = get_selection(2)
    return "Bluetooth" if choice == 1 else "No-Bluetooth"


def select_firmware_version():
    """Step 6: Select Firmware Version"""
    print_header("Step 6: Select Firmware Version")
    print_option(1, "Stable", "Production-tested firmware")
    print_option(2, "Beta", "Latest features (may have bugs)")

    choice = get_selection(2)
    return "Stable" if choice == 1 else "Beta"


def build_manifest_url(
    platform, sensor, addon_module, board_revision, firmware_type, firmware_version
):
    """Build the manifest URL based on selections"""

    # Build base name
    if platform == "Home Assistant":
        base = "everything-presence-one-ha"
    else:
        base = "everything-presence-one-st"

    # Add sensor model
    if sensor == "SEN0609":
        base += "-sen0609"
    else:
        base += "-sen0395"

    # Add module type
    if addon_module == "CO2":
        base += "-co2"
    else:
        base += "-nomodule"

    # Add connection type
    if platform == "Home Assistant":
        if firmware_type == "Bluetooth":
            base += "-ble"
        else:
            base += "-noble"
    else:
        # SmartThings always has BLE built-in
        base += "-ble"

    # Add board revision
    if platform == "SmartThings":
        if sensor == "SEN0609":
            base += "-rev1-6"
        else:
            base += "-rev1-5"
    else:
        if board_revision == "1.3/1.4":
            base += "-rev1-3"
        elif board_revision == "1.5":
            base += "-rev1-5"
        elif board_revision == "1.6":
            base += "-rev1-6"

    # Add channel (stable/beta)
    if firmware_version == "Beta":
        base += "-beta"
    else:
        base += "-stable"

    return f"{base}-manifest.json"


def display_summary(
    platform, sensor, addon_module, board_revision, firmware_type, firmware_version
):
    """Display summary of selections"""
    print_header("Firmware Selection Summary")
    print(f"  Platform:          {platform}")
    print(f"  mmWave Sensor:    {sensor}")
    print(f"  Add-on Module:    {addon_module if addon_module else 'None'}")
    print(f"  Board Revision:   {board_revision}")
    if platform == "Home Assistant":
        print(
            f"  Firmware Type:     {'Bluetooth' if firmware_type == 'Bluetooth' else 'No Bluetooth'}"
        )
    print(f"  Version:           {firmware_version}")


def find_serial_port():
    """Attempt to find the ESP32 serial port"""
    possible_ports = [
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
        "/dev/ttyACM0",
        "/dev/ttyACM1",
    ]

    # Check which ports exist
    available = []
    for p in possible_ports:
        if os.path.exists(p):
            available.append(p)

    if not available:
        return None

    # If only one, use it
    if len(available) == 1:
        return available[0]

    # Let user choose
    print_header("Multiple Serial Ports Found")
    for i, p in enumerate(available, 1):
        print_option(i, p)

    choice = get_selection(len(available), "Select port")
    return available[choice - 1]


def detect_device(port):
    """Try to detect the device on the specified port"""
    if not ESPROG:
        return None

    try:
        result = subprocess.run(
            [sys.executable, "-m", "esptool", "--port", port, "chip-id"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "ESP32" in result.stdout:
            # Extract MAC address
            for line in result.stdout.split("\n"):
                if "MAC:" in line:
                    mac = line.split("MAC:")[1].strip()
                    return mac
            return "ESP32 detected"
    except Exception as e:
        pass

    return None


def download_firmware(manifest_url):
    """Download firmware files from manifest"""
    print(f"\n{Colors.BLUE}Downloading firmware manifest...{Colors.END}")

    try:
        import requests
    except ImportError:
        print(
            f"{Colors.RED}requests library required. Install with: pip install requests{Colors.END}"
        )
        return None, None

    manifest_url = f"{BASE_URL}/{manifest_url}"

    try:
        response = requests.get(manifest_url, timeout=30)
        response.raise_for_status()
        manifest = response.json()
    except Exception as e:
        print(f"{Colors.RED}Failed to download manifest: {e}{Colors.END}")
        return None, None

    print(f"  Firmware: {manifest.get('name', 'Unknown')}")
    print(f"  Version:  {manifest.get('version', 'Unknown')}")

    # Get the factory bin path
    builds = manifest.get("builds", [])
    if not builds:
        print(f"{Colors.RED}No builds found in manifest{Colors.END}")
        return None, None

    parts = builds[0].get("parts", [])
    if not parts:
        print(f"{Colors.RED}No parts found in manifest{Colors.END}")
        return None, None

    factory_bin = parts[0].get("path")
    if not factory_bin:
        print(f"{Colors.RED}No factory bin path in manifest{Colors.END}")
        return None, None

    # Download the firmware
    firmware_url = f"{BASE_URL}/{factory_bin}"
    print(
        f"\n{Colors.BLUE}Downloading firmware ({firmware_url.split('/')[-1]})...{Colors.END}"
    )

    try:
        response = requests.get(firmware_url, timeout=120)
        response.raise_for_status()

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        print(f"  {Colors.GREEN}Downloaded {len(response.content)} bytes{Colors.END}")
        return temp_path, manifest.get("version", "unknown")
    except Exception as e:
        print(f"{Colors.RED}Failed to download firmware: {e}{Colors.END}")
        return None, None


def flash_firmware(port, firmware_path, erase_first=True):
    """Flash the firmware to the device"""
    if not ESPROG:
        print(f"{Colors.RED}esptool not found{Colors.END}")
        return False

    print(f"\n{Colors.BLUE}Flashing firmware to {port}...{Colors.END}")

    # Erase flash first
    if erase_first:
        print("  Erasing flash...\n")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "esptool",
                    "--port",
                    port,
                    "--chip",
                    "esp32",
                    "erase-flash",
                ],
                timeout=60,
            )
            if result.returncode != 0:
                print(f"{Colors.YELLOW}Warning: Erase returned non-zero{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}Failed to erase: {e}{Colors.END}")
            return False

    # Flash firmware
    print("  Writing firmware...\n")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "esptool",
                "--port",
                port,
                "--chip",
                "esp32",
                "write-flash",
                "0x0",
                firmware_path,
            ],
            timeout=300,
        )
        if result.returncode != 0:
            print(
                f"{Colors.RED}Flash failed with return code {result.returncode}{Colors.END}"
            )
            return False

        print(f"  {Colors.GREEN}Flash complete!{Colors.END}")
        return True
    except Exception as e:
        print(f"{Colors.RED}Failed to flash: {e}{Colors.END}")
        return False


# Improv Serial Protocol Constants
IMPROV_MAGIC = b"IMPROV"
IMPROV_VERSION = 1

# Packet Types
IMPROV_TYPE_STATE = 0x01
IMPROV_TYPE_ERROR = 0x02
IMPROV_TYPE_RPC_COMMAND = 0x03
IMPROV_TYPE_RPC_RESULT = 0x04

# State Values
IMPROV_STATE_READY = 0x02
IMPROV_STATE_PROVISIONING = 0x03
IMPROV_STATE_PROVISIONED = 0x04

# RPC Commands
IMPROV_CMD_WIFI_SETTINGS = 0x01
IMPROV_CMD_REQUEST_STATE = 0x02
IMPROV_CMD_REQUEST_INFO = 0x03


def build_improv_packet(packet_type, data):
    """Build an Improv Serial packet"""
    # Build the packet without checksum first
    packet = IMPROV_MAGIC + bytes([IMPROV_VERSION, packet_type, len(data)]) + data

    # Calculate checksum (sum of all bytes mod 256)
    checksum = sum(packet) % 256

    return packet + bytes([checksum])


def parse_improv_response(data):
    """Parse an Improv Serial response packet"""
    if len(data) < 10:
        return None

    # Check magic bytes
    if data[:6] != IMPROV_MAGIC:
        return None

    version = data[6]
    packet_type = data[7]
    length = data[8]
    payload = data[9 : 9 + length]
    received_checksum = data[9 + length] if len(data) > 9 + length else None

    # Verify checksum
    if received_checksum is not None:
        calculated_checksum = sum(data[: 9 + length]) % 256
        if calculated_checksum != received_checksum:
            return None

    return {"version": version, "type": packet_type, "length": length, "data": payload}


def send_improv_command(ser, command_id, data):
    """Send an Improv RPC command and return the response"""
    rpc_data = bytes([command_id]) + bytes([len(data)]) + data
    packet = build_improv_packet(IMPROV_TYPE_RPC_COMMAND, rpc_data)

    ser.write(packet)

    # Wait for response with timeout
    timeout = 10
    start_time = time.time()
    response_bytes = b""

    while time.time() - start_time < timeout:
        if ser.in_waiting > 0:
            response_bytes += ser.read(ser.in_waiting)

            # Try to parse the response
            response = parse_improv_response(response_bytes)
            if response:
                return response
        else:
            time.sleep(0.1)

    return None


def request_improv_state(ser):
    """Request the current Improv state"""
    return send_improv_command(ser, IMPROV_CMD_REQUEST_STATE, b"")


def get_device_info_improv(ser):
    """Get device information via Improv"""
    return send_improv_command(ser, IMPROV_CMD_REQUEST_INFO, b"")


def send_wifi_settings_improv(ser, ssid, password):
    """Send WiFi credentials using Improv Serial protocol"""
    # Build WiFi settings data:
    # - SSID length (1 byte)
    # - SSID (variable)
    # - Password length (1 byte)
    # - Password (variable)

    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")

    # Build the RPC data: command + length + ssid_length + ssid + password_length + password
    rpc_data = (
        bytes([len(ssid_bytes)])
        + ssid_bytes
        + bytes([len(password_bytes)])
        + password_bytes
    )

    return send_improv_command(ser, IMPROV_CMD_WIFI_SETTINGS, rpc_data)


def configure_wifi_via_serial(port, ssid, password, timeout=60):
    """Configure WiFi on the device via Improv Serial

    Uses the Improv Serial protocol to send WiFi credentials to the ESP32 device.
    Reference: https://www.improv-wifi.com/serial/
    """
    print(f"\n{Colors.BLUE}Configuring WiFi via Improv Serial...{Colors.END}")

    try:
        # Open serial connection
        ser = serial.Serial(port, 115200, timeout=1)

        # Clear any existing data in the buffer
        ser.reset_input_buffer()

        # Read any startup data
        startup_data = ser.read(2000)

        # Try to get current state
        print("  Checking device state...")
        state_response = request_improv_state(ser)

        if state_response:
            state = state_response["data"][0] if state_response["data"] else 0

            if state == IMPROV_STATE_READY:
                print("  Device is ready for WiFi configuration")
            elif state == IMPROV_STATE_PROVISIONING:
                print("  Device is already provisioning...")
            elif state == IMPROV_STATE_PROVISIONED:
                print("  Device is already provisioned!")
                ser.close()
                return True
            else:
                print(f"  Unknown state: {state}")
        else:
            print("  Could not get device state (may still work)")

        # Try to get device info
        print(f"  Sending WiFi credentials for network: {ssid}")
        wifi_response = send_wifi_settings_improv(ser, ssid, password)

        ser.close()

        if wifi_response:
            # Parse the response - first byte is the command ID
            if len(wifi_response["data"]) > 0:
                cmd_id = wifi_response["data"][0]
                print(f"  Received response for command: {cmd_id}")

            print(f"  {Colors.GREEN}WiFi credentials sent!{Colors.END}")
            print(
                f"  {Colors.YELLOW}Device is attempting to connect to WiFi...{Colors.END}"
            )
            return True

        # If we didn't get a response but no error, assume it worked
        print(
            f"  {Colors.YELLOW}WiFi credentials sent (no response from device){Colors.END}"
        )
        return True

    except serial.SerialException as e:
        print(f"{Colors.RED}Serial error: {e}{Colors.END}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Error configuring WiFi: {e}{Colors.END}")
        try:
            ser.close()
        except:
            pass
        return False


def wait_for_device_ready(port, timeout=30):
    """Wait for the device to be ready for WiFi configuration via Improv"""
    print(f"  Waiting for device to be ready...")

    try:
        ser = serial.Serial(port, 115200, timeout=1)
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Clear buffer
            ser.reset_input_buffer()

            # Send state request
            state_response = request_improv_state(ser)

            if state_response and state_response["data"]:
                state = state_response["data"][0]

                if state == IMPROV_STATE_READY:
                    print(f"  {Colors.GREEN}Device is ready!{Colors.END}")
                    ser.close()
                    return True
                elif state == IMPROV_STATE_PROVISIONING:
                    print("  Device is already connecting to WiFi...")
                    ser.close()
                    return True
                elif state == IMPROV_STATE_PROVISIONED:
                    print("  Device is already provisioned!")
                    ser.close()
                    return True
                # If we got a response but not a ready state, keep polling

            time.sleep(0.5)

        ser.close()
        print(
            f"  {Colors.YELLOW}Timeout waiting for device, continuing anyway...{Colors.END}"
        )
        return True

    except Exception as e:
        print(f"  {Colors.YELLOW}Could not wait for device: {e}{Colors.END}")
        return True  # Continue anyway


def configure_wifi_only():
    """Standalone WiFi configuration - no flashing"""
    print(f"""
{Colors.BLUE}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         WiFi Configuration - Everything Presence One          ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

This option configures WiFi on an already-flashed EP1 device
using the Improv Serial protocol.
""")

    # Find the serial port
    port = find_serial_port()
    if not port:
        print(f"\n{Colors.RED}No ESP32 device found on serial ports.{Colors.END}")
        print("Make sure the EP1 is connected via USB and try again.")
        sys.exit(1)

    print(f"\n{Colors.GREEN}Found device on {port}{Colors.END}")

    # Configure WiFi via the interactive flow
    configure_wifi_interactive(port)


def configure_wifi_interactive(port):
    """Interactively configure WiFi via serial with the user"""
    print(f"""
{Colors.YELLOW}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║              WiFi Configuration via Serial                    ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
""")

    # Get WiFi credentials
    ssid, password = get_wifi_credentials()

    # Wait for device to be ready (actively poll via Improv)
    wait_for_device_ready(port, timeout=30)

    # Configure WiFi
    success = configure_wifi_via_serial(port, ssid, password)

    if success:
        print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║              WiFi Configuration Complete!                     ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

The WiFi credentials have been sent to the device.

The device should now connect to your WiFi network.
It may take 30-60 seconds for the device to appear in Home Assistant.

If the device doesn't appear, you can:
1. Check your router for a new device
2. Use a serial terminal to debug: screen {port} 115200
3. Re-run this tool and try again
""")
    else:
        print(f"""
{Colors.RED}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║              WiFi Configuration Failed                        ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

Could not automatically configure WiFi.

Please configure WiFi manually using a serial terminal:
  screen {port} 115200

Or re-flash with Bluetooth enabled for easier setup.
""")

    return success


def main():
    print(f"""
{Colors.BLUE}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         EP1 CLI Flasher - Everything Presence One             ║
║         Command-line firmware flashing tool                   ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Main menu - choose action
    print_header("Select Action")
    print_option(1, "Flash Firmware", "Flash the EP1 with new firmware")
    print_option(2, "Configure WiFi", "Configure WiFi via serial (if already flashed)")

    choice = get_selection(2, "Select action")

    if choice == 2:
        # Configure WiFi only
        configure_wifi_only()
        sys.exit(0)

    # Flash firmware flow (original code)
    # Interactive configuration - matches web flasher flow
    platform = select_platform()
    board_revision = select_board_revision()
    sensor = select_mmwave_sensor(board_revision)
    addon_module = select_co2_module()

    if platform == "Home Assistant":
        firmware_type = select_ble_option(platform)
        firmware_version = select_firmware_version()
    else:
        # SmartThings
        firmware_type = None
        firmware_version = "Stable"

    # Display summary and confirm
    display_summary(
        platform, sensor, addon_module, board_revision, firmware_type, firmware_version
    )

    if not get_yes_no("\nProceed with flashing"):
        print("Aborted.")
        sys.exit(0)

    # Build manifest URL
    manifest_url = build_manifest_url(
        platform, sensor, addon_module, board_revision, firmware_type, firmware_version
    )

    print(f"\n{Colors.BLUE}Manifest: {manifest_url}{Colors.END}")

    # Find serial port
    port = find_serial_port()
    if not port:
        print(f"\n{Colors.RED}No ESP32 device found on serial ports.{Colors.END}")
        print("Make sure the EP1 is connected via USB and try again.")
        sys.exit(1)

    print(f"\n{Colors.GREEN}Found device on {port}{Colors.END}")

    # Detect device
    device_info = detect_device(port)
    if device_info:
        print(f"  Detected: {device_info}")

    # Download firmware
    firmware_path, version = download_firmware(manifest_url)
    if not firmware_path:
        print(f"{Colors.RED}Failed to download firmware{Colors.END}")
        sys.exit(1)

    # Flash firmware
    success = flash_firmware(port, firmware_path)

    # Cleanup
    try:
        os.unlink(firmware_path)
    except:
        pass

    if success:
        print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                     Flash Complete!                           ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

The EP1 has been flashed with firmware version {version}.

For SmartThings:
  - Follow the SmartThings setup instructions in the documentation
""")

        # For Home Assistant without Bluetooth, configure WiFi via serial
        if platform == "Home Assistant" and firmware_type == "No-Bluetooth":
            print(f"""
{Colors.YELLOW}Note: Since Bluetooth is disabled, you need to configure WiFi.{Colors.END}
""")
            configure_wifi_interactive(port)
    else:
        print(
            f"\n{Colors.RED}Flash failed. Please check the connection and try again.{Colors.END}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
