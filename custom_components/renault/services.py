"""Support for Renault services."""

from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_get_device_and_config_entry

from .const import DOMAIN
from .ev_settings import (
    hvac_schedules_to_ev_programs,
    normalize_ev_program,
)
from .renault_vehicle import RenaultVehicleProxy

if TYPE_CHECKING:
    from . import RenaultConfigEntry

LOGGER = logging.getLogger(__name__)


class RenaultService(StrEnum):
    """Service names."""

    AC_CANCEL = "ac_cancel"
    AC_SET_SCHEDULES = "ac_set_schedules"
    AC_START = "ac_start"
    CHARGE_SET_SCHEDULES = "charge_set_schedules"
    CHARGE_START = "charge_start"
    EV_CLEAR_SCHEDULES = "ev_clear_schedules"
    EV_SET_SCHEDULES = "ev_set_schedules"


class RenaultServiceArgument(StrEnum):
    """Service argument names."""

    CHARGE_DURATION = "charge_duration"
    CHARGE_MODE_RQ = "charge_mode_rq"
    CHARGE_TIME_START = "charge_time_start"
    PRECONDITIONING_TEMPERATURE = "preconditioning_temperature"
    PROGRAMS = "programs"
    SCHEDULES = "schedules"
    TEMPERATURE = "temperature"
    VEHICLE = "vehicle"
    WHEN = "when"


SERVICE_VEHICLE_SCHEMA = probatio.Schema(
    {
        probatio.Required(RenaultServiceArgument.VEHICLE): cv.string,
    }
)
SERVICE_AC_START_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        probatio.Required(RenaultServiceArgument.TEMPERATURE): cv.positive_float,
        probatio.Optional(RenaultServiceArgument.WHEN): cv.datetime,
    }
)
SERVICE_CHARGE_START_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        probatio.Optional(RenaultServiceArgument.WHEN): cv.datetime,
    }
)
SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA = probatio.Schema(
    {
        probatio.Required("startTime"): cv.string,
        probatio.Required("duration"): cv.positive_int,
    }
)
SERVICE_CHARGE_SET_SCHEDULE_SCHEMA = probatio.Schema(
    {
        probatio.Required("id"): cv.positive_int,
        probatio.Optional("activated"): cv.boolean,
        probatio.Optional("monday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("tuesday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("wednesday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("thursday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("friday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("saturday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("sunday"): probatio.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
    }
)
SERVICE_CHARGE_SET_SCHEDULES_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        probatio.Required(RenaultServiceArgument.SCHEDULES): probatio.All(
            probatio.EnsureList(), [SERVICE_CHARGE_SET_SCHEDULE_SCHEMA]
        ),
    }
)

SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA = probatio.Schema(
    {
        probatio.Required("readyAtTime"): cv.string,
    }
)

SERVICE_AC_SET_SCHEDULE_SCHEMA = probatio.Schema(
    {
        probatio.Required("id"): cv.positive_int,
        probatio.Optional("activated"): cv.boolean,
        probatio.Optional("monday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("tuesday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("wednesday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("thursday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("friday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("saturday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
        probatio.Optional("sunday"): probatio.Any(
            None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA
        ),
    }
)
SERVICE_AC_SET_SCHEDULES_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        probatio.Required(RenaultServiceArgument.SCHEDULES): probatio.All(
            probatio.EnsureList(), [SERVICE_AC_SET_SCHEDULE_SCHEMA]
        ),
    }
)

SERVICE_EV_SET_SCHEDULES_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        probatio.Optional(RenaultServiceArgument.PROGRAMS): probatio.All(
            probatio.EnsureList(), [dict]
        ),
        probatio.Optional(
            RenaultServiceArgument.PRECONDITIONING_TEMPERATURE
        ): cv.positive_float,
        probatio.Optional(RenaultServiceArgument.CHARGE_MODE_RQ): cv.string,
        probatio.Optional(RenaultServiceArgument.CHARGE_TIME_START): cv.string,
        probatio.Optional(RenaultServiceArgument.CHARGE_DURATION): cv.positive_int,
    }
)


async def ac_cancel(service_call: ServiceCall) -> None:
    """Cancel A/C."""
    proxy = get_vehicle_proxy(service_call)

    LOGGER.debug("A/C cancel attempt")
    result = await proxy.set_ac_stop()
    LOGGER.debug("A/C cancel result: %s", result)


async def ac_start(service_call: ServiceCall) -> None:
    """Start A/C."""
    temperature: float = service_call.data[RenaultServiceArgument.TEMPERATURE]
    when: datetime | None = service_call.data.get(RenaultServiceArgument.WHEN)
    proxy = get_vehicle_proxy(service_call)

    LOGGER.debug("A/C start attempt: %s / %s", temperature, when)
    result = await proxy.set_ac_start(temperature, when)
    LOGGER.debug("A/C start result: %s", result.raw_data)


async def charge_start(service_call: ServiceCall) -> None:
    """Start Charging with optional delay."""
    when: datetime | None = service_call.data.get(RenaultServiceArgument.WHEN)
    proxy = get_vehicle_proxy(service_call)

    LOGGER.debug("Charge start attempt, when: %s", when)
    result = await proxy.set_charge_start(when)
    LOGGER.debug("Charge start result: %s", result.raw_data)


async def charge_set_schedules(service_call: ServiceCall) -> None:
    """Set charge schedules."""
    schedules: list[dict[str, Any]] = service_call.data[
        RenaultServiceArgument.SCHEDULES
    ]
    proxy = get_vehicle_proxy(service_call)
    charge_schedules = await proxy.get_charging_settings()
    for schedule in schedules:
        charge_schedules.update(schedule)

    if TYPE_CHECKING:
        assert charge_schedules.schedules is not None
    LOGGER.debug("Charge set schedules attempt: %s", schedules)
    result = await proxy.set_charge_schedules(charge_schedules.schedules)

    LOGGER.debug("Charge set schedules result: %s", result)
    LOGGER.debug(
        "It may take some time before these changes are reflected in your vehicle"
    )


async def ac_set_schedules(service_call: ServiceCall) -> None:
    """Set A/C schedules (automatically routes to KCM /ev/settings on Phase 2 vehicles)."""
    schedules: list[dict[str, Any]] = service_call.data[
        RenaultServiceArgument.SCHEDULES
    ]
    proxy = get_vehicle_proxy(service_call)

    if proxy.uses_kcm_ev_settings():
        ev_settings = await proxy.get_ev_settings()
        programs = hvac_schedules_to_ev_programs(schedules, ev_settings.programs)
        payload = ev_settings.to_post_body(programs=programs)
        LOGGER.debug("KCM /ev/settings HVAC set schedules attempt: %s", payload)
        result = await proxy.set_ev_settings(payload)
        LOGGER.debug("KCM /ev/settings HVAC set schedules result: %s", result)
        return

    hvac_schedules = await proxy.get_hvac_settings()

    for schedule in schedules:
        hvac_schedules.update(schedule)

    if TYPE_CHECKING:
        assert hvac_schedules.schedules is not None
    LOGGER.debug("HVAC set schedules attempt: %s", schedules)
    result = await proxy.set_hvac_schedules(hvac_schedules.schedules)

    LOGGER.debug("HVAC set schedules result: %s", result)
    LOGGER.debug(
        "It may take some time before these changes are reflected in your vehicle"
    )


async def ev_set_schedules(service_call: ServiceCall) -> None:
    """Set KCM /ev/settings departure schedules and preconditioning/charging parameters."""
    proxy = get_vehicle_proxy(service_call)
    ev_settings = await proxy.get_ev_settings()

    raw_programs: list[dict[str, Any]] | None = service_call.data.get(
        RenaultServiceArgument.PROGRAMS
    )
    normalized_programs: list[dict[str, Any]] | None = None
    if raw_programs is not None:
        normalized_programs = [normalize_ev_program(p) for p in raw_programs]

    payload = ev_settings.to_post_body(
        programs=normalized_programs,
        preconditioning_temperature=service_call.data.get(
            RenaultServiceArgument.PRECONDITIONING_TEMPERATURE
        ),
        charge_mode_rq=service_call.data.get(RenaultServiceArgument.CHARGE_MODE_RQ),
        charge_time_start=service_call.data.get(
            RenaultServiceArgument.CHARGE_TIME_START
        ),
        charge_duration=service_call.data.get(RenaultServiceArgument.CHARGE_DURATION),
    )
    LOGGER.debug("KCM /ev/settings set schedules attempt: %s", payload)
    result = await proxy.set_ev_settings(payload)
    LOGGER.debug("KCM /ev/settings set schedules result: %s", result)


async def ev_clear_schedules(service_call: ServiceCall) -> None:
    """Clear all KCM /ev/settings departure schedules."""
    proxy = get_vehicle_proxy(service_call)
    ev_settings = await proxy.get_ev_settings()
    payload = ev_settings.to_post_body(programs=[])
    LOGGER.debug("KCM /ev/settings clear schedules attempt: %s", payload)
    result = await proxy.set_ev_settings(payload)
    LOGGER.debug("KCM /ev/settings clear schedules result: %s", result)


def get_vehicle_proxy(service_call: ServiceCall) -> RenaultVehicleProxy:
    """Get vehicle from service_call data."""
    device_id: str = service_call.data[RenaultServiceArgument.VEHICLE]
    entry: RenaultConfigEntry
    device_entry, entry = async_get_device_and_config_entry(
        service_call.hass, DOMAIN, device_id
    )
    for vin, vehicle in entry.runtime_data.vehicles.items():
        if (DOMAIN, vin) in device_entry.identifiers:
            return vehicle
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_config_entry_for_device",
        translation_placeholders={"device_id": device_entry.name or device_id},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Renault services."""

    hass.services.async_register(
        DOMAIN,
        RenaultService.AC_CANCEL,
        ac_cancel,
        schema=SERVICE_VEHICLE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RenaultService.AC_START,
        ac_start,
        schema=SERVICE_AC_START_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RenaultService.CHARGE_START,
        charge_start,
        schema=SERVICE_CHARGE_START_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RenaultService.CHARGE_SET_SCHEDULES,
        charge_set_schedules,
        schema=SERVICE_CHARGE_SET_SCHEDULES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RenaultService.AC_SET_SCHEDULES,
        ac_set_schedules,
        schema=SERVICE_AC_SET_SCHEDULES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RenaultService.EV_SET_SCHEDULES,
        ev_set_schedules,
        schema=SERVICE_EV_SET_SCHEDULES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RenaultService.EV_CLEAR_SCHEDULES,
        ev_clear_schedules,
        schema=SERVICE_VEHICLE_SCHEMA,
    )
