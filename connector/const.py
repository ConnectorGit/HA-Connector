"""Constants for the Connector integration."""
from homeassistant.const import Platform

DOMAIN = "connector"
DEFAULT_HUB_NAME = "Connector Hub"
MANUFACTURER = "Connector Shades"
DEFAULT_GATEWAY_NAME = "Connector Shades"

PLATFORMS = [Platform.COVER]

CONF_WAIT_FOR_PUSH = "wait_for_push"
CONF_INTERFACE = "interface"
DEFAULT_WAIT_FOR_PUSH = False
DEFAULT_INTERFACE = "any"

KEY_GATEWAY = "gateway"
KEY_API_LOCK = "api_lock"
KEY_COORDINATOR = "coordinator"
KEY_MULTICAST_LISTENER = "multicast_listener"
KEY_SETUP_LOCK = "setup_lock"
KEY_UNSUB_STOP = "unsub_stop"
KEY_VERSION = "version"

ATTR_WIDTH = "width"
ATTR_ABSOLUTE_POSITION = "absolute_position"
ATTR_AVAILABLE = "available"

SERVICE_SET_ABSOLUTE_POSITION = "set_absolute_position"
