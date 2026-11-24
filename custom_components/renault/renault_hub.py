"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations


import asyncio
from collections.abc import Callable
import contextlib
from datetime import datetime, timedelta
import logging
from time import time
from typing import TYPE_CHECKING

import aiohttp
from renault_api.const import CONF_KAMEREON_APIKEY
from renault_api.credential import Credential, JWTCredential
from renault_api.exceptions import NotAuthenticatedException
from renault_api.gigya import GIGYA_JWT
from renault_api.gigya.exceptions import (
    GigyaException,
    InvalidCredentialsException,
    PendingTwoFactorAuthenticationException,
)
from renault_api.gigya.models import GigyaTfaEmail
from renault_api.kamereon.exceptions import (
    KamereonResponseException,
    QuotaLimitException,
)
from renault_api.kamereon.models import KamereonVehiclesLink
from renault_api.renault_account import RenaultAccount
from renault_api.renault_client import RenaultClient

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    COOLING_UPDATES_SECONDS,
    MAX_COOLING_UPDATES_SECONDS,
    DOMAIN,
    MAX_CALLS_PER_HOURS,
    RenaultConfigurationKeys,
)
from .coordinator import RenaultVehicleListCoordinator
from .oidc_auth import (
    MYDACIA_WIRED_API_KEY,
    OIDC_DEFAULT_CLIENT_ID,
    OIDC_DEFAULT_TOKEN_URL,
    install_kamereon_bearer_patch,
    refresh_oidc_access_token,
)
from .renault_vehicle import COORDINATORS, RenaultVehicleProxy

if TYPE_CHECKING:
    from . import RenaultConfigEntry

LOGGER = logging.getLogger(__name__)

VEHICLES_THROTTLE_KEY = "vehicles"


async def _get_filtered_vehicles(account: RenaultAccount) -> list[KamereonVehiclesLink]:
    """Get the vehicles, filtering out those with missing details."""
    vehicles = await account.get_vehicles()
    return await _filter_vehicles_with_details(
        account, vehicles.vehicleLinks or [], set()
    )


async def _filter_vehicles_with_details(
    account: RenaultAccount,
    vehicle_links: list[KamereonVehiclesLink],
    missing_details_vins: set[str | None],
) -> list[KamereonVehiclesLink]:
    """Filter out the vehicles with missing details.

    The vehicle list sometimes omits the details, so they are requested
    separately. They may still be missing for new purchases, or due to an
    issue with the Renault servers. A warning is logged once for each vehicle,
    `missing_details_vins` keeps track of the vehicles already logged.
    """
    result: list[KamereonVehiclesLink] = []
    for link in vehicle_links:
        if link.vehicleDetails is None and link.vin:
            vehicle = await account.get_api_vehicle(link.vin)
            with contextlib.suppress(KamereonResponseException):
                link.vehicleDetails = await vehicle.get_details()
        if link.vehicleDetails is None:
            if link.vin in missing_details_vins:
                LOGGER.debug("Ignoring vehicle with missing details: %s", link.vin)
            else:
                LOGGER.warning("Ignoring vehicle with missing details: %s", link.vin)
                missing_details_vins.add(link.vin)
            continue
        result.append(link)
    return result


def _get_scan_interval(num_call_per_scan: int) -> timedelta:
    """Get the scan interval that keeps the calls within the hourly limit."""
    # One call per hour is kept for the vehicle list.
    return timedelta(seconds=(3600 * num_call_per_scan) / (MAX_CALLS_PER_HOURS - 1))


class RenaultHub:
    """Handle account communication with Renault servers."""

    def __init__(self, hass: HomeAssistant, locale: str) -> None:
        """Initialise proxy."""
        install_kamereon_bearer_patch()
        self._hass = hass
        self._websession = async_get_clientsession(self._hass)
        self._client = RenaultClient(
            websession=self._websession, locale=locale
        )
        self._account: RenaultAccount | None = None
        self._config_entry: RenaultConfigEntry | None = None
        self._vehicles: dict[str, RenaultVehicleProxy] = {}
        self._vehicle_listeners: list[Callable[[RenaultVehicleProxy], None]] = []
        self._vehicles_lock = asyncio.Lock()
        self._missing_details_vins: set[str | None] = set()

        self._got_throttled_at_time: float | None = None

    @property
    def login_token(self) -> str | None:
        """Return the Gigya login token obtained from a successful login."""
        return self._client.session.login_token

    @property
    def device_ids(self) -> dict[str, str]:
        """Return the Gigya device ids remembered after two-factor authentication."""
        return self._client.session.device_ids

    def set_device_ids(self, device_ids: dict[str, str]) -> None:
        """Restore Gigya device ids, so a remembered device skips two-factor auth."""
        self._client.session.set_device_ids(device_ids)

    # --- API quota handling -------------------------------------------------
    # Renault enforces the quota per endpoint (e.g. `location` can be
    # "overloaded" while `battery-status` still answers), so every endpoint
    # gets its own pause. VEHICLES_THROTTLE_KEY is used for the account
    # vehicle list (setup + vehicle list coordinator).

    @property
    def _throttle_states(self) -> dict[str, dict[str, float | int | None]]:
        """Throttle state per endpoint, shared across reloads/setup retries."""
        key = self._config_entry.entry_id if self._config_entry else str(id(self))
        store: dict[str, dict[str, dict[str, float | int | None]]] = (
            self._hass.data.setdefault(f"{DOMAIN}_throttle", {})
        )
        return store.setdefault(key, {})

    def _throttle_state(self, endpoint: str) -> dict[str, float | int | None]:
        return self._throttle_states.setdefault(endpoint, {"until": None, "count": 0})

    def throttled_until(self, endpoint: str = VEHICLES_THROTTLE_KEY) -> datetime | None:
        """Return when the quota pause of `endpoint` ends (None if not paused)."""
        until = self._throttle_state(endpoint)["until"]
        if until is None or time() >= float(until):
            return None
        return dt_util.utc_from_timestamp(float(until))

    def _quota_issue_id(self) -> str:
        key = self._config_entry.entry_id if self._config_entry else "unknown"
        return f"api_quota_exceeded_{key}"

    def set_throttled(self, endpoint: str = VEHICLES_THROTTLE_KEY) -> datetime:
        """Renault answered err.func.wired.overloaded for `endpoint`: pause it.

        The pause starts at COOLING_UPDATES_SECONDS and doubles with every
        consecutive throttle (no successful call in between), capped at
        MAX_COOLING_UPDATES_SECONDS. A repair issue lists the paused endpoints
        and when they will be retried.
        """
        state = self._throttle_state(endpoint)
        if state["until"] is not None and time() < float(state["until"]):
            return dt_util.utc_from_timestamp(float(state["until"]))
        state["count"] = int(state["count"] or 0) + 1
        pause = min(
            COOLING_UPDATES_SECONDS * 2 ** (int(state["count"]) - 1),
            MAX_COOLING_UPDATES_SECONDS,
        )
        state["until"] = time() + pause
        until = dt_util.utc_from_timestamp(float(state["until"]))
        LOGGER.warning(
            "Renault API quota exceeded for '%s' (err.func.wired.overloaded). "
            "Pausing this endpoint for %d min, next attempt at %s",
            endpoint,
            pause // 60,
            dt_util.as_local(until).strftime("%Y-%m-%d %H:%M"),
        )
        self._async_update_quota_issue()
        return until

    def is_throttled(self, endpoint: str = VEHICLES_THROTTLE_KEY) -> bool:
        """Check if `endpoint` is inside a quota pause."""
        state = self._throttle_state(endpoint)
        if state["until"] is None:
            return False
        if time() >= float(state["until"]):
            # Pause over: allow the next call. Keep `count` so that an immediate
            # new throttle doubles the pause; it is reset by set_api_ok().
            state["until"] = None
            self._async_update_quota_issue()
            return False
        return True

    def set_api_ok(self, endpoint: str = VEHICLES_THROTTLE_KEY) -> None:
        """A request to `endpoint` succeeded: reset its backoff."""
        state = self._throttle_states.get(endpoint)
        if state and (state["count"] or state["until"]):
            LOGGER.info("Renault API endpoint '%s' answers again", endpoint)
            del self._throttle_states[endpoint]
            self._async_update_quota_issue()

    @callback
    def _async_update_quota_issue(self) -> None:
        """Create/refresh or remove the repair warning listing paused endpoints."""
        now = time()
        paused = sorted(
            (float(st["until"]), name)
            for name, st in self._throttle_states.items()
            if st["until"] is not None and now < float(st["until"])
        )
        if not paused:
            ir.async_delete_issue(self._hass, DOMAIN, self._quota_issue_id())
            return
        lines = "\n".join(
            f"- `{name}`: "
            + dt_util.as_local(dt_util.utc_from_timestamp(until)).strftime("%d.%m.%Y %H:%M")
            for until, name in paused
        )
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            self._quota_issue_id(),
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="api_quota_exceeded",
            translation_placeholders={
                "endpoints": lines,
                "retry_at": dt_util.as_local(
                    dt_util.utc_from_timestamp(paused[-1][0])
                ).strftime("%d.%m.%Y %H:%M"),
            },
        )

    def _quota_not_ready(self) -> ConfigEntryNotReady:
        until = self.throttled_until()
        return ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="api_quota_exceeded",
            translation_placeholders={
                "retry_at": dt_util.as_local(until).strftime("%d.%m.%Y %H:%M")
                if until
                else "?"
            },
        )

    async def attempt_login(self, username: str, password: str) -> bool:
        """Attempt login to Renault servers."""
        try:
            await self._client.session.login(username, password)
        except InvalidCredentialsException as ex:
            LOGGER.error("Login to Renault failed: %s", ex.error_details)
        else:
            return True
        return False

    async def get_two_factor_auth_emails(self) -> list[GigyaTfaEmail]:
        """Get the email addresses registered for two-factor authentication."""
        return await self._client.session.get_two_factor_auth_emails()

    async def request_two_factor_auth_code(self, email_id: str) -> None:
        """Email a two-factor authentication code."""
        await self._client.session.request_two_factor_auth_code(email_id)

    async def complete_two_factor_auth(self, code: str) -> None:
        """Complete the pending login with the emailed code."""
        await self._client.session.complete_two_factor_auth(code)

    def _install_oidc_jwt_resolver(self, config_entry: RenaultConfigEntry) -> None:
        """Install an OIDC-aware _get_jwt method on the underlying RenaultSession."""
        session = self._client.session
        if CONF_KAMEREON_APIKEY not in session._credentials:
            session._credentials[CONF_KAMEREON_APIKEY] = Credential(MYDACIA_WIRED_API_KEY)
        if access_token := config_entry.data.get(
            RenaultConfigurationKeys.OIDC_ACCESS_TOKEN
        ):
            clean_token = str(access_token).removeprefix("Bearer ").strip()
            session._credentials[GIGYA_JWT] = JWTCredential(clean_token)

        orig_get_jwt = session._get_jwt

        async def _oidc_get_jwt() -> str:
            async with session._gigya_lock:
                jwt = session._credentials.get_value(GIGYA_JWT)
                if jwt:
                    return f"Bearer {jwt}"
                refresh_tok = config_entry.data.get(
                    RenaultConfigurationKeys.OIDC_REFRESH_TOKEN
                )
                if refresh_tok:
                    token_resp = await refresh_oidc_access_token(
                        self._websession,
                        refresh_token=str(refresh_tok),
                        client_id=str(
                            config_entry.data.get(
                                RenaultConfigurationKeys.OIDC_CLIENT_ID,
                                OIDC_DEFAULT_CLIENT_ID,
                            )
                        ),
                        token_url=str(
                            config_entry.data.get(
                                RenaultConfigurationKeys.OIDC_TOKEN_URL,
                                OIDC_DEFAULT_TOKEN_URL,
                            )
                        ),
                    )
                    new_access = token_resp["access_token"]
                    new_refresh = token_resp.get("refresh_token", refresh_tok)
                    session._credentials[GIGYA_JWT] = JWTCredential(new_access)
                    self._hass.config_entries.async_update_entry(
                        config_entry,
                        data={
                            **config_entry.data,
                            RenaultConfigurationKeys.OIDC_ACCESS_TOKEN: new_access,
                            RenaultConfigurationKeys.OIDC_REFRESH_TOKEN: new_refresh,
                        },
                    )
                    return f"Bearer {new_access}"
            return await orig_get_jwt()

        session._get_jwt = _oidc_get_jwt  # type: ignore[method-assign]

    async def async_refresh_oidc_token(
        self, config_entry: RenaultConfigEntry
    ) -> str | None:
        """Force refresh of the OIDC access token when a 401 is encountered."""
        session = self._client.session
        refresh_tok = config_entry.data.get(
            RenaultConfigurationKeys.OIDC_REFRESH_TOKEN
        )
        if not refresh_tok:
            return None
        async with session._gigya_lock:
            token_resp = await refresh_oidc_access_token(
                self._websession,
                refresh_token=str(refresh_tok),
                client_id=str(
                    config_entry.data.get(
                        RenaultConfigurationKeys.OIDC_CLIENT_ID,
                        OIDC_DEFAULT_CLIENT_ID,
                    )
                ),
                token_url=str(
                    config_entry.data.get(
                        RenaultConfigurationKeys.OIDC_TOKEN_URL,
                        OIDC_DEFAULT_TOKEN_URL,
                    )
                ),
            )
            new_access = token_resp["access_token"]
            new_refresh = token_resp.get("refresh_token", refresh_tok)
            session._credentials[GIGYA_JWT] = JWTCredential(new_access)
            self._hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    RenaultConfigurationKeys.OIDC_ACCESS_TOKEN: new_access,
                    RenaultConfigurationKeys.OIDC_REFRESH_TOKEN: new_refresh,
                },
            )
            return new_access

    async def async_login(self, config_entry: RenaultConfigEntry) -> None:
        """Log in with OIDC tokens, the stored Gigya login token, or fall back to password."""
        if config_entry.data.get(
            RenaultConfigurationKeys.OIDC_REFRESH_TOKEN
        ) or config_entry.data.get(RenaultConfigurationKeys.OIDC_ACCESS_TOKEN):
            self._install_oidc_jwt_resolver(config_entry)
            return

        if login_token := config_entry.data.get(RenaultConfigurationKeys.LOGIN_TOKEN):
            self._client.session.set_login_token(login_token)
            return
        self.set_device_ids(
            config_entry.data.get(RenaultConfigurationKeys.DEVICE_IDS, {})
        )
        try:
            login_success = await self.attempt_login(
                config_entry.data[RenaultConfigurationKeys.USERNAME],
                config_entry.data[RenaultConfigurationKeys.PASSWORD],
            )
        except PendingTwoFactorAuthenticationException as exc:
            # The code can only be entered in the reauth flow.
            raise NotAuthenticatedException from exc
        if login_success:
            # Persist the login token so the next setup can skip the password.
            self._hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    RenaultConfigurationKeys.LOGIN_TOKEN: self.login_token,
                },
            )
        else:
            raise NotAuthenticatedException

    async def async_initialise(self, config_entry: RenaultConfigEntry) -> None:
        """Set up proxy."""
        self._config_entry = config_entry
        if self.is_throttled():
            # Still inside a quota pause: do not touch the API at all.
            raise self._quota_not_ready()

        await self.async_login(config_entry)

        account_id: str = config_entry.data[
            RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID
        ]

        self._account = await self._client.get_api_account(account_id)
        try:
            vehicles = await self._account.get_vehicles()
        except QuotaLimitException as err:
            self.set_throttled()
            raise self._quota_not_ready() from err
        self.set_api_ok()
        all_vehicle_links = vehicles.vehicleLinks or []
        vehicle_links = await _filter_vehicles_with_details(
            self._account, all_vehicle_links, self._missing_details_vins
        )
        # An empty list is more likely a server issue than all vehicles removed.
        if vins := {link.vin for link in all_vehicle_links if link.vin}:
            self._async_remove_stale_devices(config_entry, vins)
        if not vehicle_links:
            LOGGER.debug(
                "No valid vehicle details found for account_id: %s", account_id
            )
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_vehicle_details",
            )

        await self._async_add_vehicles(vehicle_links)

        vehicle_list = RenaultVehicleListCoordinator(
            self._hass, config_entry, self, self._account
        )
        vehicle_list.async_set_updated_data(all_vehicle_links)
        config_entry.async_on_unload(
            vehicle_list.async_add_listener(
                lambda: self._async_vehicle_list_updated(vehicle_list.data)
            )
        )

    async def _async_add_vehicles(
        self, vehicle_links: list[KamereonVehiclesLink]
    ) -> None:
        """Set up vehicles and adjust the scan interval of all vehicles."""
        assert self._account is not None
        assert self._config_entry is not None
        # Assume all coordinators until the endpoints of the new vehicles are checked.
        scan_interval = _get_scan_interval(
            sum(len(vehicle.coordinators) for vehicle in self._vehicles.values())
            + len(COORDINATORS) * len(vehicle_links)
        )

        device_registry = dr.async_get(self._hass)
        results = await asyncio.gather(
            *(
                self.async_initialise_vehicle(
                    vehicle_link,
                    self._account,
                    scan_interval,
                    self._config_entry,
                    device_registry,
                )
                for vehicle_link in vehicle_links
            ),
            return_exceptions=True,
        )
        self._async_update_scan_interval()
        for result in results:
            if isinstance(result, BaseException):
                raise result

    @callback
    def _async_update_scan_interval(self) -> None:
        """Set the scan interval of all vehicles from their active coordinators."""
        scan_interval = _get_scan_interval(
            sum(len(vehicle.coordinators) for vehicle in self._vehicles.values())
        )
        for vehicle in self._vehicles.values():
            vehicle.update_scan_interval(scan_interval)

    @callback
    def _async_vehicle_list_updated(
        self, vehicle_links: list[KamereonVehiclesLink]
    ) -> None:
        """Add and remove vehicles when the vehicle list changes."""
        # Listeners are also called with the previous list while throttled.
        if self.is_throttled():
            return
        if {link.vin for link in vehicle_links if link.vin} == set(self._vehicles):
            return
        assert self._config_entry is not None
        self._config_entry.async_create_background_task(
            self._hass,
            self._async_update_vehicles(vehicle_links),
            "renault_update_vehicles",
        )

    async def _async_update_vehicles(
        self, vehicle_links: list[KamereonVehiclesLink]
    ) -> None:
        """Add new vehicles and remove the vehicles no longer in the account."""
        assert self._account is not None
        assert self._config_entry is not None
        async with self._vehicles_lock:
            # An empty list is more likely a server issue than all vehicles removed.
            if vins := {link.vin for link in vehicle_links if link.vin}:
                self._async_remove_stale_devices(self._config_entry, vins)
                for vin in set(self._vehicles) - vins:
                    vehicle = self._vehicles.pop(vin)
                    for coordinator in vehicle.coordinators.values():
                        await coordinator.async_shutdown()
                self._async_update_scan_interval()

            try:
                new_vehicle_links = await _filter_vehicles_with_details(
                    self._account,
                    [
                        link
                        for link in vehicle_links
                        if link.vin and link.vin not in self._vehicles
                    ],
                    self._missing_details_vins,
                )
                if new_vehicle_links:
                    await self._async_add_vehicles(new_vehicle_links)
            except (ConfigEntryAuthFailed, NotAuthenticatedException):
                self._config_entry.async_start_reauth(self._hass)
            except (aiohttp.ClientError, TimeoutError, GigyaException) as err:
                LOGGER.debug(
                    "Failed to update the vehicles, retrying at the next check: %s",
                    err,
                )

    @callback
    def _async_remove_stale_devices(
        self, config_entry: RenaultConfigEntry, vins: set[str]
    ) -> None:
        """Remove the devices of vehicles no longer linked to the account."""
        device_registry = dr.async_get(self._hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            if not any(
                domain == DOMAIN and identifier in vins
                for domain, identifier in device_entry.identifiers
            ):
                device_registry.async_remove_device(device_entry.id)

    @callback
    def async_add_vehicle_listener(
        self, add_vehicle: Callable[[RenaultVehicleProxy], None]
    ) -> CALLBACK_TYPE:
        """Call add_vehicle for the current vehicles and each vehicle added later."""
        for vehicle in self._vehicles.values():
            add_vehicle(vehicle)
        self._vehicle_listeners.append(add_vehicle)
        return lambda: self._vehicle_listeners.remove(add_vehicle)

    async def async_initialise_vehicle(
        self,
        vehicle_link: KamereonVehiclesLink,
        renault_account: RenaultAccount,
        scan_interval: timedelta,
        config_entry: RenaultConfigEntry,
        device_registry: dr.DeviceRegistry,
    ) -> None:
        """Set up proxy."""
        assert vehicle_link.vin is not None
        assert vehicle_link.vehicleDetails is not None
        # Generate vehicle proxy
        vehicle = RenaultVehicleProxy(
            hass=self._hass,
            config_entry=config_entry,
            hub=self,
            vehicle=await renault_account.get_api_vehicle(vehicle_link.vin),
            details=vehicle_link.vehicleDetails,
            scan_interval=scan_interval,
        )
        await vehicle.async_initialise()
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=vehicle.device_info["identifiers"],
            manufacturer=vehicle.device_info.get("manufacturer"),
            name=vehicle.device_info.get("name"),
            model=vehicle.device_info.get("model"),
            model_id=vehicle.device_info.get("model_id"),
            sw_version=None,  # cleanup from PR #125399
        )
        self._vehicles[vehicle_link.vin] = vehicle
        for add_vehicle in self._vehicle_listeners:
            add_vehicle(vehicle)

    async def get_account_ids(self) -> list[str]:
        """Get Kamereon account ids."""
        accounts = []
        for account in await self._client.get_api_accounts():
            vehicle_links = await _get_filtered_vehicles(account)

            # Only add the account if it has linked vehicles.
            if vehicle_links:
                accounts.append(account.account_id)
        return accounts

    async def get_all_account_ids(self) -> list[str]:
        """Get all Kamereon account ids, including those without vehicles."""
        return [account.account_id for account in await self._client.get_api_accounts()]

    async def get_account_ids_for_vins(self, vins: set[str]) -> list[str]:
        """Get Kamereon account ids linked to any of the given vehicles."""
        accounts = []
        for account in await self._client.get_api_accounts():
            vehicle_links = await _get_filtered_vehicles(account)
            if any(link.vin in vins for link in vehicle_links):
                accounts.append(account.account_id)
        return accounts

    @property
    def vehicles(self) -> dict[str, RenaultVehicleProxy]:
        """Get list of vehicles."""
        return self._vehicles
