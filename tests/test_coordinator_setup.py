import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.missioncontrol.const import DOMAIN
from custom_components.missioncontrol.coordinator import MCCoordinator


@pytest.fixture
def config_entry(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "mc_url": "http://missioncontrol:8008",
            "sa_token": "mcs_sa_test",
            "agent_name": "home-assistant",
            "capabilities": ["home_control.light", "notify"],
            "mission_id": "mission-123",
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def coordinator(hass, config_entry):
    return MCCoordinator(hass, config_entry)


def _make_session_mock(get_resp=None, post_resp=None):
    """Build a mock aiohttp.ClientSession context manager."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    if get_resp is not None:
        get_ctx = MagicMock()
        get_ctx.__aenter__ = AsyncMock(return_value=get_resp)
        get_ctx.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_ctx)
    if post_resp is not None:
        post_ctx = MagicMock()
        post_ctx.__aenter__ = AsyncMock(return_value=post_resp)
        post_ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=post_ctx)
    return session


async def test_validate_token_raises_on_401(hass: HomeAssistant, coordinator):
    resp = MagicMock()
    resp.status = 401
    session = _make_session_mock(get_resp=resp)
    with patch("aiohttp.ClientSession", return_value=session):
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._validate_token()


async def test_enroll_agent_stores_agent_id(hass: HomeAssistant, coordinator):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value={
        "id": "agent-abc",
        "agent_public_id": "home-assistant-abc123",
        "home_mission_id": "mission-123",
    })
    session = _make_session_mock(post_resp=resp)
    with patch("aiohttp.ClientSession", return_value=session):
        await coordinator._enroll_agent()
    assert coordinator._agent_id == "agent-abc"
    assert coordinator._agent_public_id == "home-assistant-abc123"


async def test_heartbeat_silent_on_client_error(hass: HomeAssistant, coordinator):
    coordinator._agent_id = "agent-abc"
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(side_effect=Exception("network error"))
    with patch("aiohttp.ClientSession", return_value=session):
        # Should not raise
        await coordinator._heartbeat()
