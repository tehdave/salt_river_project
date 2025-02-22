"""The salt_river_project integration."""

from __future__ import annotations

from saltriverprojectenergyapi import SaltRiverProjectClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_BILLING_ACCOUNT, DOMAIN
from .data_coordinator import SaltRiverProject_DataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type SaltRiverProject_ConfigEntry = ConfigEntry[SaltRiverProjectClient]


async def async_setup_entry(hass: HomeAssistant, entry: SaltRiverProject_ConfigEntry) -> bool:
    """Set up salt_river_project from a config entry."""
    salt_river_project_client = SaltRiverProjectClient(
        billing_account=entry.data[CONF_BILLING_ACCOUNT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    # Create our DataCoordinator
    coordinator = SaltRiverProject_DataUpdateCoordinator(hass, salt_river_project_client, entry)

    # Store the coordinator for your platforms to access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the specified platforms
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SaltRiverProject_ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
