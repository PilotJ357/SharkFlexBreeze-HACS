from __future__ import annotations

from homeassistant.components.radio_frequency import ModulationType, async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, Entity
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


class _OOKCommand(RadioFrequencyCommand):
    def __init__(self, *, frequency: int, timings: list[int], repeat_count: int = 0) -> None:
        super().__init__(frequency=frequency, modulation=ModulationType.OOK, repeat_count=repeat_count)
        self.timings = timings

    def get_raw_timings(self) -> list[int]:
        return self.timings


def make_command(fan_id: str, suffix: str) -> _OOKCommand:
    """Build an OOKCommand from a fan ID prefix and command suffix."""
    hex_code = fan_id + suffix
    n = int(hex_code, 16)
    b = bin(n)[2:].zfill(44)[:PACKET_BITS]
    timings: list[int] = [SYNC_US, -GAP_US]
    for i, bit in enumerate(b):
        pulse = LONG_US if bit == "1" else SHORT_US
        gap = -RESET_US if i == PACKET_BITS - 1 else -GAP_US
        timings += [pulse, gap]
    return _OOKCommand(frequency=FREQ_HZ, timings=timings, repeat_count=REPEAT_COUNT)


class SharkFlexBreezeEntity(Entity):
    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._fan_id: str = entry.data[CONF_FAN_ID]
        self._attr_unique_id = f"{self._transmitter}_{self._fan_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Shark",
            model="FlexBreeze",
            name=entry.title,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._transmitter,
                self._handle_transmitter_state_change,
            )
        )
        self._update_availability_from_transmitter()

    @callback
    def _handle_transmitter_state_change(self, event) -> None:
        self._update_availability_from_transmitter()
        self.async_write_ha_state()

    @callback
    def _update_availability_from_transmitter(self) -> None:
        state = self.hass.states.get(self._transmitter)
        self._attr_available = state is not None and state.state not in (
            "unavailable",
            "unknown",
        )

    async def _async_send(self, command_name: str) -> None:
        command = make_command(self._fan_id, COMMAND_SUFFIXES[command_name])
        await async_send_command(self.hass, self._transmitter, command)
