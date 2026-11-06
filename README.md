# Home Assistant Custom Integration: Renault / My Dacia (Full EV & Heating API Support)

[![CI](https://github.com/marcohald/ha-renault-mydacia/actions/workflows/ci.yml/badge.svg)](https://github.com/marcohald/ha-renault-mydacia/actions/workflows/ci.yml)
[![HACS Default](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A comprehensive, production-grade Home Assistant custom integration for Renault and Dacia electric vehicles. Built on [`homeassistant/components/renault`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/renault) with complete reverse-engineered support for **Phase 2 (`C1AH2` / `CVC` gateway architecture)** vehicles such as the **2024–2026 Dacia Spring Phase 2 (`XBG2DE`)**, while preserving backward compatibility with Phase 1 vehicles (`XBG1VE`, Zoe, Twingo ZE, Mégane E-Tech).

---

## Key Highlights & Architectural Additions

### 1. Unified KCM EV & Heating Schedule API (`/kamereon/kcm/v1/vehicles/{vin}/ev/settings`)
* **Problem Solved:** Phase 2 (`C1AH2` / `CVC`) vehicles reject legacy KCA endpoints like `/kamereon/kca/car-adapter/v1/cars/{vin}/hvac-settings` with `HTTP 502 Bad Gateway` (`err.tech.vcps.ev.hvac-settings.error`).
* **Unified Payload:** Charging schedules and preconditioning/heating programs are unified into a single weekly programs array with individual day flags (`programActivationMonday` ... `programActivationSunday`), departure time (`programDepartureTime`), program type (`PRECONDITIONING`, `CHARGE`, `CHARGE_AND_PRECONDITIONING`), and cabin preconditioning temperature (`preconditioningTemperature`).
* **Automatic Endpoint Routing:** The integration automatically inspects the vehicle code (e.g., `XBG2DE`) and dispatches calls to `/kcm/v1/vehicles/{vin}/ev/settings`.

### 2. KCM Pause-Resume Charging Endpoint (`/kcm/v1/vehicles/{vin}/charge/pause-resume`)
* Replaces legacy start/stop actions for Phase 2 vehicles with the native KCM payload:
  * Resume: `{"data": {"type": "ChargePauseResume", "attributes": {"action": "resume"}}}`
  * Pause: `{"data": {"type": "ChargePauseResume", "attributes": {"action": "pause"}}}`

### 3. KCM Target State-of-Charge Limits (`/kcm/v1/vehicles/{vin}/soc-levels`)
* Full support for minimum SoC (`socMin`) and target SoC (`socTarget`) via Home Assistant `number` entities.

### 4. Modern OIDC Bearer Token Authentication & Auto-Refresh
* Newer versions of the My Dacia and My Renault mobile apps communicate with `https://api-wired-prod-1-euw1.wrd-aws.com` using OpenID Connect (`Authorization: Bearer <oidc_access_token>`) issued by Gigya's OIDC OP.
* **Dual Auth Mode:** Supports direct OIDC `refresh_token` login or standard username/password login.
* **Automatic Token Refresh:** Background polling coordinators intercept `HTTP 401 Unauthorized` responses and automatically exchange the `refresh_token` before retrying the request, preventing coordinator lockouts.
* **Dual-Header Patch:** Kamereon requests transmit both `Authorization: Bearer <token>` and `x-gigya-id_token: <token>` to seamlessly authenticate with both legacy and new microservices.

---

## Supported Entity Platforms

| Platform | Entity / Description |
| :--- | :--- |
| **`climate`** | `climate.<vehicle>_hvac` — Cabin preconditioning control with target temperature adjustment (`16°C` to `26°C`). |
| **`switch`** | `switch.<vehicle>_departure_program_1` .. `5` — Enable/disable individual weekly departure programs.<br>`switch.<vehicle>_preconditioning_heated_strg_wheel` — Enable steering wheel heating during preconditioning.<br>`switch.<vehicle>_preconditioning_heated_left_seat` — Enable left seat heating during preconditioning.<br>`switch.<vehicle>_preconditioning_heated_right_seat` — Enable right seat heating during preconditioning. |
| **`time`** | `time.<vehicle>_charge_time_start` — Scheduled charge start time (`HH:MM`). |
| **`number`** | `number.<vehicle>_charge_limit_min` — Minimum battery charge level (%).<br>`number.<vehicle>_charge_limit_target` — Target battery charge limit (%). |
| **`select`** | `select.<vehicle>_charge_mode` — Charging mode (`always`, `always_charging`, `schedule_mode`). |
| **`button`** | `button.<vehicle>_start_air_conditioner` — Start immediate HVAC preconditioning.<br>`button.<vehicle>_stop_air_conditioner` — Cancel HVAC preconditioning.<br>`button.<vehicle>_start_charge` — Start / resume battery charging.<br>`button.<vehicle>_stop_charge` — Stop / pause battery charging.<br>`button.<vehicle>_clear_ev_schedules` — Wipe all scheduled heating/charging programs.<br>`button.<vehicle>_refresh_location` — Request updated GPS vehicle coordinates. |
| **`sensor`** | `sensor.<vehicle>_battery_level` — State of charge (%).<br>`sensor.<vehicle>_battery_autonomy` — Remaining range (km).<br>`sensor.<vehicle>_charging_status` — Real-time charging state.<br>`sensor.<vehicle>_ev_programs_count` — Configured schedule count with full JSON programs in attributes.<br>`sensor.<vehicle>_preconditioning_temperature` — Configured preconditioning target temperature.<br>`sensor.<vehicle>_ev_settings_last_update` — Last timestamp reported by the vehicle gateway. |
| **`binary_sensor`** | `binary_sensor.<vehicle>_charging` — True when vehicle battery is actively charging.<br>`binary_sensor.<vehicle>_plugged_in` — True when vehicle is connected to an EVSE cable. |
| **`device_tracker`**| `device_tracker.<vehicle>_location` — GPS coordinates and tracker state. |

---

## Home Assistant Services

### `renault.ev_set_schedules`
Program departure preconditioning and charging routines directly on KCM vehicles.

```yaml
action: renault.ev_set_schedules
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
  preconditioning_temperature: 21.0
  programs:
    - programActivationStatus: true
      programType: PRECONDITIONING
      programDepartureTime: "07:30"
      programActivationMonday: true
      programActivationTuesday: true
      programActivationWednesday: true
      programActivationThursday: true
      programActivationFriday: true
      programActivationSaturday: false
      programActivationSunday: false
```

*Shorthand day list format is also accepted:*
```yaml
action: renault.ev_set_schedules
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
  programs:
    - activated: true
      program_type: PRECONDITIONING
      departure_time: "10:00"
      days: ["fri"]
```

### `renault.ev_clear_schedules`
Clears all scheduled heating and charging departure programs on the vehicle.

```yaml
action: renault.ev_clear_schedules
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
```

### `renault.charge_start` and `renault.charge_stop`
Start or stop charging. Automatically uses `/kcm/v1/vehicles/{vin}/charge/pause-resume` for Phase 2 vehicles.

```yaml
action: renault.charge_start
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
```

```yaml
action: renault.charge_stop
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
```

### `renault.ac_start` and `renault.ac_cancel`
Immediately trigger or cancel preconditioning.

```yaml
action: renault.ac_start
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
  temperature: 21.0
```

```yaml
action: renault.ac_cancel
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
```

### `renault.refresh_location`, `renault.sound_horn`, `renault.flash_lights`
```yaml
action: renault.refresh_location
data:
  vehicle: <YOUR_VEHICLE_DEVICE_ID>
```

---

## Installation

### Via HACS (Recommended)
1. Open **HACS** -> **Integrations** -> Menu (`⋮`) -> **Custom repositories**.
2. Add repository URL: `https://github.com/marcohald/ha-renault-mydacia` with Category: **Integration**.
3. Click **Download**, then restart Home Assistant.
4. Go to **Settings** -> **Devices & Services** -> **Add Integration** -> Search for **Renault / My Dacia**.

### Manual Installation
1. Copy the `custom_components/renault` folder into your Home Assistant directory: `<config_dir>/custom_components/renault`.
2. Restart Home Assistant.
3. Add the integration from **Settings** -> **Devices & Services**.

---

## Running Unit Tests

The repository includes a standalone test suite with full mocking for external dependencies:

```bash
pip install pytest pytest-asyncio aiohttp marshmallow
python3 -m pytest tests/ -v
```

---

## Privacy Notice
This integration contains no hardcoded private credentials, tokens, account identifiers, or vehicle identification numbers (VINs). All authentication credentials and vehicle identifiers are configured securely within your local Home Assistant instance.
