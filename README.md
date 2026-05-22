# MissionControl — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![CI](https://github.com/RyanMerlin/hacs-missioncontrol/actions/workflows/ci.yml/badge.svg)](https://github.com/RyanMerlin/hacs-missioncontrol/actions/workflows/ci.yml)

Registers Home Assistant as a first-class agent in the [MissionControl](https://github.com/RyanMerlin/missioncontrol) fleet. HA enrolls via the MC mesh API, receives task assignments as WebSocket push messages, executes them as HA service calls, and reports completion back to MC.

## Features

- **Full ACP lifecycle**: enroll, heartbeat, claim, execute, complete
- **WebSocket push**: tasks arrive instantly, no polling
- **Structured service calls**: JSON domain/service/target/data task format
- **iOS approval gates**: actionable notifications with APPROVE/REJECT response
- **5 HA entities**: agent online sensor, active tasks, completed tasks, last task, reconnect button

## Installation

1. Add this repository to HACS as a custom repository
2. Install "MissionControl" from HACS
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → MissionControl**
5. Enter your MC server URL and a session token (see [Authentication](#authentication) below)

## Authentication

The integration authenticates using a **MC session token** — a 64-character bearer token stored in `~/.mc/session.json` after running `mc auth login`.

```bash
mc auth login
# Token is stored at ~/.mc/session.json
cat ~/.mc/session.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"
```

Copy that token into the **API Token** field during setup.

> **Note:** MC service account tokens (`mcs_cs_*`) do not authenticate against mesh API endpoints. Session tokens are required.

## Configuration

| Field | Description |
|-------|-------------|
| MC URL | Base URL of your MissionControl server. If HA runs in the same Kubernetes cluster as MC, use the cluster-internal service DNS (e.g. `http://mc-controlplane.missioncontrol.svc.cluster.local:8008`) rather than a Tailscale hostname. |
| API Token | A session token from `mc auth login` (see above) |
| Agent name | Identifier shown in the MC fleet view |
| Capabilities | Which HA domains to expose as MC capabilities |

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.missioncontrol_agent_online` | Binary Sensor | True when WebSocket connected |
| `sensor.missioncontrol_active_tasks` | Sensor | Currently running tasks |
| `sensor.missioncontrol_tasks_completed` | Sensor | Total tasks completed since restart |
| `sensor.missioncontrol_last_task` | Sensor | Title of last executed task |
| `button.missioncontrol_reconnect` | Button | Force re-register and reconnect |

## Task Payload Format

Tasks must have a JSON description:

```json
{
  "domain": "light",
  "service": "turn_on",
  "target": {"entity_id": "light.office_ceiling"},
  "data": {"brightness": 200}
}
```

## Phase 2 (planned)

- `hga_prompt` capability — route tasks to Home Generative Agent
- Mission ledger WebSocket stream for real-time fleet sensors
- `missioncontrol.create_task` HA service for automation triggers
