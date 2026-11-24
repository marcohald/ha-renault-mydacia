"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations

from typing import Generic, TypeVar, Any
T = TypeVar('T', bound=Any)


import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from renault_api.exceptions import NotAuthenticatedException
from renault_api.kamereon.exceptions import (
    AccessDeniedException,
    KamereonResponseException,
    NotSupportedException,
    QuotaLimitException,
)
from renault_api.kamereon.models import (
    KamereonVehicleDataAttributes,
    KamereonVehiclesLink,
)
from renault_api.renault_account import RenaultAccount

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, VEHICLE_LIST_SCAN_INTERVAL, RenaultConfigurationKeys

if TYPE_CHECKING:
    from . import RenaultConfigEntry
    from .renault_hub import RenaultHub

_LOGGER = logging.getLogger(__name__)

# We have potentially 7 coordinators per vehicle
_PARALLEL_SEMAPHORE = asyncio.Semaphore(1)


async def _call_unwrapped(method: Callable[[], Awaitable[T]]) -> T:
    """Call an update method, re-raising the Renault error behind a HomeAssistantError.

    Proxy methods decorated with `with_error_wrapping` turn Renault errors into
    HomeAssistantError (useful for actions). For polling we need the original
    exception (e.g. QuotaLimitException) to apply the right handling.
    """
    try:
        return await method()
    except HomeAssistantError as err:
        if isinstance(err.__cause__, (KamereonResponseException, NotAuthenticatedException)):
            raise err.__cause__ from err
        raise


class RenaultDataUpdateCoordinator(DataUpdateCoordinator[T], Generic[T]):
    """Handle vehicle communication with Renault servers."""

    config_entry: RenaultConfigEntry
    update_method: Callable[[], Awaitable[T]]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RenaultConfigEntry,
        hub: RenaultHub,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: timedelta,
        update_method: Callable[[], Awaitable[T]],
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
        )
        self.config_entry = config_entry

        self.access_denied = False
        self.not_supported = False
        self.assumed_state = False

        self._has_already_worked = False
        self._hub = hub
        # name is "<vin> <coordinator key>"; quota pauses are tracked per endpoint
        self.throttle_key = name.rsplit(" ", 1)[-1]


    @override
    async def _async_update_data(self) -> T:
        """Fetch the latest data from the source."""

        if self._hub.is_throttled(self.throttle_key):
            if not self._has_already_worked:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="throttled",
                )
            # we have been throttled and decided to cooldown
            # so do not count this update as an error
            # coordinator. last_update_success should still be ok
            self.logger.debug("Renault hub currently throttled: scan skipped")
            self.assumed_state = True
            return self.data

        try:
            async with _PARALLEL_SEMAPHORE:
                data = await _call_unwrapped(self.update_method)

        except AccessDeniedException as err:
            # This can mean both a temporary error or a permanent error. If it has
            # worked before, make it temporary, if not disable the update interval.
            if not self._has_already_worked:
                self.update_interval = None
                self.access_denied = True
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="endpoint_denied",
            ) from err

        except QuotaLimitException as err:
            # Quota exhausted for this endpoint: pause it (other endpoints keep polling)
            self._hub.set_throttled(self.throttle_key)
            if self._has_already_worked:
                self.assumed_state = True
                return self.data

            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="throttled",
            ) from err

        except NotSupportedException as err:
            # Disable because the vehicle does not support this Renault endpoint.
            self.update_interval = None
            self.not_supported = True
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="endpoint_not_supported",
            ) from err

        except NotAuthenticatedException as err:
            if self.config_entry.data.get(RenaultConfigurationKeys.OIDC_REFRESH_TOKEN):
                try:
                    await self._hub.async_refresh_oidc_token(self.config_entry)
                    async with _PARALLEL_SEMAPHORE:
                        return await self.update_method()
                except Exception:
                    pass
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_expired",
            ) from err

        except KamereonResponseException as err:
            # Other Renault errors.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

        self._has_already_worked = True
        self.assumed_state = False
        self._hub.set_api_ok(self.throttle_key)
        return data

    @override
    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Contrary to base implementation, we are not raising ConfigEntryNotReady
        but only updating the `access_denied` and `not_supported` flags.
        """
        await self._async_refresh(log_failures=False, raise_on_auth_failed=True)


class RenaultVehicleListCoordinator(DataUpdateCoordinator[list[KamereonVehiclesLink]]):
    """Handle the list of vehicles linked to the Kamereon account."""

    config_entry: RenaultConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RenaultConfigEntry,
        hub: RenaultHub,
        account: RenaultAccount,
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{account.account_id} vehicles",
            update_interval=VEHICLE_LIST_SCAN_INTERVAL,
        )
        self.config_entry = config_entry
        self._account = account
        self._hub = hub

    @override
    async def _async_update_data(self) -> list[KamereonVehiclesLink]:
        """Fetch the latest vehicle list from the source."""
        if self._hub.is_throttled():
            return self.data

        try:
            async with _PARALLEL_SEMAPHORE:
                vehicles = await self._account.get_vehicles()

        except QuotaLimitException as err:
            self._hub.set_throttled()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="throttled",
            ) from err

        except NotAuthenticatedException as err:
            if self.config_entry.data.get(RenaultConfigurationKeys.OIDC_REFRESH_TOKEN):
                _LOGGER.info(
                    "OIDC access token expired during vehicle list poll; attempting auto-refresh"
                )
                try:
                    refreshed = await self._hub.async_refresh_oidc_token(self.config_entry)
                    if refreshed:
                        async with _PARALLEL_SEMAPHORE:
                            vehicles = await self._account.get_vehicles()
                            return vehicles.vehicleLinks or []
                except Exception as refresh_err:
                    _LOGGER.warning(
                        "Auto-refresh of OIDC token failed during vehicle list poll: %s",
                        refresh_err,
                    )
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_expired",
            ) from err

        except KamereonResponseException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

        self._hub.set_api_ok()
        return vehicles.vehicleLinks or []
