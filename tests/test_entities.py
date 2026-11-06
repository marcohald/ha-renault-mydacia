"""Tests for Renault number, select, and button entity behaviors."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.renault.ev_settings import (
    KamereonVehicleEvSettingsData,
    SOC_LEVELS_ENDPOINT,
)
from custom_components.renault.number import (
    RenaultNumberEntity,
    NUMBER_TYPES,
)

from custom_components.renault.select import (
    RenaultSelectEntity,
    SENSOR_TYPES as SELECT_TYPES,
)


@pytest.fixture
def mock_ev_vehicle():
    """Mock vehicle proxy with ev_settings coordinator."""
    vehicle = MagicMock()
    vehicle.details = MagicMock()
    vehicle.details.vin = "VF1TESTVIN000002"
    vehicle.vin = "VF1TESTVIN000002"
    vehicle.device_info = {"identifiers": {("renault", "VF1TESTVIN000002")}}
    vehicle.get_ev_settings = AsyncMock()
    vehicle.set_ev_settings = AsyncMock()
    vehicle.set_battery_soc = AsyncMock()

    coord = MagicMock()
    coord.vehicle = vehicle
    coord.async_request_refresh = AsyncMock()
    coord.async_set_updated_data = MagicMock()
    ev_data = KamereonVehicleEvSettingsData.from_dict({
        "lastSettingsUpdateTimestamp": "2026-11-06T00:00:00Z",
        "chargeModeRq": "SCHEDULED",
        "chargeDuration": 90,
        "preconditioningTemperature": 22.0,
        "programs": [],
    })
    coord.data = ev_data
    vehicle.get_ev_settings.return_value = ev_data
    vehicle.coordinators = {"ev_settings": coord}
    return vehicle


def test_number_entity_preconditioning_temperature(mock_ev_vehicle):
    """Test preconditioning temperature number entity value and update."""
    desc = next(d for d in NUMBER_TYPES if d.key == "preconditioning_temperature")
    entity = RenaultNumberEntity(mock_ev_vehicle, desc)
    assert entity.native_value == 22.0
    assert entity.native_min_value == 16.0
    assert entity.native_max_value == 28.0


def test_number_entity_charge_duration(mock_ev_vehicle):
    """Test charge duration number entity value."""
    desc = next(d for d in NUMBER_TYPES if d.key == "charge_duration")
    entity = RenaultNumberEntity(mock_ev_vehicle, desc)
    assert entity.native_value == 90
    assert entity.native_step == 15


def test_select_entity_charge_mode_rq(mock_ev_vehicle):
    """Test select entity for charge_mode_rq."""
    desc = next(d for d in SELECT_TYPES if d.key == "charge_mode_rq")
    entity = RenaultSelectEntity(mock_ev_vehicle, desc)
    assert entity.current_option == "SCHEDULED"
    assert "SMARTCHARGING_OFFPEAK" in entity.options


def test_soc_levels_endpoint_definition():
    """Verify soc-levels endpoint is configured for KCM."""
    assert SOC_LEVELS_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/ev/soc-levels"
    assert SOC_LEVELS_ENDPOINT.mode == "kcm-soc-levels"


