"""Config flow pour DeepSeek Usage & Balance."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import fetch_balance


async def _validate_key(hass: HomeAssistant, api_key: str) -> tuple[str, str] | None:
    """Teste la clé ; renvoie (currency, title_part) ou lève une erreur lisible."""
    try:
        info = await fetch_balance(hass, api_key)
    except ConfigEntryAuthFailed:
        return ("invalid_auth", "invalid_auth")
    except Exception:
        return ("cannot_connect", "cannot_connect")
    currency = info.get("currency", "USD")
    return (None, currency)


class DeepSeekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gère le flux de configuration initial."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        currency_hint: str | None = None

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            result = await _validate_key(self.hass, api_key)
            if result[0] is not None:
                errors["base"] = result[0]
            else:
                currency = result[1]
                await self.async_set_unique_id(api_key)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"DeepSeek ({currency})",
                    data={CONF_API_KEY: api_key, "currency": currency},
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        )
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=DEFAULT_SCAN_INTERVAL,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> ConfigFlowResult:
        """Support d'import YAML minimal (aucune config YAML officielle)."""
        return await self.async_step_user(import_config)

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,  # noqa: ARG004
    ) -> OptionsFlow:
        return DeepSeekOptionsFlow()


class DeepSeekOptionsFlow(OptionsFlow):
    """Options : intervalle de polling modifiable."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                },
            )
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
