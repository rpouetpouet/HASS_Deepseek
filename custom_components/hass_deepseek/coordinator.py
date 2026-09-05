"""Coordinateur : polling du solde DeepSeek + suivi local des dépenses."""

from __future__ import annotations

import calendar
import datetime as dt
import logging
import time
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_BALANCE_URL,
    CONF_API_KEY,
    PEAK_WINDOWS_UTC,
    PRICING_GRID,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def tariff_at(hour_utc: int) -> str:
    """Renvoie 'peak' ou 'off-peak' pour une heure UTC donnée (fenêtres officielles)."""
    for start, end in PEAK_WINDOWS_UTC:
        if start <= hour_utc < end:
            return "peak"
    return "off-peak"


def next_tariff_change(now_utc: dt.datetime) -> tuple[str, dt.datetime]:
    """Prochaine bascule tarifaire → (état après bascule, horodatage)."""
    boundaries = (1, 4, 6, 10)  # heures UTC des changements
    nxt = None
    for bd in boundaries:
        cand = now_utc.replace(hour=bd, minute=0, second=0, microsecond=0)
        if cand > now_utc:
            nxt = cand
            break
    if nxt is None:  # après 10h UTC → bascule à 01h le lendemain
        nxt = (now_utc + dt.timedelta(days=1)).replace(
            hour=1, minute=0, second=0, microsecond=0
        )
    state = "peak" if nxt.hour in (1, 6) else "off-peak"
    return state, nxt


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
            self._data.setdefault("day_split", {})
            self._data.setdefault("months_peak", {})
            self._data.setdefault("months_offpeak", {})
        return self._data

    @staticmethod
    def _now() -> dt.datetime:
        return dt.datetime.now().astimezone()

    async def record(self, cur_total: float, cur_topped: float) -> tuple[float, float]:
        """Enregistre un point de solde ; renvoie (spend_today, spend_month).

        top-up détecté : si topped_up augmente, l'écart n'est pas compté comme dépense
        et la recharge est mémorisée (montant + horodatage).
        La dépense est aussi ventilée peak / off-peak selon le tarif en vigueur
        à l'instant du poll (approximation : pas de timestamps par requête).
        """
        data = await self._ensure()
        now = self._now()
        day_key = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")
        bucket = tariff_at(now.astimezone(dt.timezone.utc).hour)

        days: dict[str, float] = data["days"]
        months: dict[str, float] = data["months"]
        months_peak: dict[str, float] = data["months_peak"]
        months_offpeak: dict[str, float] = data["months_offpeak"]
        days.setdefault(day_key, 0.0)
        months.setdefault(month_key, 0.0)
        months_peak.setdefault(month_key, 0.0)
        months_offpeak.setdefault(month_key, 0.0)
        day_split: dict[str, dict[str, float]] = data["day_split"]
        day_split.setdefault(day_key, {"peak": 0.0, "off-peak": 0.0})

        last_total = data["last_total"]
        last_topped = data["last_topped"]

        if last_total is None or last_topped is None:
            # Premier point : pas encore de dépense mesurable.
            data["last_total"] = cur_total
            data["last_topped"] = cur_topped
        else:
            topup = max(0.0, cur_topped - last_topped)
            if topup > 0:
                data["last_topup"] = {"amount": topup, "ts": now.isoformat()}
            spend = (last_total + topup) - cur_total
            if spend < 0:
                spend = 0.0
            days[day_key] += spend
            months[month_key] += spend
            day_split[day_key][bucket] += spend
            if bucket == "peak":
                months_peak[month_key] += spend
            else:
                months_offpeak[month_key] += spend
            data["last_total"] = cur_total
            data["last_topped"] = cur_topped

        # Nettoyage : garder ~62 jours et 13 mois.
        keep_days = sorted(days, reverse=True)[:62]
        for k in list(days):
            if k not in keep_days:
                days.pop(k, None)
                day_split.pop(k, None)
        keep_months = sorted(months, reverse=True)[:13]
        for k in list(months):
            if k not in keep_months:
                months.pop(k, None)
                months_peak.pop(k, None)
                months_offpeak.pop(k, None)

        await self._store.async_save(data)
        return days.get(day_key, 0.0), months.get(month_key, 0.0)

    async def details(self) -> dict[str, Any]:
        """Copie des données utiles aux capteurs dérivés (historique + ventilation)."""
        data = await self._ensure()
        return {
            "days": dict(data["days"]),
            "months": dict(data["months"]),
            "day_split": {k: dict(v) for k, v in data["day_split"].items()},
            "months_peak": dict(data["months_peak"]),
            "months_offpeak": dict(data["months_offpeak"]),
            "last_topup": data.get("last_topup"),
        }


class DeepSeekCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polling périodique + exposition des soldes, dépenses et tarifs."""

    def __init__(self, hass: HomeAssistant, entry_id: str, api_key: str, currency: str, scan_interval_min: int) -> None:
        self._api_key = api_key
        self._currency = currency
        self.usage_store = DeepSeekUsageStore(hass, entry_id)
        self.spend_today: float = 0.0
        self.spend_month: float = 0.0
        self.last_success_ts: float | None = None
        self._next_ts: dt.datetime | None = None
        self._ticker_started = False
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
        self.last_success_ts = time.time()

        det = await self.usage_store.details()
        now_local = dt.datetime.now().astimezone()
        today_key = now_local.strftime("%Y-%m-%d")
        month_key = now_local.strftime("%Y-%m")

        past = [v for k, v in sorted(det["days"].items()) if k < today_key][-30:]
        if past:
            avg30 = round(sum(past) / len(past), 3)
        else:
            avg30 = None  # pas encore d'historique
        days_left = round(total / avg30, 1) if avg30 and avg30 > 0 else None

        if self.spend_month > 0 and now_local.day:
            dim = calendar.monthrange(now_local.year, now_local.month)[1]
            monthly_projection = round(self.spend_month / now_local.day * dim, 2)
        else:
            monthly_projection = None

        today_split = det["day_split"].get(today_key, {"peak": 0.0, "off-peak": 0.0})
        month_peak = det["months_peak"].get(month_key, 0.0)
        month_offpeak = det["months_offpeak"].get(month_key, 0.0)
        potential_savings = round(month_peak / 2, 2) if month_peak > 0 else 0.0

        now_utc = dt.datetime.now(dt.timezone.utc)
        tariff = tariff_at(now_utc.hour)
        next_state, next_ts = next_tariff_change(now_utc)
        self._next_ts = next_ts

        if not self._ticker_started:
            self._ticker_started = True
            async_track_time_interval(
                self.hass, self._minute_tick, dt.timedelta(seconds=60)
            )

        remaining_min = max(0.0, (next_ts.timestamp() - time.time()) / 60.0)

        last_topup = det.get("last_topup") or {}
        return {
            "currency": currency,
            "total_balance": total,
            "granted_balance": granted,
            "topped_up_balance": topped,
            "spend_today": self.spend_today,
            "spend_month": self.spend_month,
            "last_topup_amount": last_topup.get("amount"),
            "last_topup_ts": last_topup.get("ts"),
            "avg_daily_spend_30d": avg30,
            "days_left": days_left,
            "monthly_projection": monthly_projection,
            "tariff": tariff,
            "next_tariff_state": next_state,
            "next_tariff_change": next_ts.isoformat(),
            "tariff_change_in_min": round(remaining_min, 1),
            "spend_today_peak": today_split.get("peak", 0.0),
            "spend_today_offpeak": today_split.get("off-peak", 0.0),
            "spend_month_peak": month_peak,
            "spend_month_offpeak": month_offpeak,
            "potential_savings_month": potential_savings,
            "pricing_grid": PRICING_GRID,
            "last_success_ts": self.last_success_ts,
        }

    async def _minute_tick(self, _now: dt.datetime) -> None:
        """Tick minute : met à jour le compte à rebours sans toucher l'API.

        Gère aussi le franchissement d'une frontière tarifaire (bascule
        auto peak/off-peak + calcul du changement suivant).
        """
        if self.data is None or self._next_ts is None:
            return
        now = dt.datetime.now().astimezone()
        new_data = dict(self.data)
        tariff_changed = False

        if now >= self._next_ts:
            # Frontière franchie : on bascule et on calcule la suivante.
            new_data["tariff"] = new_data.get("next_tariff_state", "off-peak")
            now_utc = dt.datetime.now(dt.timezone.utc)
            next_state, next_ts = next_tariff_change(now_utc)
            self._next_ts = next_ts
            new_data["next_tariff_state"] = next_state
            new_data["next_tariff_change"] = next_ts.isoformat()
            tariff_changed = True

        remaining_min = max(0.0, (self._next_ts.timestamp() - time.time()) / 60.0)
        new_rounded = round(remaining_min, 1)
        if not tariff_changed and new_rounded == new_data.get("tariff_change_in_min"):
            return  # rien de nouveau à publier
        new_data["tariff_change_in_min"] = new_rounded
        self.async_set_updated_data(new_data)
