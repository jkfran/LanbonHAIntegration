import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import mqtt
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    TOPIC_PREFIX,
    SWITCH_SUBTOPIC,
    STATE_SUBTOPIC,
    SET_SUBTOPIC,
    THERMOSTAT_SUBTOPIC,
    MODE_STATE_SUBTOPIC,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_devices"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from YAML."""
    hass.data.setdefault(
        DOMAIN,
        {"entities": {}, "set_topics": set(), "known_devices": {}},
    )
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a ConfigEntry (UI-based setup)."""
    hass.data.setdefault(
        DOMAIN,
        {"entities": {}, "set_topics": set(), "known_devices": {}},
    )

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    # Load known devices from storage
    stored_data = await store.async_load()
    if stored_data:
        hass.data[DOMAIN]["known_devices"] = stored_data.get("devices", {})
        hass.data[DOMAIN]["set_topics"] = set(stored_data.get("set_topics", []))
    else:
        hass.data[DOMAIN]["known_devices"] = {}
        hass.data[DOMAIN]["set_topics"] = set()

    # Clean up invalid device_key entries
    for device_key in list(hass.data[DOMAIN]["known_devices"].keys()):
        if not (isinstance(device_key, tuple) and len(device_key) == 2):
            _LOGGER.warning("Removing invalid device_key: %s", device_key)
            del hass.data[DOMAIN]["known_devices"][device_key]

    # Save the cleaned-up data
    await store.async_save(
        {
            "devices": hass.data[DOMAIN]["known_devices"],
            "set_topics": list(hass.data[DOMAIN]["set_topics"]),
        }
    )

    # Re-register entities from known devices
    for device_key, device_info in hass.data[DOMAIN]["known_devices"].items():
        if isinstance(device_key, tuple) and len(device_key) == 2:
            device_type, device_id = device_key
            if device_type == "switch":
                for switch_id in device_info:
                    entity_id = f"{device_id}_{switch_id}"
                    if entity_id not in hass.data[DOMAIN]["entities"]:
                        hass.data[DOMAIN]["entities"][entity_id] = True
            elif device_type == "thermostat":
                entity_id = device_id
                if entity_id not in hass.data[DOMAIN]["entities"]:
                    hass.data[DOMAIN]["entities"][entity_id] = True
        else:
            _LOGGER.warning("Skipping invalid device_key: %s", device_key)

    # Forward setup to switch and climate platforms
    _LOGGER.debug("Forwarding entry setup for switches and climate")
    await hass.config_entries.async_forward_entry_setups(entry, ["switch", "climate"])

    async def discover_switch(msg):
        topic = msg.topic
        payload = msg.payload
        _LOGGER.debug("Received switch discovery message on topic: %s, payload: %s", topic, payload)

        parts = topic.split('/')
        if len(parts) != 5:
            _LOGGER.error("Invalid switch topic structure: %s", topic)
            return

        _, device_id_raw, switch_subtopic, switch_id_raw, state_subtopic = parts
        if switch_subtopic != SWITCH_SUBTOPIC or state_subtopic != STATE_SUBTOPIC:
            _LOGGER.debug("Topic does not match expected switch subtopics")
            return

        device_id = device_id_raw.lower()
        switch_id = switch_id_raw.lower()
        entity_id = f"{device_id}_{switch_id}"

        if entity_id in hass.data[DOMAIN]["entities"]:
            return

        set_topic = f"{TOPIC_PREFIX}{device_id_raw}/{SWITCH_SUBTOPIC}/{switch_id_raw}/{SET_SUBTOPIC}"
        hass.data[DOMAIN]["set_topics"].add(set_topic)

        device_key = ("switch", device_id)
        device_entry = hass.data[DOMAIN]["known_devices"].setdefault(device_key, {})
        device_entry[switch_id] = {
            "device_id_raw": device_id_raw,
            "switch_id_raw": switch_id_raw,
            "set_topic": set_topic,
        }

        await store.async_save(
            {
                "devices": hass.data[DOMAIN]["known_devices"],
                "set_topics": list(hass.data[DOMAIN]["set_topics"]),
            }
        )

        hass.data[DOMAIN]["entities"][entity_id] = True

        if "add_switch_entities" in hass.data[DOMAIN]:
            from .switch import LANBONSwitch
            new_entity = LANBONSwitch(
                hass,
                device_id,
                switch_id,
                device_id_raw,
                switch_id_raw,
                f"{TOPIC_PREFIX}{device_id_raw}/{SWITCH_SUBTOPIC}/{switch_id_raw}/{STATE_SUBTOPIC}",
                set_topic,
            )
            hass.data[DOMAIN]["add_switch_entities"]([new_entity], update_before_add=True)

    async def discover_thermostat(msg):
        topic = msg.topic
        payload = msg.payload
        _LOGGER.debug("Received thermostat discovery message on topic: %s, payload: %s", topic, payload)

        parts = topic.split('/')
        if len(parts) != 5:
            _LOGGER.error("Invalid thermostat topic structure: %s", topic)
            return

        _, device_id_raw, thermostat_subtopic, thermostat_id_raw, mode_state_subtopic = parts
        if thermostat_subtopic != THERMOSTAT_SUBTOPIC or mode_state_subtopic != MODE_STATE_SUBTOPIC:
            _LOGGER.debug("Topic does not match expected thermostat subtopics")
            return

        device_id = device_id_raw.lower()
        thermostat_id = thermostat_id_raw.lower()
        entity_id = f"{device_id}_{thermostat_id}"

        if entity_id in hass.data[DOMAIN]["entities"]:
            return

        device_key = ("thermostat", device_id)
        device_entry = hass.data[DOMAIN]["known_devices"].setdefault(device_key, {})
        device_entry[thermostat_id] = {
            "device_id_raw": device_id_raw,
            "thermostat_id_raw": thermostat_id_raw,
            "temperature_state_topic": f"{TOPIC_PREFIX}{device_id_raw}/{THERMOSTAT_SUBTOPIC}/{thermostat_id_raw}/temperatureState",
            "temperature_detect_topic": f"{TOPIC_PREFIX}{device_id_raw}/{THERMOSTAT_SUBTOPIC}/{thermostat_id_raw}/temperatureDetect",
            "mode_state_topic": f"{TOPIC_PREFIX}{device_id_raw}/{THERMOSTAT_SUBTOPIC}/{thermostat_id_raw}/modeState",
            "temperature_set_topic": f"{TOPIC_PREFIX}{device_id_raw}/{THERMOSTAT_SUBTOPIC}/{thermostat_id_raw}/temperatureSet",
            "mode_set_topic": f"{TOPIC_PREFIX}{device_id_raw}/{THERMOSTAT_SUBTOPIC}/{thermostat_id_raw}/modeSet",
        }

        await store.async_save(
            {
                "devices": hass.data[DOMAIN]["known_devices"],
                "set_topics": list(hass.data[DOMAIN]["set_topics"]),
            }
        )

        hass.data[DOMAIN]["entities"][entity_id] = True

        if "add_climate_entities" in hass.data[DOMAIN]:
            from .climate import LANBONThermostat
            new_entity = LANBONThermostat(
                hass,
                device_id,
                thermostat_id,
                device_id_raw,
                thermostat_id_raw,
                device_entry[thermostat_id]["temperature_state_topic"],
                device_entry[thermostat_id]["temperature_detect_topic"],
                device_entry[thermostat_id]["mode_state_topic"],
                device_entry[thermostat_id]["temperature_set_topic"],
                device_entry[thermostat_id]["mode_set_topic"],
            )
            hass.data[DOMAIN]["add_climate_entities"]([new_entity], update_before_add=True)

    # Subscribe to state topics for discovery
    await mqtt.async_subscribe(hass, f"{TOPIC_PREFIX}+/switch/+/state", discover_switch)
    await mqtt.async_subscribe(hass, f"{TOPIC_PREFIX}+/thermostat/+/modeState", discover_thermostat)
    _LOGGER.debug("Subscribed to MQTT topics for discovery")

    # Request device states on startup
    async def sync_device_states(event):
        await asyncio.sleep(1)
        for device_key, device_entry in hass.data[DOMAIN]["known_devices"].items():
            if isinstance(device_key, tuple) and len(device_key) == 2:
                device_type, device_id = device_key
                if device_type == "switch":
                    for switch_info in device_entry.values():
                        set_topic = switch_info["set_topic"]
                        await mqtt.async_publish(hass, set_topic, "OFF", qos=0, retain=False)
                elif device_type == "thermostat":
                    for thermostat_info in device_entry.values():
                        mode_set_topic = thermostat_info["mode_set_topic"]
                        await mqtt.async_publish(hass, mode_set_topic, "off", qos=0, retain=False)

    hass.bus.async_listen_once("homeassistant_started", sync_device_states)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "switch")
    unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(entry, "climate")
    if unload_ok:
        hass.data.pop(DOMAIN, None)
    return unload_ok
