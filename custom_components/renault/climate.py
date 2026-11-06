"""Support for Renault / My Dacia climate entity."""

from __future__ import annotations

import logging
from typing import Any, override

from renault_api.kamereon.models import KamereonVehicleHvacStatusData

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .renault_vehicle import RenaultVehicleProxy

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault climate entities from config entry."""

    @callback
    def _async_add_vehicle(vehicle: RenaultVehicleProxy) -> None:
        if "hvac_status" in vehicle.coordinators:
            async_add_entities([RenaultClimateEntity(vehicle)])

    config_entry.async_on_unload(
        config_entry.runtime_data.async_add_vehicle_listener(_async_add_vehicle)
    )


class RenaultClimateEntity(
    RenaultDataEntity[KamereonVehicleHvacStatusData], ClimateEntity
):
    """Climate entity for Renault / My Dacia preconditioning."""

    _enable_turn_on_off_backwards_compatibility = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16.0
    _attr_max_temp = 28.0
    _attr_translation_key = "preconditioning"

    def __init__(self, vehicle: RenaultVehicleProxy) -> None:
        """Initialize the climate entity."""
        description = RenaultDataEntityDescription(
            key="climate",
            coordinator="hvac_status",
        )
        super().__init__(vehicle, description)
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
        )
        if vehicle.details.supports_endpoint("actions/hvac-stop"):
            features |= ClimateEntityFeature.TURN_OFF
        self._attr_supported_features = features

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks when added to hass."""
        await super().async_added_to_hass()
        if "ev_settings" in self.vehicle.coordinators:
            self.async_on_remove(
                self.vehicle.coordinators["ev_settings"].async_add_listener(
                    self.async_write_ha_state
                )
            )

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current inside temperature."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.internalTemperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the target preconditioning temperature."""
        if "ev_settings" in self.vehicle.coordinators:
            ev_coord = self.vehicle.coordinators["ev_settings"]
            if ev_coord.data and ev_coord.data.preconditioningTemperature is not None:
                return float(ev_coord.data.preconditioningTemperature)
        return float(self.vehicle.hvac_target_temperature)

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self.coordinator.data:
            return HVACMode.OFF
        status = (self.coordinator.data.hvacStatus or "").lower()
        if status in ("on", "running", "active", "true"):
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    @override
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        cur = self.current_temperature
        tgt = self.target_temperature
        if cur is not None and tgt is not None:
            if cur < tgt:
                return HVACAction.HEATING
            if cur > tgt:
                return HVACAction.COOLING
        return HVACAction.HEATING

    @override
    async def async_turn_on(self) -> None:
        """Turn on preconditioning."""
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    @override
    async def async_turn_off(self) -> None:
        """Turn off preconditioning."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.vehicle.set_ac_stop()
            if self.coordinator.data:
                self.coordinator.data.hvacStatus = "off"
                self.coordinator.assumed_state = True
                self.coordinator.async_set_updated_data(self.coordinator.data)
            else:
                await self.coordinator.async_request_refresh()
        elif hvac_mode in (HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL):
            tgt = self.target_temperature or 21.0
            await self.vehicle.set_ac_start(tgt)
            if self.coordinator.data:
                self.coordinator.data.hvacStatus = "on"
                self.coordinator.assumed_state = True
                self.coordinator.async_set_updated_data(self.coordinator.data)
            else:
                await self.coordinator.async_request_refresh()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        temp_val = float(temp)
        self.vehicle.hvac_target_temperature = temp_val

        # If vehicle supports KCM /ev/settings, update the vehicle setting
        if self.vehicle.uses_kcm_ev_settings():
            try:
                ev_settings = await self.vehicle.get_ev_settings()
                payload = ev_settings.to_post_body(
                    preconditioning_temperature=temp_val
                )
                await self.vehicle.set_ev_settings(payload)
            except Exception as ex:
                _LOGGER.warning(
                    "Failed to update preconditioningTemperature in ev/settings: %s",
                    ex,
                )

        # If HVAC is currently running, apply new temperature immediately
        if self.hvac_mode != HVACMode.OFF:
            await self.vehicle.set_ac_start(temp_val)

        self.async_write_ha_state()
