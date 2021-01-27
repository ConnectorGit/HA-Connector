"""The connector integration."""
import asyncio
from datetime import timedelta

import voluptuous as vol
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .connectorLocalControl import ConnectorHub
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry as dr

from socket import timeout


from .const import DOMAIN, KEY_GATEWAY, KEY_COORDINATOR, MANUFACTURER, KEY_MULTICAST_LISTENER
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["cover"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the connector component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up connector from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]
    hub = connectorLocalControl.ConnectorHub(ip=host, key=key)
    hub.start_receive_data()
    hubs = hub.deviceList

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=entry.title,
        # update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=600),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_GATEWAY: hubs,
        KEY_COORDINATOR: coordinator,
    }

    device_registry = await dr.async_get_registry(hass)
    for hub in hubs.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, hub.hub_mac)},
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer=MANUFACTURER,
            name=entry.title,
            model="Wi-Fi bridge",
            sw_version=hub.hub_version,
        )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) == 1:
        _LOGGER.debug("Shutting down Connector Listener")
        multicast = hass.data[DOMAIN].pop(KEY_MULTICAST_LISTENER)
        await hass.async_add_executor_job(multicast.Stop_listen)

    return unload_ok
