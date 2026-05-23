from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.radio_frequency import (
    ModulationType,
    async_get_transmitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_FAN_ID,
    CONF_FAN_NAME,
    CONF_TRANSMITTER,
    DOMAIN,
    FREQ_HZ,
)

_FAN_ID_RE = re.compile(r"^[0-9a-fA-F]{6}$")
_ENTER_NEW = "enter_new"


class SharkFlexBreezeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._pending: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        try:
            transmitters = async_get_transmitters(
                self.hass, FREQ_HZ, ModulationType.OOK
            )
        except HomeAssistantError:
            return self.async_abort(reason="no_compatible_transmitters")

        if user_input is not None:
            self._pending[CONF_TRANSMITTER] = user_input[CONF_TRANSMITTER]
            self._pending[CONF_FAN_NAME] = user_input[CONF_FAN_NAME]
            return await self.async_step_fan_id()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSMITTER): EntitySelector(
                        EntitySelectorConfig(include_entities=transmitters)
                    ),
                    vol.Required(CONF_FAN_NAME): TextSelector(),
                }
            ),
        )

    async def async_step_fan_id(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            choice = user_input["fan_id_choice"]
            if choice == _ENTER_NEW:
                return await self.async_step_manual_id()
            self._pending[CONF_FAN_ID] = choice
            return await self.async_step_test()

        # Build dropdown: existing configured fan IDs + "Enter new"
        known: list[SelectOptionDict] = [
            SelectOptionDict(
                value=entry.data[CONF_FAN_ID],
                label=f"{entry.title} ({entry.data[CONF_FAN_ID]})",
            )
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if CONF_FAN_ID in entry.data
        ]
        known.append(SelectOptionDict(value=_ENTER_NEW, label="Enter a new ID…"))

        return self.async_show_form(
            step_id="fan_id",
            data_schema=vol.Schema(
                {
                    vol.Required("fan_id_choice"): SelectSelector(
                        SelectSelectorConfig(
                            options=known,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_manual_id(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            fan_id = user_input[CONF_FAN_ID].lower().strip()
            if not _FAN_ID_RE.match(fan_id):
                errors[CONF_FAN_ID] = "invalid_fan_id"
            else:
                self._pending[CONF_FAN_ID] = fan_id
                return await self.async_step_test()

        return self.async_show_form(
            step_id="manual_id",
            data_schema=vol.Schema(
                {vol.Required(CONF_FAN_ID): TextSelector()}
            ),
            errors=errors,
        )

    async def async_step_test(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        from .entity import make_command
        from homeassistant.components.radio_frequency import async_send_command
        from .const import COMMAND_SUFFIXES

        command = make_command(self._pending[CONF_FAN_ID], COMMAND_SUFFIXES["power"])
        await async_send_command(
            self.hass, self._pending[CONF_TRANSMITTER], command
        )

        return self.async_show_menu(
            step_id="test",
            menu_options=["confirm", "retry", "cancel"],
            description_placeholders={"fan_name": self._pending[CONF_FAN_NAME]},
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        fan_id = self._pending[CONF_FAN_ID]
        transmitter = self._pending[CONF_TRANSMITTER]
        unique_id = f"{transmitter}_{fan_id}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._pending[CONF_FAN_NAME],
            data={
                CONF_TRANSMITTER: transmitter,
                CONF_FAN_ID: fan_id,
            },
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self.async_step_test()

    async def async_step_cancel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="cancelled")
