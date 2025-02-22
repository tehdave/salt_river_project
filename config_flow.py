"""Config flow for the salt_river_project_energy integration."""

from __future__ import annotations

import logging
from typing import Any

from saltriverprojectenergyapi import SaltRiverProjectClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_BILLING_ACCOUNT, CONF_DEFAULT_NAME, CONF_DEVICE_NAME, DOMAIN
from .data_coordinator import SaltRiverProject_DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_NAME, default=CONF_DEFAULT_NAME
        ): str,
        vol.Required(CONF_BILLING_ACCOUNT): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = SaltRiverProjectClient(
        billing_account=data[CONF_BILLING_ACCOUNT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD]
    )

    if not await hass.async_add_executor_job(api.is_authorised):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect

    # Create the coordinator for validation
    coordinator = SaltRiverProject_DataUpdateCoordinator(hass, api, None)
    await coordinator.async_config_entry_first_refresh()

    # Return info that you want to store in the config entry.
    return {"title": CONF_DEVICE_NAME}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for salt_river_project."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
