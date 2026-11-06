"""Tests for KCM vehicle endpoint mapping and definition."""

from renault_api.kamereon import models

from custom_components.renault.ev_settings import (
    ALL_KCM_ENDPOINTS,
    CHARGE_PAUSE_RESUME_ENDPOINT,
    CHARGE_SCHEDULE_ENDPOINT,
    CHARGE_SETTINGS_ENDPOINT,
    CHARGE_START_ENDPOINT,
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


def test_all_kcm_endpoints_exhaustive():
    """Verify all 8 KCM endpoints identified from the Android APK are defined and mapped."""
    # 1 & 2: GET / POST ev/settings
    assert EV_SETTINGS_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/ev/settings"
    assert EV_SETTINGS_ENDPOINT.mode == "kcm-settings"

    # 3 & 4: GET / POST ev/soc-levels
    assert SOC_LEVELS_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/ev/soc-levels"
    assert SOC_LEVELS_ENDPOINT.mode == "kcm-soc-levels"

    # 5: POST charge/pause-resume
    assert CHARGE_PAUSE_RESUME_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/charge/pause-resume"
    assert CHARGE_PAUSE_RESUME_ENDPOINT.mode == "kcm-pause-resume"

    # 6: POST charge/start
    assert CHARGE_START_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/charge/start"
    assert CHARGE_START_ENDPOINT.mode == "kcm-charge-start"

    # 7: GET charge/settings
    assert CHARGE_SETTINGS_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/charge/settings"
    assert CHARGE_SETTINGS_ENDPOINT.mode == "kcm-charge-settings"

    # 8: POST charge/schedule
    assert CHARGE_SCHEDULE_ENDPOINT.url == "/kcm/v1/vehicles/{vin}/charge/schedule"
    assert CHARGE_SCHEDULE_ENDPOINT.mode == "kcm-charge-schedule"

    # Registry check
    assert len(ALL_KCM_ENDPOINTS) == 6
    assert ALL_KCM_ENDPOINTS["ev-settings"] == EV_SETTINGS_ENDPOINT
    assert ALL_KCM_ENDPOINTS["soc-levels"] == SOC_LEVELS_ENDPOINT
    assert ALL_KCM_ENDPOINTS["charge-pause-resume"] == CHARGE_PAUSE_RESUME_ENDPOINT
    assert ALL_KCM_ENDPOINTS["charge-start"] == CHARGE_START_ENDPOINT
    assert ALL_KCM_ENDPOINTS["charge-settings"] == CHARGE_SETTINGS_ENDPOINT
    assert ALL_KCM_ENDPOINTS["charge-schedule"] == CHARGE_SCHEDULE_ENDPOINT
