"""Support for Renault switches."""

from __future__ import annotations

import logging
from typing import Any, override

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .ev_settings import DAYS_OF_WEEK_KEYS, KamereonVehicleEvSettingsData
from .renault_vehicle import RenaultVehicleProxy

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault switches from config entry."""

    @callback
    def _async_add_vehicle(vehicle: RenaultVehicleProxy) -> None:
        if "ev_settings" in vehicle.coordinators:
            entities: list[SwitchEntity] = [
                RenaultDepartureProgramSwitchEntity(vehicle, slot_index)
                for slot_index in range(5)
            ]
            entities.extend(
                [
                    RenaultPreconditioningHeaterSwitchEntity(
                        vehicle,
                        key="preconditioning_heated_steering_wheel",
                        attr_key="preconditioningHeatedStrgWheel",
                        arg_key="heated_steering_wheel",
                        translation_key="preconditioning_heated_steering_wheel",
                    ),
                    RenaultPreconditioningHeaterSwitchEntity(
                        vehicle,
                        key="preconditioning_heated_left_seat",
                        attr_key="preconditioningHeatedLeftSeat",
                        arg_key="heated_left_seat",
                        translation_key="preconditioning_heated_left_seat",
                    ),
                    RenaultPreconditioningHeaterSwitchEntity(
                        vehicle,
                        key="preconditioning_heated_right_seat",
                        attr_key="preconditioningHeatedRightSeat",
                        arg_key="heated_right_seat",
                        translation_key="preconditioning_heated_right_seat",
                    ),
                ]
            )
            async_add_entities(entities)

    config_entry.async_on_unload(
        config_entry.runtime_data.async_add_vehicle_listener(_async_add_vehicle)
    )


class RenaultDepartureProgramSwitchEntity(
    RenaultDataEntity[KamereonVehicleEvSettingsData], SwitchEntity
):
    """Switch entity to enable/disable a specific weekly departure program (1..5)."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, vehicle: RenaultVehicleProxy, slot_index: int) -> None:
        """Initialize departure program switch."""
        self.slot_index = slot_index
        description = RenaultDataEntityDescription(
            key=f"departure_program_{slot_index + 1}",
            coordinator="ev_settings",
            translation_key=f"departure_program_{slot_index + 1}",
        )
        super().__init__(vehicle, description)

    @property
    @override
    def is_on(self) -> bool:
        """Return True if departure program is activated."""
        if not self.coordinator.data or not self.coordinator.data.programs:
            return False
        if self.slot_index < len(self.coordinator.data.programs):
            prog = self.coordinator.data.programs[self.slot_index]
            return bool(prog.get("programActivationStatus", False))
        return False

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return departure program details as state attributes."""
        attrs: dict[str, Any] = {"program_slot": self.slot_index + 1}
        if (
            not self.coordinator.data
            or not self.coordinator.data.programs
            or self.slot_index >= len(self.coordinator.data.programs)
        ):
            attrs["configured"] = False
            return attrs

        prog = self.coordinator.data.programs[self.slot_index]
        attrs["configured"] = True
        attrs["departure_time"] = prog.get("programDepartureTime")
        attrs["program_type"] = prog.get("programType")
        attrs["active_days"] = [
            day_name
            for day_name, api_key in DAYS_OF_WEEK_KEYS
            if prog.get(api_key)
        ]
        return attrs

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the departure program."""
        ev_settings = await self.vehicle.get_ev_settings()
        programs = [dict(p) for p in (ev_settings.programs or [])]
        while len(programs) <= self.slot_index:
            programs.append(
                {
                    "programActivationStatus": False,
                    "programType": "PRECONDITIONING",
                    "programDepartureTime": "07:30",
                    "programActivationMonday": True,
                    "programActivationTuesday": True,
                    "programActivationWednesday": True,
                    "programActivationThursday": True,
                    "programActivationFriday": True,
                    "programActivationSaturday": False,
                    "programActivationSunday": False,
                }
            )
        programs[self.slot_index]["programActivationStatus"] = True
        payload = ev_settings.to_post_body(programs=programs)
        await self.vehicle.set_ev_settings(payload)
        self.coordinator.assumed_state = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the departure program."""
        ev_settings = await self.vehicle.get_ev_settings()
        programs = [dict(p) for p in (ev_settings.programs or [])]
        if self.slot_index < len(programs):
            programs[self.slot_index]["programActivationStatus"] = False
            payload = ev_settings.to_post_body(programs=programs)
            await self.vehicle.set_ev_settings(payload)
            self.coordinator.assumed_state = True
            self.async_write_ha_state()


class RenaultPreconditioningHeaterSwitchEntity(
    RenaultDataEntity[KamereonVehicleEvSettingsData], SwitchEntity
):
    """Switch entity for preconditioning seat & steering wheel heaters."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        vehicle: RenaultVehicleProxy,
        key: str,
        attr_key: str,
        arg_key: str,
        translation_key: str,
    ) -> None:
        """Initialize heater switch."""
        self.attr_key = attr_key
        self.arg_key = arg_key
        description = RenaultDataEntityDescription(
            key=key,
            coordinator="ev_settings",
            translation_key=translation_key,
        )
        super().__init__(vehicle, description)

    @property
    @override
    def is_on(self) -> bool:
        """Return True if heater is enabled for preconditioning."""
        if not self.coordinator.data:
            return False
        return bool(getattr(self.coordinator.data, self.attr_key, False))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable heater for preconditioning."""
        await self._set_heater_state(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable heater for preconditioning."""
        await self._set_heater_state(False)

    async def _set_heater_state(self, state: bool) -> None:
        """Update heater flag in KCM ev/settings."""
        ev_settings = await self.vehicle.get_ev_settings()
        kwargs = {self.arg_key: state}
        payload = ev_settings.to_post_body(**kwargs)
        await self.vehicle.set_ev_settings(payload)
        setattr(self.coordinator.data, self.attr_key, state)
        self.coordinator.assumed_state = True
        self.async_write_ha_state()
