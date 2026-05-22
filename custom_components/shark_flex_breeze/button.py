from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SharkFlexBreezeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SharkFlexBreezeResetButton(entry)])


class SharkFlexBreezeResetButton(SharkFlexBreezeEntity, ButtonEntity):
    _attr_translation_key = "reset_state"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:sync-alert"

    async def async_press(self) -> None:
        fan = self.hass.data[DOMAIN][self._entry.entry_id].get("fan")
        if fan is not None:
            fan.reset_state()
