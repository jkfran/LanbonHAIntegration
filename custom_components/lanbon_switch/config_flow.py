from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN

class LanbonSwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Lanbon Switch integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            # Validate user input or perform setup actions here if needed
            return self.async_create_entry(title="Lanbon Switch", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=None,  # Replace `None` with a schema if you need user input
        )
