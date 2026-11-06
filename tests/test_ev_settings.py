"""Tests for KCM /ev/settings models and schedule converters."""

import pytest

from custom_components.renault.ev_settings import (
    DAYS_OF_WEEK_KEYS,
    KamereonVehicleEvSettingsData,
    charge_schedules_to_ev_programs,
    hvac_schedules_to_ev_programs,
    normalize_departure_time,
    normalize_ev_program,
)


def test_normalize_departure_time():
    """Test departure time string parsing and normalization to HH:MM."""
    assert normalize_departure_time("07:30") == "07:30"
    assert normalize_departure_time("T07:30Z") == "07:30"
    assert normalize_departure_time("07:30:00") == "07:30"
    assert normalize_departure_time(" 09:15 ") == "09:15"
    assert normalize_departure_time("00:00") == "00:00"
    assert normalize_departure_time("23:59") == "23:59"

    with pytest.raises(ValueError):
        normalize_departure_time("invalid")
    with pytest.raises(ValueError):
        normalize_departure_time("25:00")
    with pytest.raises(ValueError):
        normalize_departure_time("12:60")


def test_ev_settings_data_serialization():
    """Test KamereonVehicleEvSettingsData deserialization and to_post_body."""
    raw = {
        "lastSettingsUpdateTimestamp": "2026-11-05T21:49:51.087Z",
        "delegatedActivated": False,
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
        ],
    }
    model = KamereonVehicleEvSettingsData.from_dict(raw)
    assert model.chargeModeRq == "SCHEDULED"
    assert model.chargeTimeStart == "01:00"
    assert model.chargeDuration == 60
    assert model.preconditioningTemperature == 21.0
    assert len(model.programs) == 1
    assert model.programs[0]["programActivationStatus"] is True

    # Build post body with overridden temperature
    body = model.to_post_body(preconditioning_temperature=22.5)
    assert body["preconditioningTemperature"] == 22.5
    assert body["chargeModeRq"] == "SCHEDULED"
    assert body["chargeTimeStart"] == "01:00"
    assert len(body["programs"]) == 1
    assert "lastSettingsUpdateTimestamp" in body


def test_hvac_schedules_to_ev_programs():
    """Test converting HA legacy AC schedule dictionaries to KCM departure programs."""
    existing_programs = [
        {
            "programActivationStatus": True,
            "programType": "CHARGE",
            "programDepartureTime": "02:00",
            "programActivationMonday": True,
        },
        {
            "programActivationStatus": True,
            "programType": "CHARGE_AND_PRECONDITIONING",
            "programDepartureTime": "06:00",
            "programActivationWednesday": True,
        },
    ]

    schedules = [
        {
            "id": 1,
            "activated": True,
            "monday": {"readyAtTime": "T07:30Z"},
            "tuesday": {"readyAtTime": "07:30"},
            "wednesday": {"readyAtTime": "T08:00Z"},
        }
    ]

    programs = hvac_schedules_to_ev_programs(schedules, existing_programs)

    # Both CHARGE and CHARGE_AND_PRECONDITIONING existing programs must be preserved
    assert len(programs) == 4
    assert programs[0]["programType"] == "CHARGE"
    assert programs[1]["programType"] == "CHARGE_AND_PRECONDITIONING"

    # New PRECONDITIONING programs grouped by departure time
    prog_730 = next(p for p in programs if p.get("programDepartureTime") == "07:30")
    assert prog_730["programActivationMonday"] is True
    assert prog_730["programActivationTuesday"] is True
    assert prog_730["programActivationWednesday"] is False

    prog_800 = next(p for p in programs if p.get("programDepartureTime") == "08:00")
    assert prog_800["programActivationWednesday"] is True
    assert prog_800["programActivationMonday"] is False


def test_charge_schedules_to_ev_programs():
    """Test converting HA legacy charge schedule dictionaries to KCM charge programs."""
    existing_programs = [
        {
            "programActivationStatus": True,
            "programType": "PRECONDITIONING",
            "programDepartureTime": "07:30",
            "programActivationMonday": True,
        },
        {
            "programActivationStatus": True,
            "programType": "CHARGE_AND_PRECONDITIONING",
            "programDepartureTime": "08:00",
            "programActivationFriday": True,
        },
    ]

    schedules = [
        {
            "id": 1,
            "activated": True,
            "monday": {"startTime": "T01:30Z", "duration": 120},
            "wednesday": {"startTime": "01:30", "duration": 120},
        }
    ]

    programs = charge_schedules_to_ev_programs(schedules, existing_programs)
    assert len(programs) == 3
    assert programs[0]["programType"] == "PRECONDITIONING"
    assert programs[1]["programType"] == "CHARGE_AND_PRECONDITIONING"

    charge_prog = next(p for p in programs if p.get("programType") == "CHARGE")
    assert charge_prog["programDepartureTime"] == "01:30"
    assert charge_prog["programActivationMonday"] is True
    assert charge_prog["programActivationWednesday"] is True


def test_normalize_ev_program():
    """Test user-friendly EvProgram normalization."""
    prog = normalize_ev_program({
        "program_type": "PRECONDITIONING",
        "time": "08:15",
        "activated": True,
        "days": ["mon", "wed", "fri"],
    })
    assert prog["programType"] == "PRECONDITIONING"
    assert prog["programDepartureTime"] == "08:15"
    assert prog["programActivationStatus"] is True
    assert prog["programActivationMonday"] is True
    assert prog["programActivationWednesday"] is True
    assert prog["programActivationFriday"] is True
    assert prog["programActivationTuesday"] is False
    assert prog["programActivationSaturday"] is False
