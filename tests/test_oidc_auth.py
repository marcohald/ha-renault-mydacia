"""Tests for OIDC authentication, token refresh, and request patching."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from renault_api.exceptions import NotAuthenticatedException
from custom_components.renault.oidc_auth import (
    MYDACIA_WIRED_API_KEY,
    kamereon_request_with_bearer,
)


@pytest.mark.asyncio
async def test_kamereon_request_with_bearer_headers():
    """Test that kamereon_request_with_bearer injects required headers."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.url = "https://api.example.com/kcm/v1/vehicles/test/ev/settings"
    mock_response.text.return_value = '{"commandId": "123"}'

    mock_session = MagicMock()
    mock_session.request.return_value.__aenter__.return_value = mock_response

    mock_schema = MagicMock()
    mock_schema.loads.return_value = MagicMock()

    await kamereon_request_with_bearer(
        websession=mock_session,
        method="POST",
        url="https://api.example.com/kcm/v1/vehicles/test/ev/settings",
        api_key=MYDACIA_WIRED_API_KEY,
        gigya_jwt="secret_token",
        params={},
        json={"chargeModeRq": "SCHEDULED"},
        schema=mock_schema,
    )

    mock_session.request.assert_called_once()
    _, kwargs = mock_session.request.call_args
    headers = kwargs["headers"]

    assert headers["Authorization"] == "Bearer secret_token"
    assert headers["x-gigya-id_token"] == "secret_token"
    assert headers["apikey"] == MYDACIA_WIRED_API_KEY
    assert headers["Content-type"] == "application/json"


@pytest.mark.asyncio
async def test_kamereon_request_kca_content_type():
    """Test that KCA requests use application/vnd.api+json."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.url = "https://api.example.com/kca/car-adapter/v1/cars/test/hvac-status"
    mock_response.text.return_value = '{"data": {}}'

    mock_session = MagicMock()
    mock_session.request.return_value.__aenter__.return_value = mock_response

    mock_schema = MagicMock()
    mock_schema.loads.return_value = MagicMock()

    await kamereon_request_with_bearer(
        websession=mock_session,
        method="GET",
        url="https://api.example.com/kca/car-adapter/v1/cars/test/hvac-status",
        api_key=MYDACIA_WIRED_API_KEY,
        gigya_jwt="Bearer test_token",
        params={},
        schema=mock_schema,
    )

    _, kwargs = mock_session.request.call_args
    headers = kwargs["headers"]
    assert headers["Content-type"] == "application/vnd.api+json"


@pytest.mark.asyncio
async def test_kamereon_request_raises_not_authenticated_on_401():
    """Test that HTTP 401 raises NotAuthenticatedException."""
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.url = "https://api.example.com/kcm/test"
    mock_response.text.return_value = '{"error": "Unauthorized"}'

    mock_session = MagicMock()
    mock_session.request.return_value.__aenter__.return_value = mock_response

    with pytest.raises(NotAuthenticatedException):
        await kamereon_request_with_bearer(
            websession=mock_session,
            method="GET",
            url="https://api.example.com/kcm/test",
            api_key=MYDACIA_WIRED_API_KEY,
            gigya_jwt="expired_token",
            params={},
        )
