from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.components import mqtt

from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up climate entities for a config entry."""
    known_devices = hass.data[DOMAIN].get("known_devices", {})
    entities = []

    for device_key, device_info in known_devices.items():
        if isinstance(device_key, tuple) and len(device_key) == 2:
            device_type, device_id = device_key
            if device_type == "thermostat":
                for thermostat_id, thermostat_info in device_info.items():
                    _LOGGER.debug("Adding thermostat entity for device: %s, thermostat: %s", device_id, thermostat_id)
                    entities.append(
                        LANBONThermostat(
                            hass,
                            device_id,
                            thermostat_id,
                            thermostat_info["device_id_raw"],
                            thermostat_info["thermostat_id_raw"],
                            thermostat_info["temperature_state_topic"],
                            thermostat_info["temperature_detect_topic"],
                            thermostat_info["mode_state_topic"],
                            thermostat_info["temperature_set_topic"],
                            thermostat_info["mode_set_topic"],
                        )
                    )
    async_add_entities(entities, update_before_add=True)
    hass.data[DOMAIN]["add_climate_entities"] = async_add_entities

class LANBONThermostat(ClimateEntity):
    def __init__(
        self,
        hass,
        device_id,
        thermostat_id,
        device_id_raw,
        thermostat_id_raw,
        temperature_state_topic,
        temperature_detect_topic,
        mode_state_topic,
        temperature_set_topic,
        mode_set_topic,
    ):
        self.hass = hass
        self._device_id = device_id
        self._thermostat_id = thermostat_id
        self._device_id_raw = device_id_raw
        self._thermostat_id_raw = thermostat_id_raw
        self._temperature_state_topic = temperature_state_topic
        self._temperature_detect_topic = temperature_detect_topic
        self._mode_state_topic = mode_state_topic
        self._temperature_set_topic = temperature_set_topic
        self._mode_set_topic = mode_set_topic
        self._unsubscribe = None

        self._target_temperature = None
        self._current_temperature = None
        self._mode = None

    @property
    def unique_id(self):
        return f"lanbon_thermostat_{self._device_id}_{self._thermostat_id}"

    @property
    def name(self):
        return f"LANBON Thermostat {self._device_id_raw} {self._thermostat_id_raw}"

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def hvac_mode(self):
        if self._mode == "off":
            return HVAC_MODE_OFF
        elif self._mode == "auto":
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        return [HVAC_MODE_OFF, HVAC_MODE_AUTO]

    @property
    def supported_features(self):
        return SUPPORT_TARGET_TEMPERATURE

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await mqtt.async_publish(self.hass, self._temperature_set_topic, str(temperature), qos=0, retain=False)
            self._target_temperature = temperature
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        mode = "off" if hvac_mode == HVAC_MODE_OFF else "auto"
        await mqtt.async_publish(self.hass, self._mode_set_topic, mode, qos=0, retain=False)
        self._mode = mode
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        @callback
        def message_received(msg):
            if msg.topic == self._temperature_state_topic:
                try:
                    self._target_temperature = float(msg.payload)
                except ValueError:
                    _LOGGER.error("Invalid temperature state payload: %s", msg.payload)
            elif msg.topic == self._temperature_detect_topic:
                try:
                    self._current_temperature = float(msg.payload)
                except ValueError:
                    _LOGGER.error("Invalid temperature detect payload: %s", msg.payload)
            elif msg.topic == self._mode_state_topic:
                self._mode = msg.payload
            self.async_write_ha_state()

        self._unsubscribe = await mqtt.async_subscribe(
            self.hass,
            [self._temperature_state_topic, self._temperature_detect_topic, self._mode_state_topic],
            message_received,
            qos=0,
        )

    async def async_will_remove_from_hass(self):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
