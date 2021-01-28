"""The connector integration."""
import asyncio
from datetime import timedelta

import time
import voluptuous as vol
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .connectorLocalControl import ConnectorHub
from homeassistant.const import CONF_API_KEY, CONF_HOST, EVENT_HOMEASSISTANT_STOP
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
    time.sleep(5)
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]
    connector = connectorLocalControl.ConnectorHub(ip=host, key=key)

    if KEY_MULTICAST_LISTENER not in hass.data[DOMAIN]:
        connector.start_receive_data()
        multicast = connector
        hass.data[DOMAIN][KEY_MULTICAST_LISTENER] = multicast

        # register stop callback to shutdown listening for local pushes
        def stop_motion_multicast(event):
            """Stop multicast thread."""
            _LOGGER.debug("Shutting down Connector Listener")
            multicast.close_receive_data()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_motion_multicast)

    def update_gateway():
        """Call all updates using one async_add_executor_job."""
        for device in connector.deviceList.values():
            try:
                device.updateBlinds()
            except timeout:
                pass

    async def async_update_data():
        """Fetch data from the gateway and blinds."""
        try:
            await hass.async_add_executor_job(update_gateway)
        except timeout:
            pass

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_GATEWAY: connector,
        KEY_COORDINATOR: coordinator,
    }

    device_registry = await dr.async_get_registry(hass)
    for hub in connector.deviceList.values():
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
        await hass.async_add_executor_job(multicast.close_receive_data)
    return unload_ok
