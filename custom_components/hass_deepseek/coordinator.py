"""Coordinateur : polling du solde DeepSeek + suivi local des dépenses."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_BALANCE_URL, CONF_API_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


async def fetch_balance(
    hass: HomeAssistant, api_key: str
) -> dict[str, Any]:
    """Interroge /user/balance et renvoie le premier bloc balance_infos + is_available."""
    session = aiohttp_client.async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        async with session.get(API_BALANCE_URL, headers=headers, timeout=15) as resp:
            if resp.status == 401:
                raise ConfigEntryAuthFailed("Invalid API key (HTTP 401)")
            if resp.status != 200:
                raise UpdateFailed(f"DeepSeek API HTTP {resp.status}")
            payload = await resp.json()
    except ConfigEntryAuthFailed:
        raise
    except aiohttp.ClientError as err:
        raise UpdateFailed(f"Network error: {err}") from err
    except ValueError as err:
        raise UpdateFailed(f"Invalid JSON: {err}") from err

    if not payload.get("is_available"):
        raise UpdateFailed("DeepSeek API reports is_available=false")
    infos = payload.get("balance_infos") or []
    if not infos:
        raise UpdateFailed("No balance_infos in response")
    return infos[0]


class DeepSeekUsageStore:
    """Persiste le suivi des dépenses (delta de solde) entre les redémarrages HA."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{__name__.split('.')[0]}.usage.{entry_id}"
        )
        self._data: dict[str, Any] | None = None

    async def _ensure(self) -> dict[str, Any]:
        if self._data is None:
            raw = await self._store.async_load()
            self._data = raw if isinstance(raw, dict) else {}
            self._data.setdefault("last_total", None)
            self._data.setdefault("last_topped", None)
            self._data.setdefault("days", {})
            self._data.setdefault("months", {})
        return self._data

    @staticmethod
    def _now() -> dt.datetime:
        return dt.datetime.now().astimezone()

    async def record(self, cur_total: float, cur_topped: float) -> tuple[float, float]:
        """Enregistre un point de solde ; renvoie (spend_today, spend_month).

        top-up détecté : si topped_up augmente, l'écart n'est pas compté comme dépense.
        """
        data = await self._ensure()
        now = self._now()
        day_key = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")

        days: dict[str, float] = data["days"]
        months: dict[str, float] = data["months"]
        days.setdefault(day_key, 0.0)
        months.setdefault(month_key, 0.0)

        last_total = data["last_total"]
        last_topped = data["last_topped"]

        if last_total is None or last_topped is None:
            # Premier point : pas encore de dépense mesurable.
            data["last_total"] = cur_total
            data["last_topped"] = cur_topped
        else:
            topup = max(0.0, cur_topped - last_topped)
            spend = (last_total + topup) - cur_total
            if spend < 0:
                spend = 0.0
            days[day_key] += spend
            months[month_key] += spend
            data["last_total"] = cur_total
            data["last_topped"] = cur_topped

        # Nettoyage : garder ~62 jours et 13 mois.
        keep_days = sorted(days, reverse=True)[:62]
        for k in list(days):
            if k not in keep_days:
                days.pop(k, None)
        keep_months = sorted(months, reverse=True)[:13]
        for k in list(months):
            if k not in keep_months:
                months.pop(k, None)

        await self._store.async_save(data)
        return days.get(day_key, 0.0), months.get(month_key, 0.0)


class DeepSeekCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polling périodique + exposition des soldes et dépenses."""

    def __init__(self, hass: HomeAssistant, entry_id: str, api_key: str, currency: str, scan_interval_min: int) -> None:
        self._api_key = api_key
        self._currency = currency
        self.usage_store = DeepSeekUsageStore(hass, entry_id)
        self.spend_today: float = 0.0
        self.spend_month: float = 0.0
        self.last_success_ts: float | None = None
        super().__init__(
            hass,
            _LOGGER,
            name="hass_deepseek",
            update_interval=dt.timedelta(minutes=scan_interval_min),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        info = await fetch_balance(self.hass, self._api_key)
        currency = info.get("currency") or self._currency
        total = float(info.get("total_balance") or 0)
        granted = float(info.get("granted_balance") or 0)
        topped = float(info.get("topped_up_balance") or 0)

        self.spend_today, self.spend_month = await self.usage_store.record(total, topped)
        self.last_success_ts = __import__("time").time()

        return {
            "currency": currency,
            "total_balance": total,
            "granted_balance": granted,
            "topped_up_balance": topped,
            "spend_today": self.spend_today,
            "spend_month": self.spend_month,
            "last_success_ts": self.last_success_ts,
        }
