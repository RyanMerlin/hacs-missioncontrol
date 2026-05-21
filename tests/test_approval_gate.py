import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.missioncontrol.const import DOMAIN
from custom_components.missioncontrol.coordinator import MCCoordinator
from custom_components.missioncontrol.models import HaTaskPayload


@pytest.fixture
def coordinator(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={
        "mc_url": "http://mc:8008", "sa_token": "mcs_sa_test",
        "agent_name": "home-assistant", "capabilities": ["notify"],
        "mission_id": "m1", "agent_id": "a1",
    })
    entry.add_to_hass(hass)
    return MCCoordinator(hass, entry)


@pytest.fixture
def approval_payload():
    return HaTaskPayload.from_json(json.dumps({
        "domain": "notify", "service": "mobile_app",
        "data": {
            "message": "Approve?",
            "actions": [
                {"action": "APPROVE", "title": "✓ Approve"},
                {"action": "REJECT", "title": "✗ Reject"},
            ],
        },
    }))


async def test_approve_path_completes_task(hass, coordinator, approval_payload):
    coordinator._complete_task = AsyncMock()
    coordinator._fail_task = AsyncMock()

    async def send_notification_and_fire(*args, **kwargs):
        hass.bus.async_fire(
            "mobile_app_notification_action", {"action": "APPROVE"}
        )

    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock,
               side_effect=send_notification_and_fire):
        await coordinator._execute_approval_gate(approval_payload, "task-1", "lease-1")

    coordinator._complete_task.assert_awaited_once_with("task-1", "lease-1")
    coordinator._fail_task.assert_not_awaited()


async def test_reject_path_fails_task(hass, coordinator, approval_payload):
    coordinator._complete_task = AsyncMock()
    coordinator._fail_task = AsyncMock()

    async def send_notification_and_fire(*args, **kwargs):
        hass.bus.async_fire(
            "mobile_app_notification_action", {"action": "REJECT"}
        )

    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock,
               side_effect=send_notification_and_fire):
        await coordinator._execute_approval_gate(approval_payload, "task-2", "lease-2")

    coordinator._fail_task.assert_awaited_once()
    args = coordinator._fail_task.call_args[0]
    assert "Rejected" in args[2]


async def test_timeout_fails_task(hass, coordinator, approval_payload):
    coordinator._complete_task = AsyncMock()
    coordinator._fail_task = AsyncMock()

    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            await coordinator._execute_approval_gate(approval_payload, "task-3", "lease-3")

    coordinator._fail_task.assert_awaited_once()
    args = coordinator._fail_task.call_args[0]
    assert "timeout" in args[2].lower()
