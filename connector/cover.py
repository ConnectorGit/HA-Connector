"""Support for Motion Blinds using their WLAN API."""

import logging
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_SHADE,
    DEVICE_CLASS_SHUTTER,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .connectorLocalControl import one_way_wirelessMode, two_way_wirelessMode

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Motion Blind from a config entry."""
    entities = []
    connector = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for hub in connector.deviceList.values():
        for blind in hub.blinds.values():
            if blind.wirelessMode in one_way_wirelessMode:
                entities.append(
                    OneWayDevice(
                        coordinator=coordinator, blind=blind, device_class=DEVICE_CLASS_SHADE,
                        config_entry=config_entry
                    )
                )
            elif blind.wirelessMode in two_way_wirelessMode:
                if blind.type == 2:
                    entities.append(
                        TiltDevice(
                            coordinator=coordinator, blind=blind, device_class=DEVICE_CLASS_SHUTTER,
                            config_entry=config_entry
                        )
                    )
                else:
                    entities.append(
                        TwoWayDevice(
                            coordinator=coordinator, blind=blind, device_class=DEVICE_CLASS_SHADE,
                            config_entry=config_entry
                        )
                    )
            else:
                _LOGGER.warning("this wirelessMode not support")

    async_add_entities(entities)


class TwoWayDevice(CoordinatorEntity, CoverEntity):
    """Representation of a Motion Blind Device."""

    def __init__(self, coordinator, blind, device_class, config_entry):
        """Initialize the blind."""
        super().__init__(coordinator)

        self._blind = blind
        self._device_class = device_class
        self._config_entry = config_entry

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return self._blind.mac

    @property
    def device_info(self):
        """Return the device info of the blind."""
        device_info = {
            "identifiers": {(DOMAIN, self._blind.mac)},
            "manufacturer": MANUFACTURER,
            "name": f"{self._blind.mac}",
            "model": "Curtain",
            "via_device": (DOMAIN, self._config_entry.unique_id),
        }

        return device_info

    @property
    def name(self):
        """Return the name of the blind."""
        return f"{self._blind.mac[12:]}"

    @property
    def available(self):
        """Return True if entity is available."""
        return True

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._blind.position == 100

    @callback
    def _push_callback(self):
        """Update entity state when a push has been received."""
        self.schedule_update_ha_state(force_refresh=False)

    async def async_added_to_hass(self):
        """Subscribe to multicast pushes."""
        self._blind.registerCallback(self._push_callback)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._blind.removeCallback()
        return super().async_will_remove_from_hass()

    @property
    def current_cover_position(self):
        """return the current position"""
        return 100 - self._blind.position

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._blind.TargetPosition(100-position)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class TiltDevice(TwoWayDevice):
    """Representation of a Motion Blind Device."""

    @property
    def current_cover_tilt_position(self):
        """
        Return current angle of cover.
        None is unknown, 0 is closed/minimum tilt, 100 is fully open/maximum tilt.
        """
        if self._blind.angle is None:
            return None
        return self._blind.angle * 100 / 180

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._blind.TargetAngle(180)

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._blind.TargetAngle(0)

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
        self._blind.TargetAngle(angle)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class OneWayDevice(CoordinatorEntity, CoverEntity):
    """Representation of a Motion Blind Device."""

    def __init__(self, coordinator, blind, device_class, config_entry):
        """Initialize the blind."""
        super().__init__(coordinator)

        self._blind = blind
        self._device_class = device_class
        self._config_entry = config_entry

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return self._blind.mac

    @property
    def device_info(self):
        """Return the device info of the blind."""
        device_info = {
            "identifiers": {(DOMAIN, self._blind.mac)},
            "manufacturer": MANUFACTURER,
            "name": f"{self._blind.mac}",
            "model": "Curtain",
            "via_device": (DOMAIN, self._config_entry.unique_id),
        }

        return device_info

    @property
    def name(self):
        """Return the name of the blind."""
        return f"{self._blind.mac[12:]}"

    @property
    def available(self):
        """Return True if entity is available."""
        return True

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        # return self._blind.position == 100
        return True

    @callback
    def _push_callback(self):
        """Update entity state when a push has been received."""
        self.schedule_update_ha_state(force_refresh=False)

    async def async_added_to_hass(self):
        """Subscribe to multicast pushes."""
        self._blind.registerCallback(self._push_callback)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._blind.removeCallback()
        return super().async_will_remove_from_hass()

    @property
    def current_cover_position(self):
        """return the current position"""
        return 50

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()
