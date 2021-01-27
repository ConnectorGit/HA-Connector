"""Config flow for connector integration."""
import logging

import voluptuous as vol
from .connectorLocalControl import ConnectorHub
from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_API_KEY
from .const import DOMAIN, DEFAULT_HUB_NAME  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema({"CONF_HOST": str, "CONF_KEY": str})


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=16, max=16)),
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host):
        """Initialize."""
        self.host = host

    async def authenticate(self, username, password) -> bool:
        """Test if we can authenticate with the host."""
        return True


# async def validate_input(hass: core.HomeAssistant, data):
#     """Validate the user input allows us to connect.
#
#     Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
#     """
# TODO validate the data can be used to set up a connection.
#
#     # If your PyPI package is not built with async, pass your methods
#     # to the executor:
#     # await hass.async_add_executor_job(
#     #     your_validate_func, data["username"], data["password"]
#     # )
#
#     hub = PlaceholderHub(data["host"])
#
#     if not await hub.authenticate(data["username"], data["password"]):
#         raise InvalidAuth
#
#     # If you cannot connect:
#     # throw CannotConnect
#     # If the authentication is wrong:
#     # InvalidAuth
#
#     # Return info that you want to store in the config entry.
#     return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for connector."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    def __init__(self):
        """Initialize the connector hub"""
        self.host = None
        self.key = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST].split("&")
            self.key = user_input[CONF_API_KEY]
            _LOGGER.info("host:", self.host)
            _LOGGER.info("key:", self.key)
            return await self.async_step_connect()

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_connect(self, user_input=None):
        """Connect to the Connector Hub"""
        await self.async_set_unique_id("ConnectorLocalControlID")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_HUB_NAME,
            data={CONF_HOST: self.host, CONF_API_KEY: self.key},
        )

