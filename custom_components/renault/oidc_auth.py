"""OIDC & Gigya Authentication Support for Renault/Dacia API Gateway."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from marshmallow.schema import Schema
from renault_api import kamereon
from renault_api.credential import JWTCredential
from renault_api.exceptions import NotAuthenticatedException
from renault_api.kamereon import models, schemas

_LOGGER = logging.getLogger(__name__)

OIDC_DEFAULT_TOKEN_URL = (
    "https://gigya-prod-eu1.idconnect.renaultgroup.com/oidc/op/v1.0/"
    "3_VgdkgtIRH3AdHvJm-cjV2ug2EFE0lxt0IJzMC4MFqZjFpn_GYFXVdNZ19L7wZX0N/token"
)
OIDC_DEFAULT_CLIENT_ID = "qiXX6GdXSgerKxYqvdAblK_M"
MYDACIA_WIRED_API_KEY = "lZeSKPcG18u3SI8AGE52lIQ5DfamawDo"

CONF_OIDC_ACCESS_TOKEN = "oidc_access_token"
CONF_OIDC_REFRESH_TOKEN = "oidc_refresh_token"
CONF_OIDC_CLIENT_ID = "oidc_client_id"
CONF_OIDC_TOKEN_URL = "oidc_token_url"


async def refresh_oidc_access_token(
    websession: aiohttp.ClientSession,
    refresh_token: str,
    client_id: str = OIDC_DEFAULT_CLIENT_ID,
    token_url: str = OIDC_DEFAULT_TOKEN_URL,
) -> dict[str, Any]:
    """Exchange an OIDC refresh_token for a fresh access_token (and rotated refresh_token)."""
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    async with websession.post(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ) as resp:
        resp_text = await resp.text()
        if resp.status != 200:
            _LOGGER.error(
                "OIDC token refresh failed (%s): %s", resp.status, resp_text
            )
            raise NotAuthenticatedException(
                f"OIDC token refresh failed ({resp.status}): {resp_text}"
            )
        return await resp.json()


async def kamereon_request_with_bearer(
    websession: aiohttp.ClientSession,
    method: str,
    url: str,
    api_key: str,
    gigya_jwt: str,
    params: dict[str, str],
    json: dict[str, Any] | None = None,
    schema: Schema | None = None,
    *,
    wrap_array_in: str | None = None,
) -> models.KamereonResponse:
    """Process Kamereon HTTP request supporting both OIDC Bearer tokens and legacy Gigya JWTs.

    Newer My Dacia / My Renault app versions (and `/kamereon/kcm/v1/vehicles/{vin}/ev/settings`)
    use `Authorization: Bearer <oidc_access_token>` and `application/json` (or `application/vnd.api+json`).
    We send both `Authorization: Bearer <token>` and `x-gigya-id_token: <token>` so that both
    OIDC tokens and legacy Gigya JWTs work seamlessly.
    """
    schema = schema or schemas.KamereonResponseSchema
    is_kcm_ev_settings = "/kcm/" in url and "/ev/settings" in url
    content_type = (
        "application/json" if is_kcm_ev_settings else "application/vnd.api+json"
    )
    bearer_val = (
        gigya_jwt
        if gigya_jwt.startswith("Bearer ")
        else f"Bearer {gigya_jwt}"
    )
    raw_token = gigya_jwt.removeprefix("Bearer ")

    headers = {
        "Content-type": content_type,
        "Accept": "application/json",
        "apikey": api_key,
    }
    if gigya_jwt.startswith("Bearer "):
        headers["Authorization"] = gigya_jwt
    else:
        headers["x-gigya-id_token"] = gigya_jwt
    async with websession.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json,
    ) as http_response:
        response_text = await http_response.text()
        _LOGGER.debug(
            "Received Kamereon response %s on %s to %s: %s",
            http_response.status,
            method,
            http_response.url,
            response_text,
        )
        if response_text.startswith("["):
            response_text = f'{{"{wrap_array_in or "items"}": {response_text}}}'

        kamereon_response: models.KamereonResponse = schema.loads(response_text)
        # Check for Kamereon error
        kamereon_response.raise_for_error_code()

        return kamereon_response


def install_kamereon_bearer_patch() -> None:
    """Patch `renault_api.kamereon.request` to include `Authorization: Bearer` header."""
    if getattr(kamereon.request, "_oidc_patched", False):
        return
    setattr(kamereon_request_with_bearer, "_oidc_patched", True)
    kamereon.request = kamereon_request_with_bearer  # type: ignore[assignment]
