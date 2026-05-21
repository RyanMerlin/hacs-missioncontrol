"""MCCoordinator — WebSocket-primary coordinator for MissionControl."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    APPROVAL_TIMEOUT_S, CONF_AGENT_ID, CONF_AGENT_NAME, CONF_CAPABILITIES,
    CONF_MC_URL, CONF_MISSION_ID, CONF_SA_TOKEN, DOMAIN,
    HEARTBEAT_INTERVAL_S, PATH_AGENT_HEARTBEAT, PATH_AGENT_NOTIFY,
    PATH_AGENT_STATUS, PATH_AUTH_WHOAMI, PATH_ENROLL, PATH_HEALTH, PATH_TASK,
    PATH_TASK_CLAIM, PATH_TASK_COMPLETE, PATH_TASK_FAIL,
    PATH_TASK_HEARTBEAT, PATH_TASK_PROGRESS,
    TASK_HEARTBEAT_INTERVAL_S, WS_BACKOFF_INITIAL_S, WS_BACKOFF_MAX_S,
)
from .models import HaTaskPayload, MCAgentState

_LOGGER = logging.getLogger(__name__)


class MCCoordinator(DataUpdateCoordinator):
    """Manages MC connection, heartbeat, WebSocket task stream, and task execution."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=300)
        )
        self._entry = entry
        self._base_url: str = entry.data[CONF_MC_URL].rstrip("/")
        self._token: str = entry.data[CONF_SA_TOKEN]
        self._agent_name: str = entry.data[CONF_AGENT_NAME]
        self._capabilities: list[str] = entry.data[CONF_CAPABILITIES]
        self._mission_id: str = entry.data[CONF_MISSION_ID]
        self._agent_id: str | None = entry.data.get(CONF_AGENT_ID)
        self._backoff: int = WS_BACKOFF_INITIAL_S
        self._shutdown: bool = False
        self._ws_task: asyncio.Task | None = None
        self.state = MCAgentState()

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _url(self, path_template: str, **kwargs: str) -> str:
        return self._base_url + path_template.format(**kwargs)

    async def _async_setup(self) -> None:
        """One-time setup: validate token, enroll, start loops."""
        await self._validate_token()
        await self._enroll_agent()
        self._entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._heartbeat,
                timedelta(seconds=HEARTBEAT_INTERVAL_S),
            )
        )
        self._ws_task = self.hass.async_create_task(self._ws_listen_loop())
        self._entry.async_on_unload(self._cancel_ws)
        await self._set_status("online")

    def _cancel_ws(self) -> None:
        self._shutdown = True
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()

    async def _validate_token(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self._url(PATH_AUTH_WHOAMI), headers=self._headers
            ) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Invalid MC token")
                resp.raise_for_status()

    async def _enroll_agent(self) -> None:
        payload = {
            "agent_name": self._agent_name,
            "capabilities": self._capabilities,
            "labels": {
                "ha_version": str(getattr(self.hass.config, "version", "unknown")),
                "node": "home-assistant",
            },
            "runtime_kind": "custom",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._url(PATH_ENROLL, mission_id=self._mission_id),
                json=payload,
                headers=self._headers,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                self._agent_id = data["id"]
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, CONF_AGENT_ID: self._agent_id},
                )

    async def _heartbeat(self, _now: Any = None) -> None:
        if not self._agent_id:
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url(PATH_AGENT_HEARTBEAT, agent_id=self._agent_id),
                    headers=self._headers,
                ) as resp:
                    if resp.status == 401:
                        await self._notify_auth_failure()
                        return
                    resp.raise_for_status()
        except Exception as err:
            _LOGGER.warning("MC agent heartbeat failed: %s", err)

    async def _set_status(self, status: str) -> None:
        if not self._agent_id:
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url(PATH_AGENT_STATUS, agent_id=self._agent_id),
                    json={"status": status},
                    headers=self._headers,
                ) as resp:
                    resp.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.warning("MC status update failed: %s", err)
        self.state.online = status == "online"
        self.async_set_updated_data(self.state)

    async def _notify_auth_failure(self) -> None:
        self.hass.components.persistent_notification.async_create(
            "MissionControl service account token has expired. "
            "Reconfigure the integration to continue.",
            title="MissionControl: Auth Failure",
            notification_id="missioncontrol_auth_failure",
        )

    async def _async_update_data(self) -> MCAgentState:
        """Watchdog poll — returns current state. Real updates come via WS push."""
        return self.state

    async def _ws_listen_loop(self) -> None:
        """Persistent WebSocket loop. Reconnects with exponential backoff."""
        while not self._shutdown:
            try:
                ws_url = (
                    self._url(PATH_AGENT_NOTIFY, agent_id=self._agent_id)
                    .replace("http://", "ws://")
                    .replace("https://", "wss://")
                )
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        ws_url, headers=self._headers
                    ) as ws:
                        self._backoff = WS_BACKOFF_INITIAL_S
                        self.state.ws_connected = True
                        self.async_set_updated_data(self.state)
                        async for msg in ws:
                            if self._shutdown:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    continue
                                if data.get("type") == "task_available":
                                    self.hass.async_create_task(
                                        self._handle_task(data["task_id"])
                                    )
                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
            except asyncio.CancelledError:
                return
            except aiohttp.ClientError as err:
                _LOGGER.warning(
                    "MC WebSocket error: %s. Reconnecting in %ss", err, self._backoff
                )

            if self._shutdown:
                return

            self.state.ws_connected = False
            self.async_set_updated_data(self.state)
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, WS_BACKOFF_MAX_S)

    async def _handle_task(self, task_id: str) -> None:
        """Full task lifecycle: fetch → claim → execute → complete/fail."""
        # FETCH
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url(PATH_TASK, task_id=task_id), headers=self._headers
                ) as resp:
                    resp.raise_for_status()
                    task = await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to fetch task %s: %s", task_id, err)
            return

        # Capability check
        required: list[str] = task.get("required_capabilities") or []
        if required and not any(cap in self._capabilities for cap in required):
            _LOGGER.debug("Task %s requires %s — skipping", task_id, required)
            return

        # CLAIM
        claim_lease_id = await self._claim_task(task_id)
        if claim_lease_id is None:
            return  # 409/423: another agent claimed it

        # Task lease heartbeat — renewed every TASK_HEARTBEAT_INTERVAL_S
        task_hb_cancel = self._schedule_task_heartbeat(task_id, claim_lease_id)

        self.state.active_tasks += 1
        self.state.last_task = task.get("title", task_id)
        self.async_set_updated_data(self.state)

        await self._task_progress(task_id, "execution", f"Executing: {task.get('title', task_id)}")

        try:
            payload = HaTaskPayload.from_json(task.get("description", "{}"))
            await self._execute_payload(payload, task_id, claim_lease_id)
        except ValueError as err:
            await self._fail_task(task_id, claim_lease_id, f"invalid payload: {err}")
        except Exception as err:
            await self._fail_task(task_id, claim_lease_id, str(err))
        finally:
            task_hb_cancel()
            self.state.active_tasks = max(0, self.state.active_tasks - 1)
            self.state.tasks_completed += 1
            self.async_set_updated_data(self.state)

    def _schedule_task_heartbeat(
        self, task_id: str, claim_lease_id: str
    ) -> Any:
        """Schedule recurring task lease heartbeat. Returns cancel callable."""
        handle: list[Any] = []

        def _fire(_now: Any = None) -> None:
            self.hass.async_create_task(
                self._task_heartbeat(task_id, claim_lease_id)
            )
            handle.clear()
            handle.append(
                async_call_later(self.hass, TASK_HEARTBEAT_INTERVAL_S, _fire)
            )

        handle.append(async_call_later(self.hass, TASK_HEARTBEAT_INTERVAL_S, _fire))

        def cancel() -> None:
            if handle:
                handle[0]()

        return cancel

    async def _claim_task(self, task_id: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url(PATH_TASK_CLAIM, task_id=task_id),
                    json={"agent_id": self._agent_id},
                    headers=self._headers,
                ) as resp:
                    if resp.status in (409, 423):
                        return None
                    resp.raise_for_status()
                    data = await resp.json()
                    return data["claim_lease_id"]
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to claim task %s: %s", task_id, err)
            return None

    async def _task_heartbeat(self, task_id: str, claim_lease_id: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url(PATH_TASK_HEARTBEAT, task_id=task_id),
                    json={"claim_lease_id": claim_lease_id},
                    headers=self._headers,
                ) as resp:
                    resp.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.warning("Task heartbeat failed for %s: %s", task_id, err)

    async def _task_progress(self, task_id: str, phase: str, summary: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url(PATH_TASK_PROGRESS, task_id=task_id),
                    json={"event_type": "step", "phase": phase, "summary": summary},
                    headers=self._headers,
                ) as resp:
                    resp.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.warning("Task progress report failed for %s: %s", task_id, err)

    async def _execute_payload(
        self, payload: HaTaskPayload, task_id: str, claim_lease_id: str
    ) -> None:
        if payload.is_approval_gate:
            await self._execute_approval_gate(payload, task_id, claim_lease_id)
            return

        await self.hass.services.async_call(
            payload.domain,
            payload.service,
            service_data=payload.data if payload.data else None,
            target=payload.target if payload.target else None,
        )
        await self._complete_task(task_id, claim_lease_id)

    async def _execute_approval_gate(
        self, payload: HaTaskPayload, task_id: str, claim_lease_id: str
    ) -> None:
        """Send actionable notification and wait for APPROVE/REJECT response."""
        future: asyncio.Future[str] = self.hass.loop.create_future()

        def _on_action(event: Any) -> None:
            action = event.data.get("action", "")
            if not future.done():
                future.set_result(action)

        cancel_listener = self.hass.bus.async_listen(
            "mobile_app_notification_action", _on_action
        )

        await self.hass.services.async_call(
            payload.domain,
            payload.service,
            service_data=payload.data,
        )

        try:
            action = await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT_S)
        except asyncio.TimeoutError:
            cancel_listener()
            await self._fail_task(task_id, claim_lease_id, "Approval timeout after 24h")
            return

        cancel_listener()
        if action == "APPROVE":
            await self._complete_task(task_id, claim_lease_id)
        else:
            await self._fail_task(
                task_id, claim_lease_id, f"Rejected by user (action={action})"
            )

    async def _complete_task(self, task_id: str, claim_lease_id: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._url(PATH_TASK_COMPLETE, task_id=task_id),
                json={"claim_lease_id": claim_lease_id},
                headers=self._headers,
            ) as resp:
                resp.raise_for_status()

    async def _fail_task(
        self, task_id: str, claim_lease_id: str, error: str
    ) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url(PATH_TASK_FAIL, task_id=task_id),
                    json={"claim_lease_id": claim_lease_id, "error": error},
                    headers=self._headers,
                ) as resp:
                    resp.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to report task failure for %s: %s", task_id, err)

    async def shutdown(self) -> None:
        """Called on config entry unload."""
        self._cancel_ws()
        await self._set_status("offline")
