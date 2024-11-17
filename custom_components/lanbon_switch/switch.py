import asyncio
from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TOPIC_PREFIX, SWITCH_SUBTOPIC

import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up switches for a config entry."""
    known_devices = hass.data[DOMAIN].get("known_devices", {})
    entities = []

    for device_id, switches in known_devices.items():
        for switch_id, switch_info in switches.items():
            topic_state = f"{TOPIC_PREFIX}{switch_info['device_id_raw']}/{SWITCH_SUBTOPIC}/{switch_info['switch_id_raw']}/state"
            _LOGGER.warning("Adding entity for device: %s, switch: %s", device_id, switch_id)
            entities.append(
                LANBONSwitch(
                    hass,
                    device_id,
                    switch_id,
                    switch_info["device_id_raw"],
                    switch_info["switch_id_raw"],
                    topic_state,
                    switch_info["set_topic"],
                )
            )
    async_add_entities(entities, update_before_add=True)

class LANBONSwitch(SwitchEntity):
    def __init__(self, hass, device_id, switch_id, device_id_raw, switch_id_raw, topic_state, topic_set):
        self.hass = hass
        self._device_id = device_id
        self._switch_id = switch_id
        self._device_id_raw = device_id_raw
        self._switch_id_raw = switch_id_raw
        self._topic_state = topic_state
        self._topic_set = topic_set
        self._state = None
        self._unsubscribe = None

    @property
    def unique_id(self):
        return f"lanbon_switch_{self._device_id}_{self._switch_id}"

    @property
    def name(self):
        return f"LANBON Switch {self._device_id_raw} Switch {self._switch_id_raw}"

    @property
    def is_on(self):
        return self._state == "ON"

    async def async_turn_on(self, **kwargs):
        await mqtt.async_publish(self.hass, self._topic_set, "ON", qos=0, retain=False)
        self._state = "ON"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await mqtt.async_publish(self.hass, self._topic_set, "OFF", qos=0, retain=False)
        self._state = "OFF"
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        @callback
        def message_received(msg):
            payload = msg.payload
            if payload in ["ON", "OFF"]:
                self._state = payload
                self.async_write_ha_state()

        self._unsubscribe = await mqtt.async_subscribe(self.hass, self._topic_state, message_received, qos=0)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
