"""Constants for the Renault component."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN = "renault"


class RenaultConfigurationKeys:
    """Configuration keys."""

    DEVICE_IDS: Final = "device_ids"
    KAMEREON_ACCOUNT_ID: Final = "kamereon_account_id"
    LOCALE: Final = "locale"
    LOGIN_TOKEN: Final = "login_token"
    OIDC_ACCESS_TOKEN: Final = "oidc_access_token"
    OIDC_CLIENT_ID: Final = "oidc_client_id"
    OIDC_REFRESH_TOKEN: Final = "oidc_refresh_token"
    OIDC_TOKEN_URL: Final = "oidc_token_url"
    PASSWORD: Final = "password"
    USERNAME: Final = "username"


# normal number of allowed calls per hour to the API
# for a single car and the 7 coordinator, it is a scan every 7mn
MAX_CALLS_PER_HOURS = 60

# Interval to check the account for added or removed vehicles
VEHICLE_LIST_SCAN_INTERVAL = timedelta(hours=1)

# If throttled time to pause the updates, in seconds
COOLING_UPDATES_SECONDS = 60 * 15  # 15 minutes

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]
