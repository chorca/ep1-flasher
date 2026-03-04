# EP1 CLI Flasher

A command-line tool to flash Everything Presence One devices, mimicking the functionality of the web-based ESP Web Tools flasher.

## Features

- Interactive CLI interface for selecting firmware options
- Supports all EP1 configurations:
  - Home Assistant and SmartThings platforms
  - SEN0395 and SEN0609 mmWave sensors
  - CO2 module support
  - Board revisions 1.3/1.4, 1.5, and 1.6
  - Bluetooth and Non-Bluetooth firmware
  - Stable and Beta firmware channels
- Downloads firmware directly from EverythingSmartHome
- Uses esptool for flashing
- Built-in WiFi configuration via Improv Serial (for non-Bluetooth firmware)

## Installation

### Quick Start (uses virtual environment)

```bash
# This will create a virtual environment and install dependencies automatically
./flash.sh
```

## Usage

Run the flasher (recommended - automatically sets up environment):

```bash
./flash.sh
```

Or run directly:

```bash
python ep1-flasher.py
```

The tool will guide you through the following steps:

1. **Select Platform**: Choose Home Assistant or SmartThings
2. **Select Board Revision**: Choose 1.6, 1.5, or 1.3/1.4
3. **Select mmWave Sensor**: Choose DFRobot SEN0609 or SEN0395 (depends on board revision)
4. **Select CO2 Module**: Choose None or CO2 Module
5. **Select Bluetooth Option**: Choose Bluetooth Proxy or No Bluetooth (Home Assistant only)
6. **Select Firmware Version**: Choose Stable or Beta

The tool will then:
- Download the appropriate firmware
- Detect your EP1 on USB
- Erase flash and flash the new firmware
- Configure WiFi (automatically for Bluetooth firmware, or via serial for non-Bluetooth)

## Configure WiFi Separately

If you flashed your EP1 with "No Bluetooth" firmware, you can configure WiFi separately using the Improv Serial protocol:

```bash
./flash.sh
```

Select **"Configure WiFi"** from the main menu, then:
1. Select the serial port your EP1 is connected to
2. Enter your WiFi network name (SSID)
3. Enter your WiFi password

The device will attempt to connect to your WiFi network and should appear in Home Assistant within 30-60 seconds.

## Requirements

- Python 3.7+
- pyserial
- requests
- esptool

## WiFi Configuration Options

When flashing for **Home Assistant**, you have two firmware options:

### Bluetooth Firmware (Default)
- Enables Bluetooth and Improv for easy WiFi setup
- Requires the Home Assistant Android/iOS app to detect and configure WiFi
- Use the **[Add Device](https://my.home-assistant.io/redirect/integrations/)** flow in Home Assistant to connect

### Non-Bluetooth Firmware
- Disables Bluetooth for improved WiFi stability
- Requires manual WiFi configuration via USB serial (Improv Serial)
- The flasher will prompt you to configure WiFi after flashing, or you can run `./flash.sh` and select "Configure WiFi" later

For **SmartThings**, Bluetooth is always enabled and configuration is handled through the SmartThings app.

## Troubleshooting

### "No ESP32 device found"

- Make sure the EP1 is connected via USB
- Check that no other program is using the serial port
- Try a different USB cable (some are charge-only)

### Flash fails with timeout

This is the same issue as the web flasher. Try:
- Using a different USB port
- Closing other serial terminal programs
- Running with sudo (may be needed for serial port access on Linux)

## License

MIT License
