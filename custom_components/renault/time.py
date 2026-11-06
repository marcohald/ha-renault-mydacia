"""Support for Renault time entities."""

from __future__ import annotations

from datetime import time as dt_time
import logging
from typing import override

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .ev_settings import KamereonVehicleEvSettingsData
from .renault_vehicle import RenaultVehicleProxy

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault time entities from config entry."""

    @callback
    def _async_add_vehicle(vehicle: RenaultVehicleProxy) -> None:
        if "ev_settings" in vehicle.coordinators:
            async_add_entities([RenaultChargeStartTimeEntity(vehicle)])

    config_entry.async_on_unload(
        config_entry.runtime_data.async_add_vehicle_listener(_async_add_vehicle)
    )


class RenaultChargeStartTimeEntity(
    RenaultDataEntity[KamereonVehicleEvSettingsData], TimeEntity
):
    """Entity to view and set the scheduled charge start time."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "charge_time_start"

    def __init__(self, vehicle: RenaultVehicleProxy) -> None:
        """Initialize charge start time entity."""
        description = RenaultDataEntityDescription(
            key="charge_time_start",
            coordinator="ev_settings",
        )
        super().__init__(vehicle, description)

    @property
    @override
    def native_value(self) -> dt_time | None:
        """Return the scheduled charge start time."""
        if not self.coordinator.data or not self.coordinator.data.chargeTimeStart:
            return None
        raw = str(self.coordinator.data.chargeTimeStart).strip()
        try:
            parts = raw.split(":")
            return dt_time(hour=int(parts[0]), minute=int(parts[1]))
        except (ValueError, IndexError):
            _LOGGER.warning("Invalid chargeTimeStart format: %r", raw)
            return None

    @override
    async def async_set_value(self, value: dt_time) -> None:
        """Set a new scheduled charge start time."""
        formatted_time = f"{value.hour:02d}:{value.minute:02d}"
        ev_settings = await self.vehicle.get_ev_settings()
        payload = ev_settings.to_post_body(charge_time_start=formatted_time)
        await self.vehicle.set_ev_settings(payload)
        self.coordinator.data.chargeTimeStart = formatted_time
        self.coordinator.assumed_state = True
        self.async_write_ha_state()
