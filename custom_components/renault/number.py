"""Support for Renault number entities."""
from __future__ import annotations

from typing import Generic, TypeVar, Any
T = TypeVar('T', bound=Any)


from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from renault_api.kamereon.models import (
    KamereonVehicleBatterySocData,
    KamereonVehicleDataAttributes,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .const import DOMAIN
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .ev_settings import KamereonVehicleEvSettingsData
from .renault_vehicle import RenaultVehicleProxy

# Coordinator is used to centralize the data updates
# but renault servers are unreliable and it's safer to queue action calls
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RenaultNumberEntityDescription(NumberEntityDescription, RenaultDataEntityDescription, Generic[T]):
    """Class describing Renault number entities."""

    value_fn: Callable[[RenaultNumberEntity[T]], float | None]
    update_fn: Callable[[RenaultNumberEntity[T], float], Coroutine[Any, Any, None]]


async def _set_charge_limit_min(
    entity: RenaultNumberEntity[KamereonVehicleBatterySocData], value: float
) -> None:
    """Set the minimum SOC.

    The target SOC is required to set the minimum SOC, so we need to fetch it first.
    """
    if (target_soc := entity.coordinator.data.socTarget) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="battery_soc_unavailable",
        )
    await _set_charge_limits(entity, min_soc=round(value), target_soc=target_soc)


async def _set_charge_limit_target(
    entity: RenaultNumberEntity[KamereonVehicleBatterySocData], value: float
) -> None:
    """Set the target SOC.

    The minimum SOC is required to set the target SOC, so we need to fetch it first.
    """
    if (min_soc := entity.coordinator.data.socMin) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="battery_soc_unavailable",
        )
    await _set_charge_limits(entity, min_soc=min_soc, target_soc=round(value))


async def _set_charge_limits(
    entity: RenaultNumberEntity[KamereonVehicleBatterySocData],
    min_soc: int,
    target_soc: int,
) -> None:
    """Set the minimum and target SOC.

    Optimistically update local coordinator data so the new
    limits are reflected immediately without a remote refresh,
    as Renault servers may still cache old values.
    """
    await entity.vehicle.set_battery_soc(min_soc=min_soc, target_soc=target_soc)

    entity.coordinator.data.socMin = min_soc
    entity.coordinator.data.socTarget = target_soc
    entity.coordinator.assumed_state = True
    entity.coordinator.async_set_updated_data(entity.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""

    @callback
    def _async_add_vehicle(vehicle: RenaultVehicleProxy) -> None:
        async_add_entities(
            RenaultNumberEntity(vehicle, description)
            for description in NUMBER_TYPES
            if description.coordinator in vehicle.coordinators
        )

    config_entry.async_on_unload(
        config_entry.runtime_data.async_add_vehicle_listener(_async_add_vehicle)
    )


class RenaultNumberEntity(RenaultDataEntity[T], NumberEntity, Generic[T]):
    """Mixin for number specific attributes."""

    entity_description: RenaultNumberEntityDescription[T]

    @property
    @override
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self.entity_description.value_fn(self)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.update_fn(self, value)


async def _set_preconditioning_temperature(
    entity: RenaultNumberEntity[KamereonVehicleEvSettingsData], value: float
) -> None:
    """Set the target preconditioning temperature in KCM ev/settings."""
    ev_settings = await entity.vehicle.get_ev_settings()
    payload = ev_settings.to_post_body(preconditioning_temperature=value)
    await entity.vehicle.set_ev_settings(payload)
    entity.vehicle.hvac_target_temperature = value
    entity.coordinator.data.preconditioningTemperature = value
    entity.coordinator.assumed_state = True
    entity.coordinator.async_set_updated_data(entity.coordinator.data)


async def _set_charge_duration(
    entity: RenaultNumberEntity[KamereonVehicleEvSettingsData], value: float
) -> None:
    """Set the scheduled charge duration in KCM ev/settings."""
    ev_settings = await entity.vehicle.get_ev_settings()
    payload = ev_settings.to_post_body(charge_duration=int(value))
    await entity.vehicle.set_ev_settings(payload)
    entity.coordinator.data.chargeDuration = int(value)
    entity.coordinator.assumed_state = True
    entity.coordinator.async_set_updated_data(entity.coordinator.data)


NUMBER_TYPES: tuple[RenaultNumberEntityDescription, ...] = (
    RenaultNumberEntityDescription[KamereonVehicleBatterySocData](
        key="charge_limit_min",
        entity_category=EntityCategory.CONFIG,
        coordinator="battery_soc",
        update_fn=_set_charge_limit_min,
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=15,
        native_max_value=45,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_min",
        value_fn=lambda entity: entity.coordinator.data.socMin,
    ),
    RenaultNumberEntityDescription[KamereonVehicleBatterySocData](
        key="charge_limit_target",
        entity_category=EntityCategory.CONFIG,
        coordinator="battery_soc",
        update_fn=_set_charge_limit_target,
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=55,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_target",
        value_fn=lambda entity: entity.coordinator.data.socTarget,
    ),
    RenaultNumberEntityDescription[KamereonVehicleEvSettingsData](
        key="preconditioning_temperature",
        entity_category=EntityCategory.CONFIG,
        coordinator="ev_settings",
        update_fn=_set_preconditioning_temperature,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=16.0,
        native_max_value=28.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        translation_key="preconditioning_temperature",
        value_fn=lambda entity: entity.coordinator.data.preconditioningTemperature,
    ),
    RenaultNumberEntityDescription[KamereonVehicleEvSettingsData](
        key="charge_duration",
        entity_category=EntityCategory.CONFIG,
        coordinator="ev_settings",
        update_fn=_set_charge_duration,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=15,
        native_max_value=1440,
        native_step=15,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.SLIDER,
        translation_key="charge_duration",
        value_fn=lambda entity: entity.coordinator.data.chargeDuration,
    ),
)
