"""Config flow for MissionControl integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import (
    ALL_CAPABILITIES, CONF_AGENT_NAME, CONF_CAPABILITIES, CONF_MC_URL,
    CONF_MISSION_ID, CONF_SA_TOKEN, DOMAIN, PATH_AUTH_WHOAMI, PATH_MISSIONS,
)

_LOGGER = logging.getLogger(__name__)

STEP1_SCHEMA = vol.Schema({
    vol.Required(CONF_MC_URL): str,
    vol.Required(CONF_SA_TOKEN): str,
})

STEP2_SCHEMA = vol.Schema({
    vol.Required(CONF_AGENT_NAME, default="home-assistant"): str,
    vol.Required(CONF_CAPABILITIES, default=ALL_CAPABILITIES): vol.All(
        list, [vol.In(ALL_CAPABILITIES)]
    ),
})


class MCClient:
    """Minimal MC REST client used only during config flow."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def validate_and_create_mission(self) -> str:
        """Validate token, then get or create the home-assistant mission. Returns mission_id."""
        async with aiohttp.ClientSession() as session:
            # Validate token via /auth/whoami (returns 401 on bad token, unlike /health)
            async with session.get(
                f"{self._base_url}{PATH_AUTH_WHOAMI}", headers=self._headers
            ) as resp:
                if resp.status == 401:
                    raise Exception("401 Unauthorized")
                resp.raise_for_status()

            # Try to create the mission; on 409 (already exists) fetch it from the list
            async with session.post(
                f"{self._base_url}{PATH_MISSIONS}",
                json={
                    "name": "home-assistant",
                    "description": "Home Assistant fleet agent mission",
                },
                headers=self._headers,
            ) as resp:
                if resp.status == 409:
                    # Mission already exists — look it up by name
                    async with session.get(
                        f"{self._base_url}{PATH_MISSIONS}", headers=self._headers
                    ) as list_resp:
                        list_resp.raise_for_status()
                        missions = await list_resp.json()
                    for m in missions:
                        if m.get("name") == "home-assistant":
                            return m["id"]
                    raise Exception("Mission conflict but 'home-assistant' not found in list")
                resp.raise_for_status()
                data = await resp.json()
                return data["id"]


class MCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for MissionControl."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = MCClient(user_input[CONF_MC_URL], user_input[CONF_SA_TOKEN])
            try:
                mission_id = await client.validate_and_create_mission()
                self._connection_data = {
                    CONF_MC_URL: user_input[CONF_MC_URL].rstrip("/"),
                    CONF_SA_TOKEN: user_input[CONF_SA_TOKEN],
                    CONF_MISSION_ID: mission_id,
                }
                return await self.async_step_agent()
            except Exception as err:
                _LOGGER.warning("MC connection failed: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP1_SCHEMA,
            errors=errors,
        )

    async def async_step_agent(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=f"MissionControl ({user_input[CONF_AGENT_NAME]})",
                data={**self._connection_data, **user_input},
            )

        return self.async_show_form(
            step_id="agent",
            data_schema=STEP2_SCHEMA,
        )
