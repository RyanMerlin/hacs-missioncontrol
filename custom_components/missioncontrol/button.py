"""Button: force reconnect to MC."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTITY_RECONNECT
from .coordinator import MCCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MCCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MCReconnectButton(coordinator, entry)])


class MCReconnectButton(ButtonEntity):
    _attr_name = "MissionControl Reconnect"

    def __init__(self, coordinator: MCCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{ENTITY_RECONNECT}"

    async def async_press(self) -> None:
        await self._coordinator.shutdown()
        await self._coordinator._async_setup()
