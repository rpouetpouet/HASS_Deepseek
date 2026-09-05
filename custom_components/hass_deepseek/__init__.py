"""Intégration DeepSeek Usage & Balance — point d'entrée."""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_API_KEY, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import DeepSeekCoordinator

_UNDO_UPDATE_LISTENER = "undo_update_listener"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise une entrée : crée le coordinateur et les plateformes."""
    api_key: str = entry.data[CONF_API_KEY]
    currency: str = entry.data.get("currency", "USD")
    scan_interval_min: int = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )

    coordinator = DeepSeekCoordinator(
        hass, entry.entry_id, api_key, currency, scan_interval_min
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"DeepSeek first refresh failed: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def _reload_on_options(
        _hass: HomeAssistant, changed_entry: ConfigEntry
    ) -> None:
        """Réapplique l'intervalle de polling quand les options changent."""
        coordinator.update_interval = dt.timedelta(
            minutes=changed_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
        )
        await coordinator.async_request_refresh()

    hass.data[DOMAIN][entry.entry_id + _UNDO_UPDATE_LISTENER] = (
        entry.add_update_listener(_reload_on_options)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge l'entrée."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        listener = hass.data[DOMAIN].pop(entry.entry_id + _UNDO_UPDATE_LISTENER, None)
        if listener is not None:
            listener()
    return unload_ok
