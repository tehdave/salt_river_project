"""docstring."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .data_coordinator import SaltRiverProject_DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Salt River Project Energy sensors from a config entry."""
    coordinator: SaltRiverProject_DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SaltRiverProjectEnergySensor(coordinator, entry, "total_kwh", "Total Usage", "total_kwh"),
        SaltRiverProjectEnergySensor(coordinator, entry, "on_peak_usage", "On Peak Usage", "on_peak_kwh_total"),
        SaltRiverProjectEnergySensor(coordinator, entry, "off_peak_usage", "Off Peak Usage", "off_peak_kwh_total"),
        SaltRiverProjectEnergySensor(coordinator, entry, "shoulder_usage", "Shoulder Usage", "shoulder_kwh_total"),
        SaltRiverProjectEnergySensor(coordinator, entry, "super_off_peak_usage", "Super Off Peak Usage", "super_off_peak_kwh_total"),
    ]

    async_add_entities(sensors, update_before_add=True)

class SaltRiverProjectEnergySensor(CoordinatorEntity[SaltRiverProject_DataUpdateCoordinator], SensorEntity):
    """Representation of a Salt River Project Energy sensor."""

    def __init__(self, coordinator: SaltRiverProject_DataUpdateCoordinator, entry: ConfigEntry, id: str, name: str, data_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{id}"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL
        self.entity_id = f"sensor.{DOMAIN}_{id}"
        self._data_key = data_key

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._data_key)
