# Home Assistant Custom Integration: Renault / My Dacia (`KCM /ev/settings` Heating & Schedule Support)

This repository provides a drop-in Home Assistant custom component (`custom_components/renault`) based on [`homeassistant/components/renault`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/renault), extended with reverse-engineered support for **Phase 2 (`C1AH2` / `CVC` gateway) vehicles** such as the **2026 Dacia Spring Phase 2 (`XBG2DE`)**.

---

## What Was Added / Modified

1. **Unified KCM EV & Heating Schedule Endpoint (`/kamereon/kcm/v1/vehicles/{vin}/ev/settings`)**
   - On `C1AH2` / `CVC` vehicles (e.g., Dacia Spring `XBG2DE`), the legacy `/kamereon/kca/car-adapter/v1/cars/{vin}/hvac-settings` endpoint returns `HTTP 502` (`err.tech.vcps.ev.hvac-settings.error`).
   - Added [`ev_settings.py`](custom_components/renault/ev_settings.py) and registered `XBG2DE` in `renault_api.kamereon.models._VEHICLE_ENDPOINTS`.
   - Added the `ev_settings` coordinator to [`renault_vehicle.py`](custom_components/renault/renault_vehicle.py) (`get_ev_settings()` and `set_ev_settings()`).

2. **New & Updated Home Assistant Services ([`services.py`](custom_components/renault/services.py), [`services.yaml`](custom_components/renault/services.yaml))**
   - **`renault.ac_set_schedules` (Updated):** Automatically detects if the vehicle uses KCM `/ev/settings` (`vehicle.uses_kcm_ev_settings()`), converts standard Home Assistant `ac_set_schedules` day schedules into `PRECONDITIONING` programs (`PostEvSettingsBodySchema`), and posts them to `/kamereon/kcm/v1/vehicles/{vin}/ev/settings` while preserving any existing `CHARGE`-only programs.
   - **`renault.ev_set_schedules` (New):** Full control over KCM `/ev/settings` departure programs (`PRECONDITIONING`, `CHARGE`, or `CHARGE_AND_PRECONDITIONING`), `preconditioning_temperature`, `charge_mode_rq` (`SCHEDULED`, `SMARTCHARGING_OFFPEAK`, `V2G`), `charge_time_start`, and `charge_duration`.
   - **`renault.ev_clear_schedules` (New):** Clears all departure heating/charging programs (`programs: []`) on the vehicle.

3. **New Entities ([`sensor.py`](custom_components/renault/sensor.py), [`button.py`](custom_components/renault/button.py))**
   - `sensor.<vehicle>_ev_programs_count` — Number of configured departure programs, with full `programs`, `charge_mode_rq`, `charge_time_start`, `charge_duration`, and `preconditioning_temperature` in `extra_state_attributes`.
   - `sensor.<vehicle>_preconditioning_temperature` — Target preconditioning temperature (`°C`) reported by `/ev/settings`.
   - `sensor.<vehicle>_ev_settings_last_update` — Diagnostic timestamp of the last `/ev/settings` synchronization (`lastSettingsUpdateTimestamp`).
   - `button.<vehicle>_clear_ev_schedules` — One-tap button to clear all scheduled heating/charging programs.

4. **OIDC Bearer Token & Auto-Refresh Support ([`oidc_auth.py`](custom_components/renault/oidc_auth.py), [`renault_hub.py`](custom_components/renault/renault_hub.py), [`config_flow.py`](custom_components/renault/config_flow.py))**
   - Newer My Dacia / My Renault app versions authenticate against `https://api-wired-prod-1-euw1.wrd-aws.com` using `Authorization: Bearer <oidc_access_token>` (issued by `https://gigya-prod-eu1.idconnect.renaultgroup.com/oidc/op/v1.0/.../token`) instead of `x-gigya-id_token`.
   - Patches `renault_api.kamereon.request` to send both `Authorization: Bearer <token>` and `x-gigya-id_token: <token>`, and uses `Content-Type: application/json` for `/kcm/v1/vehicles/{vin}/ev/settings`.
   - Allows configuring the integration either with standard My Dacia / My Renault credentials or directly with an OIDC `refresh_token` / `access_token`.

---

## Installation in Home Assistant

### Option A: Via HACS (Custom Repository)
1. Open **HACS** in Home Assistant -> **Integrations** -> top-right menu (`⋮`) -> **Custom repositories**.
2. Add the URL of this repository and select category **Integration**.
3. Install **Renault / My Dacia (KCM EV & Heating Schedule Support)** and restart Home Assistant.

### Option B: Manual Copy
1. Copy the `custom_components/renault` folder into your Home Assistant `<config>/custom_components/renault` directory.
2. Restart Home Assistant.

---

## Example Service Calls

### 1. Schedule Preconditioning Only (No Charging) for Friday at 10:00 AM via `renault.ev_set_schedules`
```yaml
action: renault.ev_set_schedules
data:
  vehicle: <YOUR_DEVICE_ID>
  preconditioning_temperature: 21.0
  programs:
    - programActivationStatus: true
      programType: PRECONDITIONING
      programDepartureTime: "10:00"
      programActivationMonday: false
      programActivationTuesday: false
      programActivationWednesday: false
      programActivationThursday: false
      programActivationFriday: true
      programActivationSaturday: false
      programActivationSunday: false
```

*(Shorthand `days` list is also supported in `programs`:)*
```yaml
action: renault.ev_set_schedules
data:
  vehicle: <YOUR_DEVICE_ID>
  programs:
    - activated: true
      program_type: PRECONDITIONING
      departure_time: "07:30"
      days: ["mon", "tue", "wed", "thu", "fri"]
```

### 2. Clear All Heating / Charging Schedules via `renault.ev_clear_schedules`
```yaml
action: renault.ev_clear_schedules
data:
  vehicle: <YOUR_DEVICE_ID>
```

### 3. Legacy `renault.ac_set_schedules` (Automatically Routed to `/ev/settings`)
```yaml
action: renault.ac_set_schedules
data:
  vehicle: <YOUR_DEVICE_ID>
  schedules:
    - id: 1
      activated: true
      friday:
        readyAtTime: "T10:00Z"
```
