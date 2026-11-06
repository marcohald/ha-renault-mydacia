"""Tests for Renault / My Dacia switches, time, and number entities."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.renault.ev_settings import KamereonVehicleEvSettingsData
from custom_components.renault.switch import (
    RenaultDepartureProgramSwitchEntity,
    RenaultPreconditioningHeaterSwitchEntity,
)
from custom_components.renault.time import RenaultChargeStartTimeEntity


@pytest.fixture
def mock_vehicle():
    """Mock RenaultVehicleProxy."""
    vehicle = MagicMock()
    vehicle.details = MagicMock()
    vehicle.details.vin = "VF1TESTVIN000001"
    vehicle.vin = "VF1TESTVIN000001"
    vehicle.device_info = {"identifiers": {("renault", "VF1TESTVIN000001")}}
    vehicle.get_ev_settings = AsyncMock()
    vehicle.set_ev_settings = AsyncMock()
    return vehicle


@pytest.fixture
def mock_coordinator(mock_vehicle):
    """Mock RenaultDataUpdateCoordinator for ev/settings."""
    coord = MagicMock()
    coord.vehicle = mock_vehicle
    coord.async_request_refresh = AsyncMock()
    ev_data = KamereonVehicleEvSettingsData.from_dict({
        "lastSettingsUpdateTimestamp": "2026-11-06T00:00:00Z",
        "delegatedActivated": False,
        "chargeModeRq": "SCHEDULED",
        "chargeTimeStart": "02:15",
        "chargeDuration": 120,
        "preconditioningTemperature": 20.0,
        "preconditioningHeatedStrgWheel": False,
        "preconditioningHeatedRightSeat": True,
        "preconditioningHeatedLeftSeat": False,
        "programs": [
            {
                "programActivationStatus": True,
                "programType": "PRECONDITIONING",
                "programDepartureTime": "08:00",
                "programActivationMonday": True,
            },
            {
                "programActivationStatus": False,
                "programType": "PRECONDITIONING",
                "programDepartureTime": "09:00",
                "programActivationTuesday": True,
            },
        ],
    })
    coord.data = ev_data
    mock_vehicle.get_ev_settings.return_value = ev_data
    mock_vehicle.coordinators = {"ev_settings": coord}
    return coord


@pytest.mark.asyncio
async def test_departure_program_switch_state(mock_coordinator, mock_vehicle):
    """Test departure program switch is_on and toggle."""
    switch = RenaultDepartureProgramSwitchEntity(mock_vehicle, 0)
    assert switch.is_on is True
    assert switch.unique_id == "vf1testvin000001_departure_program_1"

    await switch.async_turn_off()
    mock_vehicle.set_ev_settings.assert_called_once()
    called_payload = mock_vehicle.set_ev_settings.call_args[0][0]
    assert called_payload["programs"][0]["programActivationStatus"] is False


@pytest.mark.asyncio
async def test_heater_switch_turn_on(mock_coordinator, mock_vehicle):
    """Test seat heater switch turns on and updates ev settings."""
    switch = RenaultPreconditioningHeaterSwitchEntity(
        mock_vehicle,
        "preconditioning_heated_left_seat",
        "preconditioningHeatedLeftSeat",
        "heated_left_seat",
        "preconditioning_heated_left_seat",
    )
    assert switch.is_on is False

    await switch.async_turn_on()
    mock_vehicle.set_ev_settings.assert_called_once()
    called_payload = mock_vehicle.set_ev_settings.call_args[0][0]
    assert called_payload["preconditioningHeatedLeftSeat"] is True


@pytest.mark.asyncio
async def test_charge_start_time_entity(mock_coordinator, mock_vehicle):
    """Test charge start time entity reads native_value and sets new time."""
    from datetime import time

    entity = RenaultChargeStartTimeEntity(mock_vehicle)
    assert entity.native_value == time(2, 15)

    await entity.async_set_value(time(3, 45))
    mock_vehicle.set_ev_settings.assert_called_once()
    called_payload = mock_vehicle.set_ev_settings.call_args[0][0]
    assert called_payload["chargeTimeStart"] == "03:45"

