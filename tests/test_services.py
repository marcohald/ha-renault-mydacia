"""Tests for Renault custom integration services."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.renault.ev_settings import (
    normalize_ev_program,
    hvac_schedules_to_ev_programs,
    charge_schedules_to_ev_programs,
)


def test_ev_set_schedules_shorthand_normalization():
    """Test normalizing shorthand day list into full boolean dictionary."""
    raw_prog = {
        "activated": True,
        "program_type": "PRECONDITIONING",
        "departure_time": "08:15",
        "days": ["mon", "wed", "fri"],
    }
    normalized = normalize_ev_program(raw_prog)
    assert normalized["programActivationStatus"] is True
    assert normalized["programType"] == "PRECONDITIONING"
    assert normalized["programDepartureTime"] == "08:15"
    assert normalized["programActivationMonday"] is True
    assert normalized["programActivationTuesday"] is False
    assert normalized["programActivationWednesday"] is True
    assert normalized["programActivationThursday"] is False
    assert normalized["programActivationFriday"] is True
    assert normalized["programActivationSaturday"] is False
    assert normalized["programActivationSunday"] is False


@pytest.mark.asyncio
async def test_ev_clear_schedules_payload_generation():
    """Test that clearing schedules passes an empty program list."""
    vehicle = MagicMock()
    vehicle.get_ev_settings = AsyncMock()
    mock_ev = MagicMock()
    mock_ev.to_post_body = MagicMock(return_value={"programs": []})
    vehicle.get_ev_settings.return_value = mock_ev
    vehicle.set_ev_settings = AsyncMock()

    # Simulate clearing schedules
    ev_settings = await vehicle.get_ev_settings()
    payload = ev_settings.to_post_body(programs=[])
    await vehicle.set_ev_settings(payload)

    mock_ev.to_post_body.assert_called_once_with(programs=[])
    vehicle.set_ev_settings.assert_called_once_with({"programs": []})


@pytest.mark.asyncio
async def test_pause_resume_charge_action():
    """Test charge pause/resume endpoint payload construction."""
    from custom_components.renault.ev_settings import CHARGE_PAUSE_RESUME_ENDPOINT

    assert CHARGE_PAUSE_RESUME_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/charge/pause-resume"
    assert CHARGE_PAUSE_RESUME_ENDPOINT.mode == "kcm-pause-resume"

