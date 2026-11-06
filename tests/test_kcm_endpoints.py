"""Tests for KCM vehicle endpoint mapping and definition."""

from renault_api.kamereon import models

from custom_components.renault.ev_settings import (
    CHARGE_PAUSE_RESUME_ENDPOINT,
    EV_SETTINGS_ENDPOINT,
    SOC_LEVELS_ENDPOINT,
)


def test_vehicle_endpoints_registration():
    """Verify XBG2DE and XBG1VE are registered in _VEHICLE_ENDPOINTS with KCM definitions."""
    assert "XBG2DE" in models._VEHICLE_ENDPOINTS
    assert "XBG1VE" in models._VEHICLE_ENDPOINTS

    endpoints = models._VEHICLE_ENDPOINTS["XBG2DE"]

    # Charge pause-resume endpoints
    assert endpoints["actions/charge-start"] == CHARGE_PAUSE_RESUME_ENDPOINT
    assert endpoints["actions/charge-stop"] == CHARGE_PAUSE_RESUME_ENDPOINT
    assert CHARGE_PAUSE_RESUME_ENDPOINT.mode == "kcm-pause-resume"
    assert "/charge/pause-resume" in CHARGE_PAUSE_RESUME_ENDPOINT.url

    # EV settings endpoints
    assert endpoints["ev-settings"] == EV_SETTINGS_ENDPOINT
    assert endpoints["actions/charge-set-schedule"] == EV_SETTINGS_ENDPOINT
    assert endpoints["actions/hvac-set-schedule"] == EV_SETTINGS_ENDPOINT
    assert EV_SETTINGS_ENDPOINT.mode == "kcm-settings"

    # SoC levels endpoints
    assert endpoints["soc-levels"] == SOC_LEVELS_ENDPOINT
    assert SOC_LEVELS_ENDPOINT.mode == "kcm-soc-levels"
    assert "/ev/soc-levels" in SOC_LEVELS_ENDPOINT.url

    # Location refresh
    assert endpoints["actions/refresh-location"] is not None
    assert endpoints["actions/hvac-stop"] is not None
