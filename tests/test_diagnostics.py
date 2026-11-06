"""Tests for Renault integration diagnostics redaction."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from custom_components.renault.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics_redacts_sensitive_fields():
    """Verify diagnostics masks private tokens, credentials, vin, and coordinates."""
    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Renault Account"
    entry.data = {
        "username": "secret_user@example.com",
        "password": "supersecretpassword",
        "vin": "VF1SECRET12345678",
        "oidc_access_token": "secret_oidc_access_jwt",
        "oidc_refresh_token": "secret_oidc_refresh_token",
        "kamereon_account_id": "account-1234",
        "locale": "de_DE",
    }
    entry.runtime_data = MagicMock()
    entry.runtime_data.vehicles = {}

    result = await async_get_config_entry_diagnostics(hass, entry)
    redacted_data = result["entry"]["data"]

    # Check that sensitive keys are redacted
    assert redacted_data["username"] == "**REDACTED**"
    assert redacted_data["password"] == "**REDACTED**"
    assert redacted_data["vin"] == "**REDACTED**"
    assert redacted_data["oidc_access_token"] == "**REDACTED**"
    assert redacted_data["oidc_refresh_token"] == "**REDACTED**"
    assert redacted_data["kamereon_account_id"] == "**REDACTED**"

    # Non-sensitive keys remain untouched
    assert redacted_data["locale"] == "de_DE"

    # Confirm key presence in TO_REDACT set
    assert "gpsLatitude" in TO_REDACT
    assert "gpsLongitude" in TO_REDACT
    assert "radioCode" in TO_REDACT
