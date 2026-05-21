"""Sensors: active tasks, completed count, last task."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_ACTIVE_TASKS, ENTITY_LAST_TASK, ENTITY_TASKS_COMPLETED
from .coordinator import MCCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MCCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MCActiveTasksSensor(coordinator),
        MCTasksCompletedSensor(coordinator),
        MCLastTaskSensor(coordinator),
    ])


class MCActiveTasksSensor(CoordinatorEntity[MCCoordinator], SensorEntity):
    _attr_name = "MissionControl Active Tasks"
    _attr_native_unit_of_measurement = "tasks"

    def __init__(self, coordinator: MCCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{ENTITY_ACTIVE_TASKS}"

    @property
    def native_value(self) -> int:
        return self.coordinator.state.active_tasks


class MCTasksCompletedSensor(CoordinatorEntity[MCCoordinator], SensorEntity):
    _attr_name = "MissionControl Tasks Completed"
    _attr_native_unit_of_measurement = "tasks"

    def __init__(self, coordinator: MCCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{ENTITY_TASKS_COMPLETED}"

    @property
    def native_value(self) -> int:
        return self.coordinator.state.tasks_completed


class MCLastTaskSensor(CoordinatorEntity[MCCoordinator], SensorEntity):
    _attr_name = "MissionControl Last Task"

    def __init__(self, coordinator: MCCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{ENTITY_LAST_TASK}"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.state.last_task
