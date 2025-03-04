# LanbonHAIntegration

**LanbonHAIntegration** is a custom integration for [Home Assistant](https://www.home-assistant.io/) that supports automatic discovery and control of LANBON devices using MQTT. Designed for all LANBON devices that can connect to an MQTT server, this integration includes support for switches and thermostats, with a workaround for the known issue with 4-gang switch models (`L8-HS4`).

---

## Features

- **Automatic Device Discovery**: Seamlessly detects LANBON switches and thermostats connected via MQTT and adds them to Home Assistant.
- **Broad Compatibility**: Supports all LANBON devices configurable to work with an MQTT server.
- **4-Gang Switch Fix**: Resolves a hardware issue with the `L8-HS4` model, ensuring reliable management of `gang4` switches by momentarily toggling `gang1`.
- **Thermostat Support**: Controls and monitors LANBON thermostats, including target temperature and modes (auto/off).
- **State Persistence**: Stores device configurations and topics for consistent operation after Home Assistant restarts.
- **State Synchronization**: Automatically requests device states at startup to ensure synchronization.

---

## Installation

### HACS Installation (Recommended)

1. Open the HACS panel in Home Assistant.
2. Click on the `Integrations` tab and then click `+ Explore & Download Repositories`.
3. Search for `LanbonHAIntegration` and install the integration.
4. Restart Home Assistant.

### Manual Installation

1. Download the latest release from the [Releases](https://github.com/your-username/LanbonHAIntegration/releases) page.
2. Extract the files to the `custom_components/lanbon_switch` directory in your Home Assistant configuration folder.
3. Restart Home Assistant.

---

## Configuration

This integration requires no manual configuration for discovery. LANBON devices will automatically appear in Home Assistant once connected to the MQTT server.

### MQTT Configuration for LANBON Devices

Ensure your LANBON devices are configured to publish MQTT messages with the following topic structures:

#### Switches
- **State Topic**: `homeassistant/<device_id>/switch/<switch_id>/state`
- **Command Topic**: `homeassistant/<device_id>/switch/<switch_id>/set`

Example:
- `homeassistant/D6925E1A7741/switch/08F9E003F138-01/state`
- `homeassistant/D6925E1A7741/switch/08F9E003F138-01/set`

#### Thermostats
- **Temperature State**: `homeassistant/<device_id>/thermostat/<thermostat_id>/temperatureState`
- **Detected Temperature**: `homeassistant/<device_id>/thermostat/<thermostat_id>/temperatureDetect`
- **Mode State**: `homeassistant/<device_id>/thermostat/<thermostat_id>/modeState`
- **Temperature Set**: `homeassistant/<device_id>/thermostat/<thermostat_id>/temperatureSet` *(assumed)*
- **Mode Set**: `homeassistant/<device_id>/thermostat/<thermostat_id>/modeSet` *(assumed)*

Example:
- `homeassistant/D6925E1A7741/thermostat/409151FA9E8C/temperatureState`
- `homeassistant/D6925E1A7741/thermostat/409151FA9E8C/temperatureSet`

---

## Known Issues

### 4-Gang Switch Fix (`L8-HS4`)
- Due to hardware constraints, controlling `gang4` requires temporarily toggling `gang1`. This workaround ensures `gang4` operates correctly without impacting the rest of the device's functionality.

### Thermostat Command Topics
- The integration assumes `temperatureSet` and `modeSet` topics for controlling the thermostat. If these are incorrect, update them in `__init__.py` and `climate.py` based on your device’s MQTT configuration.

---

## Troubleshooting

### Devices Not Detected
- Confirm that your LANBON devices are publishing MQTT messages using the correct topic format.
- Check the MQTT broker logs to ensure messages are being received.
- Restart Home Assistant to force a discovery sync.

### Incorrect or Missing States
- Verify that the devices are powered on and correctly configured.
- Check the respective state topics for accurate status updates.

---

## Contributing

Contributions are welcome! If you encounter issues or have feature requests, feel free to open an issue or pull request in the [GitHub repository](https://github.com/your-username/LanbonHAIntegration).

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgments

- Thanks to the Home Assistant and MQTT communities for providing inspiration and support.
- Inspired by the need for reliable integration of LANBON devices into smart home setups.
