"""Constants for MissionControl integration."""

DOMAIN = "missioncontrol"

# Config entry keys
CONF_MC_URL = "mc_url"
CONF_SA_TOKEN = "sa_token"
CONF_AGENT_NAME = "agent_name"
CONF_CAPABILITIES = "capabilities"
CONF_MISSION_ID = "mission_id"
CONF_AGENT_ID = "agent_id"
CONF_AGENT_PUBLIC_ID = "agent_public_id"

# Timings
HEARTBEAT_INTERVAL_S = 60
TASK_HEARTBEAT_INTERVAL_S = 90
WS_BACKOFF_INITIAL_S = 1
WS_BACKOFF_MAX_S = 60
APPROVAL_TIMEOUT_S = 86400  # 24 hours

# MC API paths
PATH_HEALTH = "/health"
PATH_AUTH_WHOAMI = "/auth/whoami"
PATH_MISSIONS = "/missions"
PATH_ENROLL = "/work/missions/{mission_id}/agents/enroll"
PATH_AGENT_HEARTBEAT = "/work/agents/{agent_id}/heartbeat"
PATH_AGENT_STATUS = "/agents/{agent_public_id}"
PATH_AGENT_NOTIFY = "/work/agents/{agent_id}/notify"
PATH_TASK = "/work/tasks/{task_id}"
PATH_TASK_CLAIM = "/work/tasks/{task_id}/claim"
PATH_TASK_HEARTBEAT = "/work/tasks/{task_id}/heartbeat"
PATH_TASK_PROGRESS = "/work/tasks/{task_id}/progress"
PATH_TASK_COMPLETE = "/work/tasks/{task_id}/complete"
PATH_TASK_FAIL = "/work/tasks/{task_id}/fail"

# Capability strings
CAP_LIGHT = "home_control.light"
CAP_SWITCH = "home_control.switch"
CAP_CLIMATE = "home_control.climate"
CAP_COVER = "home_control.cover"
CAP_SCENE = "home_control.scene"
CAP_SCRIPT = "home_control.script"
CAP_MEDIA_PLAYER = "home_control.media_player"
CAP_NOTIFY = "notify"
CAP_PRESENCE = "presence"
CAP_SENSOR_READ = "sensor_read"

ALL_CAPABILITIES = [
    CAP_LIGHT, CAP_SWITCH, CAP_CLIMATE, CAP_COVER,
    CAP_SCENE, CAP_SCRIPT, CAP_MEDIA_PLAYER,
    CAP_NOTIFY, CAP_PRESENCE, CAP_SENSOR_READ,
]

# Entity unique ID suffixes
ENTITY_AGENT_ONLINE = "agent_online"
ENTITY_ACTIVE_TASKS = "active_tasks"
ENTITY_TASKS_COMPLETED = "tasks_completed"
ENTITY_LAST_TASK = "last_task"
ENTITY_RECONNECT = "reconnect"
