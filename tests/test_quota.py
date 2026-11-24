"""Tests for Renault API quota (err.func.wired.overloaded) handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from renault_api.kamereon.exceptions import QuotaLimitException

from custom_components.renault import renault_hub as hub_module
from custom_components.renault.const import (
    COOLING_UPDATES_SECONDS,
    MAX_COOLING_UPDATES_SECONDS,
)
from custom_components.renault.coordinator import RenaultDataUpdateCoordinator
from custom_components.renault.renault_hub import RenaultHub


class _Clock:
    """Controllable replacement for time.time()."""

    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def _mock_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hub_module, "RenaultClient", MagicMock())


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    c = _Clock()
    monkeypatch.setattr(hub_module, "time", c)
    return c


@pytest.fixture
def issues(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    ir = MagicMock()
    monkeypatch.setattr(hub_module, "ir", ir)
    return ir


@pytest.fixture
def hub() -> RenaultHub:
    hass = MagicMock()
    hass.data = {}
    h = RenaultHub(hass, "de_DE")
    entry = MagicMock()
    entry.entry_id = "entry1"
    h._config_entry = entry
    return h


def test_throttle_is_per_endpoint(hub: RenaultHub, clock: _Clock, issues: MagicMock) -> None:
    hub.set_throttled("location")
    assert hub.is_throttled("location")
    assert not hub.is_throttled("battery")
    assert not hub.is_throttled()  # vehicle list

    issues.async_create_issue.assert_called_once()
    kwargs = issues.async_create_issue.call_args.kwargs
    assert kwargs["translation_key"] == "api_quota_exceeded"
    assert "`location`" in kwargs["translation_placeholders"]["endpoints"]


def test_pause_expires_and_backoff_doubles(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    first = hub.set_throttled("location")
    assert (first.timestamp() - clock.now) == COOLING_UPDATES_SECONDS

    clock.now += COOLING_UPDATES_SECONDS
    assert not hub.is_throttled("location")
    issues.async_delete_issue.assert_called()  # nothing paused any more

    # Throttled again right after the pause: doubled
    second = hub.set_throttled("location")
    assert (second.timestamp() - clock.now) == 2 * COOLING_UPDATES_SECONDS

    # Capped at the maximum
    for _ in range(10):
        clock.now += MAX_COOLING_UPDATES_SECONDS
        assert not hub.is_throttled("location")
        last = hub.set_throttled("location")
    assert (last.timestamp() - clock.now) == MAX_COOLING_UPDATES_SECONDS


def test_repeated_throttle_during_pause_is_ignored(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    first = hub.set_throttled("location")
    clock.now += 10
    assert hub.set_throttled("location") == first
    assert issues.async_create_issue.call_count == 1


def test_success_resets_backoff_and_removes_issue(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    hub.set_throttled("location")
    clock.now += COOLING_UPDATES_SECONDS
    hub.set_api_ok("location")
    issues.async_delete_issue.assert_called()

    again = hub.set_throttled("location")
    assert (again.timestamp() - clock.now) == COOLING_UPDATES_SECONDS


def test_success_of_other_endpoint_keeps_pause(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    hub.set_throttled("location")
    hub.set_api_ok("battery")
    assert hub.is_throttled("location")


def test_state_survives_new_hub_instance(clock: _Clock, issues: MagicMock) -> None:
    """A reload/setup retry creates a new hub; the pause must be kept."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "entry1"
    h1 = RenaultHub(hass, "de_DE")
    h1._config_entry = entry
    h1.set_throttled()
    h2 = RenaultHub(hass, "de_DE")
    h2._config_entry = entry
    assert h2.is_throttled()


def _coordinator(hub: RenaultHub, update_method) -> RenaultDataUpdateCoordinator:
    config_entry = MagicMock()
    config_entry.data = {}
    return RenaultDataUpdateCoordinator(
        MagicMock(),
        config_entry,
        hub,
        MagicMock(),
        name="VIN123 location",
        update_interval=MagicMock(),
        update_method=update_method,
    )


@pytest.mark.asyncio
async def test_coordinator_pauses_endpoint_and_skips_api(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    calls = 0

    async def update():
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"lat": 1}
        raise QuotaLimitException("err.func.wired.overloaded")

    coord = _coordinator(hub, update)
    assert await coord._async_update_data() == {"lat": 1}
    coord.data = {"lat": 1}

    # Quota hit: keeps last data, endpoint paused
    assert await coord._async_update_data() == {"lat": 1}
    assert coord.assumed_state
    assert hub.is_throttled("location")
    assert calls == 2

    # While paused no API call is made
    assert await coord._async_update_data() == {"lat": 1}
    assert calls == 2

    # After the pause the API is asked again
    clock.now += COOLING_UPDATES_SECONDS
    await coord._async_update_data()
    assert calls == 3


@pytest.mark.asyncio
async def test_coordinator_unwraps_quota_from_wrapped_proxy_method(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    """with_error_wrapping turns QuotaLimitException into HomeAssistantError."""

    async def update():
        try:
            raise QuotaLimitException("err.func.wired.overloaded")
        except QuotaLimitException as err:
            raise HomeAssistantError("quota") from err

    coord = _coordinator(hub, update)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert hub.is_throttled("location")


@pytest.mark.asyncio
async def test_coordinator_success_clears_pause(
    hub: RenaultHub, clock: _Clock, issues: MagicMock
) -> None:
    async def update():
        return {"ok": True}

    hub.set_throttled("location")
    clock.now += COOLING_UPDATES_SECONDS
    coord = _coordinator(hub, update)
    await coord._async_update_data()
    assert "location" not in hub._throttle_states
