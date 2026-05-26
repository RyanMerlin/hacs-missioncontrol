"""Global pytest fixtures for edgeplane-homeassistant tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def ep_url() -> str:
    return "http://edgeplane:8008"


@pytest.fixture
def sa_token() -> str:
    return "ep_session_abc123"


@pytest.fixture
def mock_config_entry_data(ep_url, sa_token):
    return {
        "ep_url": ep_url,
        "sa_token": sa_token,
        "agent_name": "home-assistant",
        "capabilities": ["home_control.light", "notify"],
        "mission_id": "test-mission-id",
        "agent_id": "test-agent-id",
    }
