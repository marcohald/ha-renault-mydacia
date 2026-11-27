"""Charge-start button builds the same request as the My Dacia app."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.renault.ev_settings import (
    EV_SETTINGS_ENDPOINT,
    KamereonVehicleEvSettingsData,
)
from custom_components.renault.renault_vehicle import RenaultVehicleProxy

# GET /ev/settings answer before pressing "start charging"
CURRENT = {
    "lastSettingsUpdateTimestamp": "2026-11-26T20:00:00Z",
    "chargeModeRq": "SCHEDULED",
    "chargeTimeStart": "01:00",
    "chargeDuration": 60,
    "preconditioningTemperature": 21.0,
    "preconditioningHeatedStrgWheel": False,
    "preconditioningHeatedRightSeat": False,
    "preconditioningHeatedLeftSeat": False,
    "programs": [
        {
            "programActivationStatus": True,
            "programType": "CHARGE",
            "programDepartureTime": "07:00",
            "programActivationMonday": True,
        }
    ],
}


def _proxy() -> RenaultVehicleProxy:
    proxy = RenaultVehicleProxy.__new__(RenaultVehicleProxy)
    proxy.hass = MagicMock()
    proxy.config_entry = MagicMock()
    proxy.config_entry.data = {}
    proxy._hub = MagicMock()
    proxy._details = MagicMock()
    proxy._details.vin = "VIN123"
    proxy._details.supports_endpoint.return_value = True
    proxy._details.get_endpoint.return_value = EV_SETTINGS_ENDPOINT
    proxy.coordinators = {}
    proxy.programs_before_instant_charge = []
    proxy._vehicle = MagicMock()
    proxy._vehicle._get_vehicle_data = AsyncMock(
        return_value=SimpleNamespace(raw_data=CURRENT)
    )
    proxy._vehicle._set_vehicle_data = AsyncMock(
        return_value=SimpleNamespace(raw_data={"commandId": "1"})
    )
    proxy._vehicle.set_charge_start = AsyncMock()
    return proxy


@pytest.mark.asyncio
async def test_charge_start_posts_ev_settings_without_programs() -> None:
    proxy = _proxy()
    await proxy.set_charge_start()

    proxy._vehicle._get_vehicle_data.assert_awaited_once_with(EV_SETTINGS_ENDPOINT)
    endpoint, body = proxy._vehicle._set_vehicle_data.await_args.args
    assert endpoint is EV_SETTINGS_ENDPOINT
    assert body["programs"] == []
    # everything else is the current setting, unchanged (same as the app)
    for key in (
        "chargeModeRq",
        "chargeTimeStart",
        "chargeDuration",
        "preconditioningTemperature",
        "preconditioningHeatedStrgWheel",
        "preconditioningHeatedRightSeat",
        "preconditioningHeatedLeftSeat",
    ):
        assert body[key] == CURRENT[key], key
    assert body["lastSettingsUpdateTimestamp"] != CURRENT["lastSettingsUpdateTimestamp"]
    assert body["lastSettingsUpdateTimestamp"].endswith("Z")
    # legacy KCA charging-start is not used
    proxy._vehicle.set_charge_start.assert_not_called()
    # removed programs are remembered
    assert proxy.programs_before_instant_charge == CURRENT["programs"]


@pytest.mark.asyncio
async def test_charge_start_updates_ev_settings_coordinator() -> None:
    proxy = _proxy()
    coord = MagicMock()
    proxy.coordinators = {"ev_settings": coord}
    await proxy.set_charge_start()
    coord.async_set_updated_data.assert_called_once()
    data = coord.async_set_updated_data.call_args.args[0]
    assert isinstance(data, KamereonVehicleEvSettingsData)
    assert data.programs == []
