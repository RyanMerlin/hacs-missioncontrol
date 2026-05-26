# EdgePlane — Home Assistant Integration

[![HACS Default](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/hacs/integration)
[![CI](https://github.com/RyanMerlin/edgeplane-homeassistant/actions/workflows/ci.yml/badge.svg)](https://github.com/RyanMerlin/edgeplane-homeassistant/actions/workflows/ci.yml)

Registers Home Assistant as a first-class agent in the [EdgePlane](https://github.com/RyanMerlin/edgeplane) fleet. HA enrolls via the EdgePlane mesh API, receives task assignments as WebSocket push messages, executes them as HA service calls, and reports completion back to EdgePlane.

## Features

- **Full ACP lifecycle**: enroll, heartbeat, claim, execute, complete
- **WebSocket push**: tasks arrive instantly, no polling
- **Structured service calls**: JSON domain/service/target/data task format
- **iOS approval gates**: actionable notifications with APPROVE/REJECT response
- **5 HA entities**: agent online sensor, active tasks, completed tasks, last task, reconnect button

## Installation

### Via HACS (recommended)

1. In HACS, search for **EdgePlane** and click Download
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → EdgePlane**
4. Enter your EdgePlane server URL and a session token (see [Authentication](#authentication) below)

### Manual / custom repository

If EdgePlane hasn't appeared in the HACS default store yet, add it manually:

1. In HACS → ⋮ → Custom repositories, add `https://github.com/RyanMerlin/edgeplane-homeassistant` (category: Integration)
2. Install "EdgePlane" from HACS
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → EdgePlane**
5. Enter your EdgePlane server URL and a session token

## Authentication

The integration authenticates using an **EdgePlane session token** — a 64-character bearer token stored in `~/.edgeplane/session.json` after running `edgeplane auth login`.

```bash
edgeplane auth login
# Token is stored at ~/.edgeplane/session.json
cat ~/.edgeplane/session.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"
```

Copy that token into the **API Token** field during setup.

## Configuration

| Field | Description |
|-------|-------------|
| EdgePlane URL | Base URL of your EdgePlane server. If HA runs in the same Kubernetes cluster as EdgePlane, use the cluster-internal service DNS (e.g. `http://edgeplane.edgeplane.svc.cluster.local:8008`) rather than a Tailscale hostname. |
| API Token | A session token from `edgeplane auth login` (see above) |
| Agent name | Identifier shown in the EdgePlane fleet view |
| Capabilities | Which HA domains to expose as EdgePlane capabilities |

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.edgeplane_agent_online` | Binary Sensor | True when WebSocket connected |
| `sensor.edgeplane_active_tasks` | Sensor | Currently running tasks |
| `sensor.edgeplane_tasks_completed` | Sensor | Total tasks completed since restart |
| `sensor.edgeplane_last_task` | Sensor | Title of last executed task |
| `button.edgeplane_reconnect` | Button | Force re-register and reconnect |

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
- `edgeplane.create_task` HA service for automation triggers
