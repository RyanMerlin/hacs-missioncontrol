"""Data models for MissionControl integration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class HaTaskPayload:
    """Structured task payload — a single HA service call."""

    domain: str
    service: str
    target: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: str) -> "HaTaskPayload":
        """Parse from task description JSON. Raises ValueError on bad input."""
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as err:
            raise ValueError(f"invalid payload: {err}") from err

        if "domain" not in obj:
            raise ValueError("payload missing required field: domain")
        if "service" not in obj:
            raise ValueError("payload missing required field: service")

        return cls(
            domain=obj["domain"],
            service=obj["service"],
            target=obj.get("target", {}),
            data=obj.get("data", {}),
        )

    @property
    def is_approval_gate(self) -> bool:
        """True when this payload sends an actionable notification."""
        return (
            self.domain == "notify"
            and isinstance(self.data.get("actions"), list)
            and len(self.data["actions"]) > 0
        )


@dataclass
class MCAgentState:
    """Mutable state surfaced to HA entities."""

    online: bool = False
    ws_connected: bool = False
    active_tasks: int = 0
    tasks_completed: int = 0
    last_task: str | None = None
