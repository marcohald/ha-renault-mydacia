"""Support for KCM /ev/settings (Phase 2 / C1AH2 / CVC vehicles such as Dacia Spring XBG2DE)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
from typing import Any

from renault_api.kamereon import models

DAYS_OF_WEEK_KEYS: tuple[tuple[str, str], ...] = (
    ("monday", "programActivationMonday"),
    ("tuesday", "programActivationTuesday"),
    ("wednesday", "programActivationWednesday"),
    ("thursday", "programActivationThursday"),
    ("friday", "programActivationFriday"),
    ("saturday", "programActivationSaturday"),
    ("sunday", "programActivationSunday"),
)

EV_SETTINGS_ENDPOINT = models.EndpointDefinition(
    "/kcm/v1/vehicles/{vin}/ev/settings", mode="kcm-settings"
)

CHARGE_PAUSE_RESUME_ENDPOINT = models.EndpointDefinition(
    "/kcm/v1/vehicles/{vin}/charge/pause-resume", mode="kcm-pause-resume"
)

SOC_LEVELS_ENDPOINT = models.EndpointDefinition(
    "/kcm/v1/vehicles/{vin}/ev/soc-levels", mode="kcm-soc-levels"
)

CHARGE_START_ENDPOINT = models.EndpointDefinition(
    "/kcm/v1/vehicles/{vin}/charge/start", mode="kcm-charge-start"
)

CHARGE_SETTINGS_ENDPOINT = models.EndpointDefinition(
    "/kcm/v1/vehicles/{vin}/charge/settings", mode="kcm-charge-settings"
)

CHARGE_SCHEDULE_ENDPOINT = models.EndpointDefinition(
    "/kcm/v1/vehicles/{vin}/charge/schedule", mode="kcm-charge-schedule"
)

# Complete registry of all 8 KCM endpoints identified in My Dacia Android APK
ALL_KCM_ENDPOINTS: dict[str, models.EndpointDefinition] = {
    "ev-settings": EV_SETTINGS_ENDPOINT,
    "soc-levels": SOC_LEVELS_ENDPOINT,
    "charge-pause-resume": CHARGE_PAUSE_RESUME_ENDPOINT,
    "charge-start": CHARGE_START_ENDPOINT,
    "charge-settings": CHARGE_SETTINGS_ENDPOINT,
    "charge-schedule": CHARGE_SCHEDULE_ENDPOINT,
}

# Register XBG2DE (Dacia Spring Phase 2 / MY26) and XBG1VE (Phase 1)
# in renault_api._VEHICLE_ENDPOINTS so that supports_endpoint() works
# out of the box even before renault-api upstream adds them.
if "XBG2DE" not in models._VEHICLE_ENDPOINTS:
    models._VEHICLE_ENDPOINTS["XBG2DE"] = {
        "actions/charge-set-mode": None,
        "actions/charge-set-schedule": EV_SETTINGS_ENDPOINT,
        "actions/charge-start": CHARGE_PAUSE_RESUME_ENDPOINT,
        "actions/charge-stop": CHARGE_PAUSE_RESUME_ENDPOINT,
        "actions/horn-start": models._DEFAULT_ENDPOINTS["actions/horn-start"],
        "actions/hvac-set-schedule": EV_SETTINGS_ENDPOINT,
        "actions/hvac-start": models._DEFAULT_ENDPOINTS["actions/hvac-start"],
        "actions/hvac-stop": models._KCA_ALTERNATIVE_ENDPOINTS["actions/hvac-stop"],
        "actions/lights-start": models._DEFAULT_ENDPOINTS["actions/lights-start"],
        "actions/refresh-location": models._DEFAULT_ENDPOINTS[
            "actions/refresh-location"
        ],
        "alerts": None,
        "battery-status": models._DEFAULT_ENDPOINTS["battery-status"],
        "charge-history": None,
        "charge-mode": None,
        "charge-schedule": EV_SETTINGS_ENDPOINT,
        "charges": models._DEFAULT_ENDPOINTS["charges"],
        "charging-settings": None,
        "cockpit": models._DEFAULT_ENDPOINTS["cockpit"],
        "ev-settings": EV_SETTINGS_ENDPOINT,
        "hvac-history": None,
        "hvac-sessions": None,
        "hvac-settings": None,
        "hvac-status": models._DEFAULT_ENDPOINTS["hvac-status"],
        "location": models._DEFAULT_ENDPOINTS["location"],
        "lock-status": None,
        "notification-settings": None,
        "pressure": None,
        "res-state": None,
        "soc-levels": SOC_LEVELS_ENDPOINT,
    }

if "XBG1VE" not in models._VEHICLE_ENDPOINTS:
    models._VEHICLE_ENDPOINTS["XBG1VE"] = models._VEHICLE_ENDPOINTS["XBG2DE"]


def normalize_departure_time(time_str: str) -> str:
    """Normalize a time string ('T07:30Z', '07:30:00', or '07:30') to 'HH:MM'."""
    cleaned = time_str.strip()
    if cleaned.startswith("T"):
        cleaned = cleaned[1:]
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    parts = cleaned.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid departure time format: {time_str!r} (expected HH:MM)")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Departure time out of range: {time_str!r}")
    return f"{hour:02d}:{minute:02d}"


@dataclass
class KamereonVehicleEvSettingsData(models.KamereonVehicleDataAttributes):
    """Kamereon vehicle data ev/settings attributes."""

    raw_data: dict[str, Any] = field(default_factory=dict)
    lastSettingsUpdateTimestamp: str | None = None
    delegatedActivated: bool | None = None
    chargeModeRq: str | None = None
    chargeTimeStart: str | None = None
    chargeDuration: int | None = None
    preconditioningTemperature: float | None = None
    preconditioningHeatedStrgWheel: bool | None = None
    preconditioningHeatedRightSeat: bool | None = None
    preconditioningHeatedLeftSeat: bool | None = None
    programs: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw_data: dict[str, Any]) -> KamereonVehicleEvSettingsData:
        """Create KamereonVehicleEvSettingsData from raw JSON response."""
        return cls(
            raw_data=raw_data,
            lastSettingsUpdateTimestamp=raw_data.get("lastSettingsUpdateTimestamp"),
            delegatedActivated=raw_data.get("delegatedActivated"),
            chargeModeRq=raw_data.get("chargeModeRq"),
            chargeTimeStart=raw_data.get("chargeTimeStart"),
            chargeDuration=raw_data.get("chargeDuration"),
            preconditioningTemperature=raw_data.get("preconditioningTemperature"),
            preconditioningHeatedStrgWheel=raw_data.get(
                "preconditioningHeatedStrgWheel"
            ),
            preconditioningHeatedRightSeat=raw_data.get(
                "preconditioningHeatedRightSeat"
            ),
            preconditioningHeatedLeftSeat=raw_data.get("preconditioningHeatedLeftSeat"),
            programs=list(raw_data.get("programs") or []),
        )

    def to_post_body(
        self,
        *,
        programs: list[dict[str, Any]] | None = None,
        charge_mode_rq: str | None = None,
        charge_time_start: str | None = None,
        charge_duration: int | None = None,
        preconditioning_temperature: float | None = None,
        heated_steering_wheel: bool | None = None,
        heated_right_seat: bool | None = None,
        heated_left_seat: bool | None = None,
    ) -> dict[str, Any]:
        """Build PostEvSettingsBodySchema payload for POST /ev/settings."""
        now_iso = (
            datetime.now(UTC)
            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z"
        )
        return {
            "lastSettingsUpdateTimestamp": now_iso,
            "chargeModeRq": (
                charge_mode_rq
                if charge_mode_rq is not None
                else (self.chargeModeRq or "SCHEDULED")
            ),
            "chargeTimeStart": (
                normalize_departure_time(charge_time_start)
                if charge_time_start is not None
                else (self.chargeTimeStart or "01:00")
            ),
            "chargeDuration": (
                charge_duration
                if charge_duration is not None
                else (self.chargeDuration if self.chargeDuration is not None else 60)
            ),
            "preconditioningTemperature": float(
                preconditioning_temperature
                if preconditioning_temperature is not None
                else (
                    self.preconditioningTemperature
                    if self.preconditioningTemperature is not None
                    else 21.0
                )
            ),
            "preconditioningHeatedStrgWheel": bool(
                heated_steering_wheel
                if heated_steering_wheel is not None
                else self.preconditioningHeatedStrgWheel
            ),
            "preconditioningHeatedRightSeat": bool(
                heated_right_seat
                if heated_right_seat is not None
                else self.preconditioningHeatedRightSeat
            ),
            "preconditioningHeatedLeftSeat": bool(
                heated_left_seat
                if heated_left_seat is not None
                else self.preconditioningHeatedLeftSeat
            ),
            "programs": (
                programs if programs is not None else list(self.programs or [])
            ),
        }


def hvac_schedules_to_ev_programs(
    schedules: list[dict[str, Any]],
    existing_programs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert Home Assistant `renault.ac_set_schedules` input to KCM `EvProgramSchema` list.

    In the legacy `ac_set_schedules` service, each schedule item has:
      - `id`: 1..5
      - `activated`: bool
      - `monday`..`sunday`: `{"readyAtTime": "T07:30Z"}` or `{"readyAtTime": "07:30"}`

    In KCM `/ev/settings`, each `EvProgramSchema` has a single `programDepartureTime` ("HH:MM")
    and boolean day flags (`programActivationMonday`..`programActivationSunday`).
    If a single schedule dictionary specifies different `readyAtTime` values across days,
    it is automatically split into separate `PRECONDITIONING` programs grouped by departure time.
    Existing `CHARGE`-only programs are preserved unless overwritten.
    """
    preserved_charge_programs: list[dict[str, Any]] = [
        p
        for p in (existing_programs or [])
        if p.get("programType") in ("CHARGE", "CHARGE_AND_PRECONDITIONING")
    ]
    new_programs: list[dict[str, Any]] = []

    for sched in schedules:
        activated = bool(sched.get("activated", True))
        # Group days by their normalized readyAtTime
        time_to_days: dict[str, set[str]] = {}
        for day_name, _ in DAYS_OF_WEEK_KEYS:
            day_cfg = sched.get(day_name)
            if isinstance(day_cfg, dict) and day_cfg.get("readyAtTime"):
                norm_time = normalize_departure_time(day_cfg["readyAtTime"])
                time_to_days.setdefault(norm_time, set()).add(day_name)

        for dep_time, active_days in time_to_days.items():
            prog: dict[str, Any] = {
                "programActivationStatus": activated,
                "programType": "PRECONDITIONING",
                "programDepartureTime": dep_time,
            }
            for day_name, api_key in DAYS_OF_WEEK_KEYS:
                prog[api_key] = day_name in active_days
            new_programs.append(prog)

    return (preserved_charge_programs + new_programs)[:5]


def charge_schedules_to_ev_programs(
    schedules: list[dict[str, Any]],
    existing_programs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert Home Assistant `renault.charge_set_schedules` input to KCM `EvProgramSchema` list.

    In the legacy `charge_set_schedules` service, each schedule item has:
      - `id`: 1..5
      - `activated`: bool
      - `monday`..`sunday`: `{"startTime": "T12:00Z", "duration": 15}`

    In KCM `/ev/settings`, each `EvProgramSchema` has a single `programDepartureTime` ("HH:MM")
    and boolean day flags (`programActivationMonday`..`programActivationSunday`).
    Existing `PRECONDITIONING`-only programs are preserved unless overwritten.
    """
    preserved_precond_programs: list[dict[str, Any]] = [
        p
        for p in (existing_programs or [])
        if p.get("programType") in ("PRECONDITIONING", "CHARGE_AND_PRECONDITIONING")
    ]
    new_programs: list[dict[str, Any]] = []

    for sched in schedules:
        activated = bool(sched.get("activated", True))
        time_to_days: dict[str, set[str]] = {}
        for day_name, _ in DAYS_OF_WEEK_KEYS:
            day_cfg = sched.get(day_name)
            if isinstance(day_cfg, dict) and day_cfg.get("startTime"):
                norm_time = normalize_departure_time(day_cfg["startTime"])
                time_to_days.setdefault(norm_time, set()).add(day_name)

        for dep_time, active_days in time_to_days.items():
            prog: dict[str, Any] = {
                "programActivationStatus": activated,
                "programType": "CHARGE",
                "programDepartureTime": dep_time,
            }
            for day_name, api_key in DAYS_OF_WEEK_KEYS:
                prog[api_key] = day_name in active_days
            new_programs.append(prog)

    return (preserved_precond_programs + new_programs)[:5]


def normalize_ev_program(program_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize a user-provided program dictionary into `EvProgramSchema` format."""
    program_type = str(
        program_input.get("programType")
        or program_input.get("program_type")
        or "PRECONDITIONING"
    ).upper()
    if program_type not in (
        "PRECONDITIONING",
        "CHARGE",
        "CHARGE_AND_PRECONDITIONING",
    ):
        raise ValueError(
            f"Invalid program_type {program_type!r}; must be PRECONDITIONING, CHARGE, or CHARGE_AND_PRECONDITIONING"
        )

    raw_time = (
        program_input.get("programDepartureTime")
        or program_input.get("departure_time")
        or program_input.get("time")
        or "07:30"
    )
    dep_time = normalize_departure_time(str(raw_time))
    activated = bool(
        program_input.get(
            "programActivationStatus",
            program_input.get("activated", True),
        )
    )

    days_list = program_input.get("days")
    active_days_set: set[str] = set()
    if isinstance(days_list, list):
        for d in days_list:
            d_low = str(d).strip().lower()
            for day_name, _ in DAYS_OF_WEEK_KEYS:
                if day_name.startswith(d_low[:3]):
                    active_days_set.add(day_name)

    prog: dict[str, Any] = {
        "programActivationStatus": activated,
        "programType": program_type,
        "programDepartureTime": dep_time,
    }
    for day_name, api_key in DAYS_OF_WEEK_KEYS:
        if api_key in program_input:
            prog[api_key] = bool(program_input[api_key])
        elif day_name in program_input:
            prog[api_key] = bool(program_input[day_name])
        elif days_list is not None:
            prog[api_key] = day_name in active_days_set
        else:
            prog[api_key] = False

    return prog
