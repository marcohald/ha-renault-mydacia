"""Tests for Renault coordinator token refresh behavior."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from renault_api.exceptions import NotAuthenticatedException
from custom_components.renault.coordinator import RenaultDataUpdateCoordinator


@pytest.mark.asyncio
async def test_coordinator_refreshes_token_on_not_authenticated():
    """Test coordinator catches NotAuthenticatedException, refreshes token, and retries."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.data = {"oidc_refresh_token": "valid_refresh_token"}
    hub = MagicMock()
    hub.is_throttled.return_value = False
    hub.async_refresh_oidc_token = AsyncMock(return_value=True)


    calls = 0

    async def sample_update():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise NotAuthenticatedException("Token expired")
        return {"status": "ok"}

    coordinator = RenaultDataUpdateCoordinator(
        hass,
        config_entry,
        hub,
        MagicMock(),
        name="test_coordinator",
        update_interval=MagicMock(),
        update_method=sample_update,
    )

    result = await coordinator._async_update_data()
    assert result == {"status": "ok"}
    assert calls == 2
    hub.async_refresh_oidc_token.assert_called_once_with(config_entry)
