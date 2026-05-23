from __future__ import annotations

import logging

from homeassistant.components.radio_frequency import ModulationType, async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from rf_protocols import RadioFrequencyCommand

from .const import (
    COMMAND_SUFFIXES,
    CONF_FAN_ID,
    CONF_TRANSMITTER,
    DOMAIN,
    FREQ_HZ,
    GAP_US,
    LONG_US,
    PACKET_BITS,
    REPEAT_COUNT,
    RESET_US,
    SHORT_US,
    SYNC_US,
)

_LOGGER = logging.getLogger(__name__)


class _OOKCommand(RadioFrequencyCommand):
    def __init__(self, *, frequency: int, timings: list[int], repeat_count: int = 0) -> None:
        super().__init__(frequency=frequency, modulation=ModulationType.OOK, repeat_count=repeat_count)
        self.timings = timings

    def get_raw_timings(self) -> list[int]:
        return self.timings


def make_command(fan_id: str, suffix: str) -> _OOKCommand:
    hex_code = fan_id + suffix
    n = int(hex_code, 16)
    b = bin(n)[2:].zfill(44)[:PACKET_BITS]
    timings: list[int] = [SYNC_US, -GAP_US]
    for i, bit in enumerate(b):
        pulse = LONG_US if bit == "1" else SHORT_US
        gap = -RESET_US if i == PACKET_BITS - 1 else -GAP_US
        timings += [pulse, gap]
    return _OOKCommand(frequency=FREQ_HZ, timings=timings, repeat_count=0)


class SharkFlexBreezeEntity(Entity):
    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._fan_id: str = entry.data[CONF_FAN_ID]
        self._transmitter_entity_id: str = self._transmitter
        self._attr_unique_id = f"{self._transmitter}_{self._fan_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Shark",
            model="FlexBreeze",
            name=entry.title,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        self._transmitter_entity_id = er.async_validate_entity_id(
            er.async_get(self.hass), self._transmitter
        )

        @callback
        def _handle_transmitter_state_change(
            event: Event[EventStateChangedData],
        ) -> None:
            new_state = event.data["new_state"]
            available = new_state is not None and new_state.state != STATE_UNAVAILABLE
            if available != self.available:
                _LOGGER.info(
                    "Transmitter %s used by %s is %s",
                    self._transmitter_entity_id,
                    self.entity_id,
                    "available" if available else "unavailable",
                )
                self._attr_available = available
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._transmitter_entity_id],
                _handle_transmitter_state_change,
            )
        )

        transmitter_state = self.hass.states.get(self._transmitter_entity_id)
        self._attr_available = (
            transmitter_state is not None
            and transmitter_state.state != STATE_UNAVAILABLE
        )

    async def _async_send(self, command_name: str) -> None:
        suffix = COMMAND_SUFFIXES[command_name]
        command = make_command(self._fan_id, suffix)
        _LOGGER.debug(
            "Sending %s (fan_id=%s suffix=%s) via %s x%d",
            command_name, self._fan_id, suffix, self._transmitter, REPEAT_COUNT,
        )
        for i in range(REPEAT_COUNT):
            try:
                await async_send_command(
                    self.hass, self._transmitter, command, context=self._context
                )
            except Exception as err:
                _LOGGER.error(
                    "Command %s send %d/%d failed: %s",
                    command_name, i + 1, REPEAT_COUNT, err,
                )
                raise
