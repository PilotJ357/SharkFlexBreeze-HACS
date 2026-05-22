from __future__ import annotations

import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, PRESET_MODES, PRESET_NORMAL, PRESET_TURBO
from .entity import SharkFlexBreezeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    fan = SharkFlexBreezeFan(entry)
    hass.data[DOMAIN][entry.entry_id]["fan"] = fan
    async_add_entities([fan])


class SharkFlexBreezeFan(SharkFlexBreezeEntity, FanEntity, RestoreEntity):
    _attr_name = None
    _attr_speed_count = 5  # hardware has 5 speed levels
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._is_on = False
        # 0 = unknown, 1–5 = hardware levels. Preserved when turbo is active —
        # turbo is a toggle and the fan returns to this level automatically on exit.
        self._speed_level: int = 0
        self._preset_mode: str | None = None
        self._oscillating: bool = False
        self._direction: str = "forward"

    # ── state properties ────────────────────────────────────────────────────

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def percentage(self) -> int | None:
        if self._speed_level == 0:
            return None
        return self._speed_level * 20  # 5 levels → 20/40/60/80/100%

    @property
    def preset_mode(self) -> str | None:
        return self._preset_mode

    @property
    def oscillating(self) -> bool:
        return self._oscillating

    @property
    def current_direction(self) -> str:
        return self._direction

    # ── restore ─────────────────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._is_on = last_state.state == STATE_ON
            attrs = last_state.attributes
            pct = attrs.get("percentage")
            if pct is not None:
                self._speed_level = max(1, min(5, math.ceil(int(pct) / 20)))
            self._preset_mode = attrs.get("preset_mode")
            osc = attrs.get("oscillating")
            if osc is not None:
                self._oscillating = bool(osc)
            direction = attrs.get("direction")
            if direction is not None:
                self._direction = direction

    # ── commands ─────────────────────────────────────────────────────────────

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        if not self._is_on:
            await self._async_send("power")
            self._is_on = True
            if self._speed_level == 0:
                self._speed_level = 1

        if preset_mode == PRESET_TURBO:
            await self._async_send("turbo")
            self._preset_mode = PRESET_TURBO
        elif percentage is not None:
            await self._set_speed_level(math.ceil(percentage / 20))
            return  # _set_speed_level writes state

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        if self._is_on:
            await self._async_send("power")
            self._is_on = False
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self._is_on:
            await self._async_send("power")
            self._is_on = True
            if self._speed_level == 0:
                self._speed_level = 1
        await self._set_speed_level(math.ceil(percentage / 20))

    async def async_increase_speed(self, percentage_step: int | None = None) -> None:
        if not self._is_on:
            await self.async_turn_on()
        if self._speed_level < 5:
            await self._async_send("speed_increase")
            self._speed_level = min(5, self._speed_level + 1)
            self._preset_mode = PRESET_NORMAL
            self.async_write_ha_state()

    async def async_decrease_speed(self, percentage_step: int | None = None) -> None:
        if self._speed_level > 1:
            await self._async_send("speed_decrease")
            self._speed_level = max(1, self._speed_level - 1)
            self._preset_mode = PRESET_NORMAL
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_TURBO:
            if not self._is_on:
                await self._async_send("power")
                self._is_on = True
                if self._speed_level == 0:
                    self._speed_level = 1
            await self._async_send("turbo")
            self._preset_mode = PRESET_TURBO
        elif preset_mode == PRESET_NORMAL and self._preset_mode == PRESET_TURBO:
            # Turbo is a toggle — sending it again exits burst and the fan
            # returns to its previous speed automatically. No speed command needed.
            await self._async_send("turbo")
            self._preset_mode = PRESET_NORMAL
            # _speed_level was preserved when we entered turbo, so it's still correct
        else:
            self._preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        cmd = "swing_increase" if oscillating else "swing_decrease"
        await self._async_send(cmd)
        self._oscillating = oscillating
        self.async_write_ha_state()

    async def async_set_direction(self, direction: str) -> None:
        cmd = "rotate_right" if direction == "forward" else "rotate_left"
        await self._async_send(cmd)
        self._direction = direction
        self.async_write_ha_state()

    # ── state sync ───────────────────────────────────────────────────────────

    def reset_state(self) -> None:
        """Reset assumed state to off. Use after physically powering the fan off
        so HA re-syncs: next turn_on will always start from speed 1."""
        self._is_on = False
        self._speed_level = 0
        self._preset_mode = None
        self._oscillating = False
        self._direction = "forward"
        self.async_write_ha_state()

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _set_speed_level(self, target: int) -> None:
        target = max(1, min(5, target))
        delta = target - self._speed_level
        if delta > 0:
            for _ in range(delta):
                await self._async_send("speed_increase")
        elif delta < 0:
            for _ in range(-delta):
                await self._async_send("speed_decrease")
        self._speed_level = target
        self._preset_mode = PRESET_NORMAL
        self.async_write_ha_state()
