import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.missioncontrol.const import DOMAIN, WS_BACKOFF_INITIAL_S
from custom_components.missioncontrol.coordinator import MCCoordinator


@pytest.fixture
def coordinator(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={
        "mc_url": "http://missioncontrol:8008",
        "sa_token": "mcs_sa_test",
        "agent_name": "home-assistant",
        "capabilities": ["home_control.light"],
        "mission_id": "mission-123",
        "agent_id": "agent-456",
    })
    entry.add_to_hass(hass)
    return MCCoordinator(hass, entry)


class _AsyncIter:
    """Async iterator over a list of messages."""
    def __init__(self, messages):
        self._iter = iter(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def _make_ws_mock(messages):
    """Build a mock WebSocket that yields given messages then stops."""
    ws = MagicMock()
    ws.__aenter__ = AsyncMock(return_value=ws)
    ws.__aexit__ = AsyncMock(return_value=False)
    ws.__aiter__ = lambda self: _AsyncIter(messages)
    return ws


def _make_session_mock(ws_mock=None, ws_error=None):
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    if ws_error:
        session.ws_connect = MagicMock(side_effect=ws_error)
    elif ws_mock:
        session.ws_connect = MagicMock(return_value=ws_mock)
    return session


async def test_ws_backoff_increases_on_failure(hass, coordinator):
    """Backoff doubles each disconnect, caps at WS_BACKOFF_MAX_S."""
    sleep_calls = []

    async def fake_sleep(n):
        sleep_calls.append(n)
        if len(sleep_calls) >= 3:
            coordinator._shutdown = True

    session = _make_session_mock(ws_error=aiohttp.ClientError("refused"))
    with patch("aiohttp.ClientSession", return_value=session):
        with patch("asyncio.sleep", fake_sleep):
            await coordinator._ws_listen_loop()

    assert sleep_calls[0] == WS_BACKOFF_INITIAL_S      # 1
    assert sleep_calls[1] == WS_BACKOFF_INITIAL_S * 2  # 2
    assert sleep_calls[2] == WS_BACKOFF_INITIAL_S * 4  # 4


async def test_ws_backoff_resets_on_connect(hass, coordinator):
    """Backoff resets to initial value after a successful connection."""
    coordinator._backoff = 32  # simulate prior failures

    close_msg = MagicMock()
    close_msg.type = aiohttp.WSMsgType.CLOSED

    ws = _make_ws_mock([close_msg])
    session = _make_session_mock(ws_mock=ws)

    with patch("aiohttp.ClientSession", return_value=session):
        with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)):
            with pytest.raises(asyncio.CancelledError):
                await coordinator._ws_listen_loop()

    assert coordinator._backoff == WS_BACKOFF_INITIAL_S


async def test_ws_dispatches_task_available(hass, coordinator):
    """task_available message spawns _handle_task."""
    task_ids = []

    async def fake_handle(task_id):
        task_ids.append(task_id)

    coordinator._handle_task = fake_handle

    text_msg = MagicMock()
    text_msg.type = aiohttp.WSMsgType.TEXT
    text_msg.data = json.dumps({"type": "task_available", "task_id": "task-789", "kluster_id": "k1"})

    close_msg = MagicMock()
    close_msg.type = aiohttp.WSMsgType.CLOSED

    call_count = 0

    def session_factory(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        msgs = [text_msg, close_msg] if call_count == 1 else [close_msg]
        ws = _make_ws_mock(msgs)
        session = _make_session_mock(ws_mock=ws)
        # Shut down after second session so loop exits
        if call_count >= 2:
            coordinator._shutdown = True
        return session

    with patch("aiohttp.ClientSession", side_effect=session_factory):
        with patch("asyncio.sleep", AsyncMock()):
            await coordinator._ws_listen_loop()

    await asyncio.sleep(0)  # let spawned tasks run
    assert "task-789" in task_ids
