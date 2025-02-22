"""DocString."""
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
import logging

from saltriverprojectenergyapi import SaltRiverProjectClient

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

@dataclass
class UsageData:
    """Class for holding the usage data in an expanded form."""

    on_date: datetime
    on_peak_kwh: float
    off_peak_kwh: float
    shoulder_kwh: float
    super_off_peak_kwh: float

    def get(self, property_name: str) -> any:
        """Get a property value by name."""
        return getattr(self, property_name)

    @classmethod
    def parse_data_from_api(cls, data) -> list["UsageData"]:
        """Create an instance of UsageData from the API Response data."""
        if not data or len(data) < 1:
            raise ValueError("API Response can not be parsed.")

        statistics_data = []

        for hourly_data in data:
            # Ensure that datetime strings are parsed into datetime objects
            data_date: datetime = datetime.strptime(hourly_data.date, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
            energy_data = hourly_data.kwh_data
            #cost_data = hourly_data.cost_data
            statistics_data.append(
                UsageData(
                    on_date=data_date,
                    on_peak_kwh=energy_data.on_peak_kwh,
                    off_peak_kwh=energy_data.off_peak_kwh,
                    shoulder_kwh=energy_data.shoulder_kwh,
                    super_off_peak_kwh=energy_data.super_off_peak_kwh,
                )
            )

        return statistics_data

class SaltRiverProject_DataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Salt River Project Client."""

    def __init__(self, hass: HomeAssistant, client: SaltRiverProjectClient, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        self._client:SaltRiverProjectClient = client
        self._entry:ConfigEntry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=CONF_DEVICE_NAME,
            update_interval=None
        )
        self._schedule_first_run() # This will schedule the first timed run for 0030 hrs.
        # But run right now anyway, to get some data.
        self.hass.async_create_task(self._async_update_data())

    def _schedule_first_run(self):
        """Schedule the first run of the update at 30 minutes after midnight."""
        now = datetime.now()
        target_time = datetime.combine(now.date(), time(0, 30))
        if now > target_time:
            target_time += timedelta(days=1)

        async_track_point_in_time(self.hass, self._schedule_subsequent_runs, target_time)

    @callback
    def _schedule_subsequent_runs(self, _):
        """Schedule subsequent runs at 24-hour intervals."""
        async_track_time_interval(self.hass, self._async_update_data, timedelta(days=1))
        self.hass.async_create_task(self._async_update_data())

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            # Calculate start and end dates.
            end_date = datetime.now() - timedelta(days=1)
            start_date = end_date - timedelta(days=1)

            # Format the dates as strings in dd-mm-yyyy format
            start_date_str = start_date.strftime("%d-%m-%Y")
            end_date_str = end_date.strftime("%d-%m-%Y")

            energy_usage_data = await self.hass.async_add_executor_job(
                self._client.get_hourly_usage,
                start_date_str,
                end_date_str
            )

            # Calculate the total kwh and cost
            on_peak_kwh_total = sum(usage.kwh_data.on_peak_kwh for usage in energy_usage_data.energy_usage)
            off_peak_kwh_total = sum(usage.kwh_data.off_peak_kwh for usage in energy_usage_data.energy_usage)
            shoulder_kwh_total = sum(usage.kwh_data.shoulder_kwh for usage in energy_usage_data.energy_usage)
            super_off_peak_kwh_total = sum(usage.kwh_data.super_off_peak_kwh for usage in energy_usage_data.energy_usage)

            on_peak_cost_total = sum(usage.cost_data.on_peak_cost for usage in energy_usage_data.energy_usage)
            off_peak_cost_total = sum(usage.cost_data.off_peak_cost for usage in energy_usage_data.energy_usage)
            shoulder_cost_total = sum(usage.cost_data.shoulder_cost for usage in energy_usage_data.energy_usage)
            super_off_peak_cost_total = sum(usage.cost_data.super_off_peak_cost for usage in energy_usage_data.energy_usage)

            # Instead of using the total_kwh stored in the data object, let's calculate it.
            total_kwh = on_peak_kwh_total + off_peak_kwh_total + shoulder_kwh_total + super_off_peak_kwh_total
            # Instead of using the total_cost stored in the data object, let's calculate it.
            total_cost = on_peak_cost_total + off_peak_cost_total + shoulder_cost_total + super_off_peak_cost_total

            # Return the calculated totals. This will be the total for ALL data returned between the start and end dates.
            result = {
                "on_peak_kwh_total": on_peak_kwh_total,
                "off_peak_kwh_total": off_peak_kwh_total,
                "shoulder_kwh_total": shoulder_kwh_total,
                "super_off_peak_kwh_total": super_off_peak_kwh_total,
                "on_peak_cost_total": on_peak_cost_total,
                "off_peak_cost_total": off_peak_cost_total,
                "shoulder_cost_total": shoulder_cost_total,
                "super_off_peak_cost_total": super_off_peak_cost_total,
                "total_kwh": total_kwh,
                "total_cost": total_cost,
                "timestamp": end_date
            }

            # Save this data to the statistics.
            hourly_usage_data = UsageData.parse_data_from_api(energy_usage_data.energy_usage)

            await self._update_statistics(hourly_usage_data)

        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        else:
            return result

    async def _update_statistics(self, usage_data: list[UsageData]) -> None:
        """Insert energy usage statistics."""
        _LOGGER.debug("We are going to set statistics for the data passed in as a list")
        if not usage_data:
            _LOGGER.debug("No valid data to process")
            return

        on_peak_kwh_statistic = []
        off_peak_kwh_statistic = []
        shoulder_kwh_statistic = []
        super_off_peak_kwh_statistic = []

        on_peak_kwh_statistic_sum = 0
        off_peak_kwh_statistic_sum = 0
        shoulder_kwh_statistic_sum = 0
        super_off_peak_kwh_statistic_sum = 0

        on_peak_kwh_statistic_id = f"{DOMAIN}:salt_river_project_on_peak_usage"
        off_peak_kwh_statistic_id = f"{DOMAIN}:salt_river_project_off_peak_usage"
        shoulder_kwh_statistic_id = f"{DOMAIN}:salt_river_project_shoulder_usage"
        super_off_peak_kwh_statistic_id = f"{DOMAIN}:salt_river_project_super_off_peak_usage"

        for usage_data_record in usage_data:
            start = usage_data_record.on_date
            on_peak_kwh_statistic_sum += usage_data_record.on_peak_kwh
            off_peak_kwh_statistic_sum += usage_data_record.off_peak_kwh
            shoulder_kwh_statistic_sum += usage_data_record.shoulder_kwh
            super_off_peak_kwh_statistic_sum += usage_data_record.super_off_peak_kwh

            on_peak_kwh_statistic.append(
                StatisticData(
                    start=start,
                    state=usage_data_record.on_peak_kwh,
                    sum=on_peak_kwh_statistic_sum
                )
            )

            off_peak_kwh_statistic.append(
                StatisticData(
                    start=start,
                    state=usage_data_record.off_peak_kwh,
                    sum=off_peak_kwh_statistic_sum
                )
            )

            shoulder_kwh_statistic.append(
                StatisticData(
                    start=start,
                    state=usage_data_record.shoulder_kwh,
                    sum=shoulder_kwh_statistic_sum
                )
            )

            super_off_peak_kwh_statistic.append(
                StatisticData(
                    start=start,
                    state=usage_data_record.super_off_peak_kwh,
                    sum=super_off_peak_kwh_statistic_sum
                )
            )

        on_peak_kwh_metadata = StatisticMetaData(
            statistic_id=on_peak_kwh_statistic_id,
            name="On Peak Usage",
            has_mean=False,
            has_sum=True,
            source=DOMAIN,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        off_peak_kwh_metadata = StatisticMetaData(
            statistic_id=off_peak_kwh_statistic_id,
            name="Off Peak Usage",
            has_mean=False,
            has_sum=True,
            source=DOMAIN,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        shoulder_kwh_metadata = StatisticMetaData(
            statistic_id=shoulder_kwh_statistic_id,
            name="Shoulder Usage",
            has_mean=False,
            has_sum=True,
            source=DOMAIN,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        super_off_peak_kwh_metadata = StatisticMetaData(
            statistic_id=super_off_peak_kwh_statistic_id,
            name="Super Off Peak Usage",
            has_mean=False,
            has_sum=True,
            source=DOMAIN,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        if on_peak_kwh_statistic:
            _LOGGER.debug("Adding Statistics Data: %i records to statistics\n", len(on_peak_kwh_statistic))
            async_add_external_statistics(self.hass, on_peak_kwh_metadata, on_peak_kwh_statistic)
        if off_peak_kwh_statistic:
            _LOGGER.debug("Adding Statistics Data: %i records to statistics\n", len(off_peak_kwh_statistic))
            async_add_external_statistics(self.hass, off_peak_kwh_metadata, off_peak_kwh_statistic)
        if shoulder_kwh_statistic:
            _LOGGER.debug("Adding Statistics Data: %i records to statistics\n", len(shoulder_kwh_statistic))
            async_add_external_statistics(self.hass, shoulder_kwh_metadata, shoulder_kwh_statistic)
        if super_off_peak_kwh_statistic:
            _LOGGER.debug("Adding Statistics Data: %i records to statistics\n", len(super_off_peak_kwh_statistic))
            async_add_external_statistics(self.hass, super_off_peak_kwh_metadata, super_off_peak_kwh_statistic)
