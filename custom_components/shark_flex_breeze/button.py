from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import SharkFlexBreezeEntity


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([
        SharkFlexBreezeResetButton(entry),
        SharkFlexBreezeRotateLeftButton(entry),
        SharkFlexBreezeRotateRightButton(entry),
    ])


class SharkFlexBreezeResetButton(SharkFlexBreezeEntity, ButtonEntity):
    _attr_translation_key = "reset_state"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:sync-alert"

    async def async_press(self) -> None:
        fan = self.hass.data[DOMAIN][self._entry.entry_id].get("fan")
        if fan is not None:
            fan.reset_state()


class SharkFlexBreezeRotateLeftButton(SharkFlexBreezeEntity, ButtonEntity):
    _attr_translation_key = "rotate_left"
    _attr_icon = "mdi:rotate-left"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._attr_unique_id}_rotate_left"

    async def async_press(self) -> None:
        await self._async_send("rotate_left")


class SharkFlexBreezeRotateRightButton(SharkFlexBreezeEntity, ButtonEntity):
    _attr_translation_key = "rotate_right"
    _attr_icon = "mdi:rotate-right"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._attr_unique_id}_rotate_right"

    async def async_press(self) -> None:
        await self._async_send("rotate_right")
