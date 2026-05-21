from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.missioncontrol.const import DOMAIN


@pytest.fixture
def mock_mc_healthy():
    """MC responds 200 to /health and returns a mission on POST /missions."""
    with patch(
        "custom_components.missioncontrol.config_flow.MCClient.validate_and_create_mission",
        new_callable=AsyncMock,
        return_value="test-mission-id",
    ) as mock:
        yield mock


@pytest.fixture
def mock_mc_auth_fail():
    with patch(
        "custom_components.missioncontrol.config_flow.MCClient.validate_and_create_mission",
        new_callable=AsyncMock,
        side_effect=Exception("401 Unauthorized"),
    ) as mock:
        yield mock


async def test_step1_shows_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "mc_url" in result["data_schema"].schema
    assert "sa_token" in result["data_schema"].schema


async def test_step1_invalid_token_shows_error(hass: HomeAssistant, mock_mc_auth_fail):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"mc_url": "http://missioncontrol:8008", "sa_token": "mcs_sa_bad"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_step1_valid_proceeds_to_step2(hass: HomeAssistant, mock_mc_healthy):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"mc_url": "http://missioncontrol:8008", "sa_token": "mcs_sa_good"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "agent"


async def test_step2_creates_entry(hass: HomeAssistant, mock_mc_healthy):
    with patch("custom_components.missioncontrol.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"mc_url": "http://missioncontrol:8008", "sa_token": "mcs_sa_good"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"agent_name": "my-ha", "capabilities": ["home_control.light", "notify"]},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["mission_id"] == "test-mission-id"
    assert result["data"]["agent_name"] == "my-ha"
    assert "home_control.light" in result["data"]["capabilities"]
