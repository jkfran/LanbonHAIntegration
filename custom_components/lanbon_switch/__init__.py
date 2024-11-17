import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import mqtt
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store

from .const import DOMAIN, TOPIC_PREFIX, SWITCH_SUBTOPIC, STATE_SUBTOPIC, SET_SUBTOPIC

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_devices"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from YAML."""
    hass.data.setdefault(DOMAIN, {
        "entities": {},
        "set_topics": set(),
        "known_devices": {},
        "platform_switch_setup_done": False,  # Track switch platform setup
    })
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a ConfigEntry (UI-based setup)."""
    hass.data.setdefault(DOMAIN, {
        "entities": {},
        "set_topics": set(),
        "known_devices": {},
        "platform_switch_setup_done": False,  # Track switch platform setup
    })

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    # Load known devices from storage
    stored_data = await store.async_load()
    if stored_data:
        hass.data[DOMAIN]["known_devices"] = stored_data.get("devices", {})
        hass.data[DOMAIN]["set_topics"] = set(stored_data.get("set_topics", []))
    else:
        hass.data[DOMAIN]["known_devices"] = {}
        hass.data[DOMAIN]["set_topics"] = set()

    # Re-register entities from known devices
    for device_id, switches in hass.data[DOMAIN]["known_devices"].items():
        for switch_id in switches:
            entity_id = f"{device_id}_{switch_id}"
            if entity_id not in hass.data[DOMAIN]["entities"]:
                hass.data[DOMAIN]["entities"][entity_id] = True

    async def discover_device(msg):
        topic = msg.topic
        payload = msg.payload

        # Expected topic: homeassistant/<device_id>/switch/<switch_id>/state
        parts = topic.split('/')
        if len(parts) != 5:
            return

        _, device_id_raw, switch_subtopic, switch_id_raw, state_subtopic = parts
        if switch_subtopic != SWITCH_SUBTOPIC or state_subtopic != STATE_SUBTOPIC:
            return

        # Normalize IDs
        device_id = device_id_raw.lower()
        switch_id = switch_id_raw.lower()

        entity_id = f"{device_id}_{switch_id}"

        if entity_id in hass.data[DOMAIN]["entities"]:
            return

        # Store the set topic for synchronization
        set_topic = f"{TOPIC_PREFIX}{device_id_raw}/{SWITCH_SUBTOPIC}/{switch_id_raw}/{SET_SUBTOPIC}"
        hass.data[DOMAIN]["set_topics"].add(set_topic)

        # Update known devices
        device_entry = hass.data[DOMAIN]["known_devices"].setdefault(device_id, {})
        device_entry[switch_id] = {
            "device_id_raw": device_id_raw,
            "switch_id_raw": switch_id_raw,
            "set_topic": set_topic,
        }

        # Save known devices to storage
        await store.async_save({
            "devices": hass.data[DOMAIN]["known_devices"],
            "set_topics": list(hass.data[DOMAIN]["set_topics"]),
        })

        hass.data[DOMAIN]["entities"][entity_id] = True

        # Forward setup only if not already done
        if not hass.data[DOMAIN]["platform_switch_setup_done"]:
            hass.data[DOMAIN]["platform_switch_setup_done"] = True
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, "switch")
            )

    # Request device states on startup
    async def sync_device_states(event):
        await asyncio.sleep(1)
        for device_entry in hass.data[DOMAIN]["known_devices"].values():
            for switch_info in device_entry.values():
                set_topic = switch_info["set_topic"]
                if "--" in set_topic:
                    continue
                await mqtt.async_publish(
                    hass,
                    set_topic,
                    "OFF",
                    qos=0,
                    retain=False
                )

    # Subscribe to state topics for discovery
    await mqtt.async_subscribe(hass, f"{TOPIC_PREFIX}+/switch/+/state", discover_device)

    # Register the `sync_device_states` function
    hass.bus.async_listen_once("homeassistant_started", sync_device_states)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    # Unload the switch platform if it was loaded
    if hass.data[DOMAIN]["platform_switch_setup_done"]:
        unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "switch")
        if unload_ok:
            hass.data[DOMAIN]["platform_switch_setup_done"] = False
    else:
        unload_ok = True

    # Clear integration data
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok
