import asyncio
from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TOPIC_PREFIX, SWITCH_SUBTOPIC, STATE_SUBTOPIC
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None
):
    if discovery_info is None:
        return

    # Use normalized IDs
    device_id = discovery_info["device_id"].lower()
    device_id_raw = discovery_info["device_id_raw"]
    switch_id = discovery_info["switch_id"].lower()
    switch_id_raw = discovery_info["switch_id_raw"]
    set_topic = discovery_info["set_topic"]
    topic_state = f"{TOPIC_PREFIX}{device_id_raw}/{SWITCH_SUBTOPIC}/{switch_id_raw}/state"

    async_add_entities([LANBONSwitch(hass, device_id, switch_id, device_id_raw, switch_id_raw, topic_state, set_topic)])

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up switches for a config entry."""
    # Retrieve discovered devices from the integration's known devices
    known_devices = hass.data[DOMAIN].get("known_devices", {})

    entities = []
    for device_id, switches in known_devices.items():
        for switch_id, switch_info in switches.items():
            topic_state = f"{TOPIC_PREFIX}{switch_info['device_id_raw']}/{SWITCH_SUBTOPIC}/{switch_info['switch_id_raw']}/state"
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
    async_add_entities(entities)


class LANBONSwitch(SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        switch_id: str,
        device_id_raw: str,
        switch_id_raw: str,
        topic_state: str,
        topic_set: str
    ):
        self.hass = hass
        self._device_id = device_id  # Normalized
        self._switch_id = switch_id  # Normalized
        self._device_id_raw = device_id_raw  # Raw
        self._switch_id_raw = switch_id_raw  # Raw
        self._topic_state = topic_state
        self._topic_set = topic_set
        self._unsubscribe = None

        # Initialize state
        self._state = None

        # Identify if this is gang4
        self._is_gang4 = self._switch_id.endswith('-04')

        if self._is_gang4:
            # Compute gang1's identifiers by replacing '-04' with '-01'
            self._gang1_switch_id_raw = self._switch_id_raw.replace('-04', '-01')
            self._gang1_switch_id = self._switch_id.replace('-04', '-01')
            self._gang1_topic_set = f"{TOPIC_PREFIX}{self._device_id_raw}/{SWITCH_SUBTOPIC}/{self._gang1_switch_id_raw}/set"
            self._gang1_entity_id = f"switch.lanbon_switch_{self._device_id}_switch_{self._gang1_switch_id.replace('-', '_')}"

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
        if self._is_gang4:
            gang1_state = self.hass.states.get(self._gang1_entity_id).state.upper()

            # Turn on gang4
            await mqtt.async_publish(self.hass, self._topic_set, "ON", qos=0, retain=False)
            await asyncio.sleep(0.01)

            # Turn on gang1
            await mqtt.async_publish(self.hass, self._gang1_topic_set, "ON", qos=0, retain=False)
            await asyncio.sleep(0.01)

            # Turn off gang4
            await mqtt.async_publish(self.hass, self._topic_set, "OFF", qos=0, retain=False)
            await asyncio.sleep(0.01)

            # Back to original state gang1
            await mqtt.async_publish(self.hass, self._gang1_topic_set, gang1_state, qos=0, retain=False)

            # Update state
            self._state = "ON"
            self.async_write_ha_state()
        else:
            # Regular behavior for other gangs
            await mqtt.async_publish(self.hass, self._topic_set, "ON", qos=0, retain=False)
            # Update state
            self._state = "ON"
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        if self._is_gang4:
            # Check initial state of gang1
            gang1_state = self.hass.states.get(self._gang1_entity_id)
            gang1_is_on = gang1_state.state == 'on' if gang1_state else False

            # Turn on gang4
            await mqtt.async_publish(self.hass, self._topic_set, "ON", qos=0, retain=False)
            await asyncio.sleep(0.3)

            # Turn off gang1
            await mqtt.async_publish(self.hass, self._gang1_topic_set, "OFF", qos=0, retain=False)
            await asyncio.sleep(0.1)

            # Turn off gang4
            await mqtt.async_publish(self.hass, self._topic_set, "OFF", qos=0, retain=False)
            await asyncio.sleep(0.3)

            if gang1_is_on:
                # If gang1 was originally on, turn it back on
                await mqtt.async_publish(self.hass, self._gang1_topic_set, "ON", qos=0, retain=False)

            # Update state
            self._state = "OFF"
            self.async_write_ha_state()
        else:
            # Regular behavior for other gangs
            await mqtt.async_publish(self.hass, self._topic_set, "OFF", qos=0, retain=False)
            # Update state
            self._state = "OFF"
            self.async_write_ha_state()

    async def async_added_to_hass(self):
        @callback
        def message_received(msg):
            payload = msg.payload
            if payload in ["ON", "OFF"]:
                if not self._is_gang4:
                    self._state = payload
                    self.async_write_ha_state()
                else:
                    # Ignore state updates for gang4
                    pass

        self._unsubscribe = await mqtt.async_subscribe(self.hass, self._topic_state, message_received, qos=0)

    async def async_will_remove_from_hass(self):
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
