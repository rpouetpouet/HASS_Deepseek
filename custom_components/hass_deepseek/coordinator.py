"""Coordinateur : polling du solde DeepSeek + suivi local des dépenses."""

from __future__ import annotations

import calendar
import datetime as dt
import logging
import time
from typing import Any, Callable

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_BALANCE_URL,
    CONF_API_KEY,
    HOLIDAYS_CN,
    PEAK_WINDOWS_UTC,
    PRICING_GRID,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


# Heures UTC auxquelles le tarif peut basculer (début/fin de chaque fenêtre pleine).
_TARIFF_BOUNDARIES_UTC = (1, 4, 6, 10)

# Fuseau de la Chine (UTC+8) : les jours fériés sont des journées civiles locales,
# et les fenêtres pleines (01-04 et 06-10 UTC) tombent le même jour civil chinois.
CN_TZ = dt.timezone(dt.timedelta(hours=8))

# Fuseau des journees DeepSeek : 00:00 UTC+1 FIXE, verifie sur les exports natifs
# (toutes les bornes start_time_iso/end_time_iso portent +01:00, meme en ete).
# En hiver cela coincide avec Paris ; en ete (CEST) la journee plateforme commence
# a 01:00 Paris -> les buckets doivent etre calcules ici, pas en heure locale.
PLATFORM_TZ = dt.timezone(dt.timedelta(hours=1), "DeepSeek day (UTC+1)")

# Profondeur de recherche de la prochaine bascule, en jours. Doit couvrir les
# plus longues interruptions de fenêtres pleines : Nouvel An chinois (9 jours
# en 2026) et Golden Week (7 jours), week-end accolé inclus.
_TARIFF_SCAN_DAYS = 21


def _is_holiday_cn(when_utc: dt.datetime) -> bool:
    """Jour férié chinois ? (date LOCALE chinoise, pas la date UTC)."""
    return when_utc.astimezone(CN_TZ).date().isoformat() in HOLIDAYS_CN


def tariff_at(when_utc: dt.datetime) -> str:
    """Renvoie 'peak' ou 'off-peak' pour un instant UTC donné.

    Samedi/dimanche (UTC) et jours fériés chinois = heures creuses toute la
    journée. La condition de jour est arrivée APRÈS la grille de prix (effective
    le 23/08/2026) et la clause « excluding Chinese public holidays » encore
    après (ajoutée à la page pricing entre le 17/09 et le 22/09/2026, cf.
    const.py) : ne jamais tester les seules fenêtres horaires, sinon 14 h par
    semaine (week-end) + 3 h par férié ouvré sont annoncées à tort en « peak »
    et les capteurs d'économies sont surestimés.
    """
    if when_utc.weekday() >= 5 or _is_holiday_cn(when_utc):
        return "off-peak"
    for start, end in PEAK_WINDOWS_UTC:
        if start <= when_utc.hour < end:
            return "peak"
    return "off-peak"


def next_tariff_change(now_utc: dt.datetime) -> tuple[str, dt.datetime]:
    """Prochaine bascule tarifaire → (état après bascule, horodatage).

    Les bascules n'ont lieu qu'aux heures 01/04/06/10 UTC. Comme le week-end et
    les jours fériés chinois sont entièrement creux, la prochaine bascule après
    vendredi 10:00 UTC est le lundi 01:00 UTC (le compte à rebours saute donc le
    week-end), et après le dernier jour ouvré avant une Golden Week elle tombe
    jusqu'à 10 jours plus loin : d'où un balayage large (_TARIFF_SCAN_DAYS) —
    un balayage trop court retomberait sur le repli « inatteignable » et
    annoncerait une bascule fantôme.
    """
    current = tariff_at(now_utc)
    base = now_utc.replace(minute=0, second=0, microsecond=0)
    for day_offset in range(_TARIFF_SCAN_DAYS):
        day = base + dt.timedelta(days=day_offset)
        for boundary in _TARIFF_BOUNDARIES_UTC:
            candidate = day.replace(hour=boundary)
            if candidate <= now_utc:
                continue
            state = tariff_at(candidate)
            if state != current:
                return state, candidate
    return current, base + dt.timedelta(days=1)  # repli théoriquement inatteignable


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
            self._data.setdefault("last_granted", None)
            self._data.setdefault("last_ts", None)
            self._data.setdefault("unallocated", 0.0)
            self._data.setdefault("days", {})
            self._data.setdefault("months", {})
            self._data.setdefault("day_split", {})
            self._data.setdefault("months_peak", {})
            self._data.setdefault("months_offpeak", {})
        return self._data

    @staticmethod
    def _now() -> dt.datetime:
        return dt.datetime.now().astimezone()

    async def record(
        self,
        cur_total: float,
        cur_granted: float,
        cur_topped: float,
        max_gap_min: float,
    ) -> tuple[float, float]:
        """Enregistre un point de solde ; renvoie (spend_today, spend_month).

        top-up / crédit offert détectés : si topped_up ou granted augmentent, l'écart
        n'est pas compté comme dépense et la recharge est mémorisée (montant + date).

        Trou de mesure : si le dernier relevé date de plus de ``max_gap_min`` minutes,
        le delta n'est PAS attribué au jour courant (il couvre plusieurs jours qu'on ne
        sait plus répartir) : il part dans ``unallocated`` et lève un WARNING. Sans ce
        garde-fou, un poll qui repart après plusieurs jours verse tout le trou sur la
        journée en cours (constaté : 2,11 $ d'octobre comptés sur le 1er novembre).

        La dépense est aussi ventilée peak / off-peak selon le tarif en vigueur
        à l'instant du poll (approximation : pas de timestamps par requête).
        """
        data = await self._ensure()
        now = self._now()
        platform_now = now.astimezone(PLATFORM_TZ)
        day_key = platform_now.strftime("%Y-%m-%d")
        month_key = platform_now.strftime("%Y-%m")
        bucket = tariff_at(now.astimezone(dt.timezone.utc))

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
        last_granted = data["last_granted"]
        last_ts_iso = data["last_ts"]

        gap_min: float | None = None
        if last_ts_iso:
            try:
                gap_min = (now.timestamp() - dt.datetime.fromisoformat(last_ts_iso).timestamp()) / 60.0
            except (TypeError, ValueError):
                gap_min = None

        if last_total is None or last_topped is None or last_granted is None:
            # Premier point : pas encore de dépense mesurable.
            data["last_total"] = cur_total
            data["last_topped"] = cur_topped
            data["last_granted"] = cur_granted
            data["last_ts"] = now.isoformat()
        else:
            topup = max(0.0, cur_topped - last_topped)
            grant = max(0.0, cur_granted - last_granted)
            if topup > 0:
                # Recharge ET consommation dans la même fenêtre : le montant exact de
                # la recharge est indécidable (topped_up baisse avec la conso), donc la
                # dépense de la fenêtre est au mieux une borne basse. On la signale.
                data["last_topup"] = {
                    "amount": topup,
                    "ts": now.isoformat(),
                    "ambiguous": True,
                    "gap_min": round(gap_min, 1) if gap_min is not None else None,
                }
                _LOGGER.warning(
                    "Recharge détectée (%.2f) depuis le relevé précédent : la dépense "
                    "de cette fenêtre ne peut pas être isolée (poll suivant à réduire).",
                    topup,
                )
            spend = (last_total + topup + grant) - cur_total
            if spend < 0:
                # Solde remonté sans recharge détectée : écart à expliquer, pas une dépense.
                data["unallocated"] = data.get("unallocated", 0.0) + spend
                spend = 0.0
            if gap_min is not None and gap_min > max_gap_min:
                _LOGGER.warning(
                    "Trou de mesure de %.0f min (max %.0f) : %.4f %s non attribués à %s",
                    gap_min,
                    max_gap_min,
                    spend,
                    data.get("currency", "USD"),
                    day_key,
                )
                data["unallocated"] = data.get("unallocated", 0.0) + spend
            else:
                days[day_key] += spend
                months[month_key] += spend
                day_split[day_key][bucket] += spend
                if bucket == "peak":
                    months_peak[month_key] += spend
                else:
                    months_offpeak[month_key] += spend
            data["last_total"] = cur_total
            data["last_topped"] = cur_topped
            data["last_granted"] = cur_granted
            data["last_ts"] = now.isoformat()

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
            "unallocated": float(data.get("unallocated") or 0.0),
            "last_ts": data.get("last_ts"),
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
        self._unsub_ticker: Callable[[], None] | None = None
        # Un delta mesuré au-delà de ce trou n'est pas attribuable à un jour précis.
        self._max_gap_min: float = max(90.0, 3.0 * float(scan_interval_min))
        super().__init__(
            hass,
            _LOGGER,
            name="hass_deepseek",
            update_interval=dt.timedelta(minutes=scan_interval_min),
        )

    @callback
    def async_start_ticker(self) -> None:
        """Enregistre le tick minute, une seule fois, hors du cycle de refresh.

        Enregistré auparavant à l'intérieur de `_async_update_data`, le ticker ne
        survivait pas au premier refresh des entités : plus aucun état n'était publié
        ensuite (constaté : un seul relevé par démarrage de HA).
        """
        if self._unsub_ticker is not None:
            return
        self._unsub_ticker = async_track_time_interval(
            self.hass, self._minute_tick, dt.timedelta(seconds=60)
        )

    @callback
    def async_stop_ticker(self) -> None:
        """Désenregistre le tick minute (déchargement / rechargement de l'entrée)."""
        if self._unsub_ticker is not None:
            self._unsub_ticker()
            self._unsub_ticker = None

    async def async_shutdown(self) -> None:
        """Arrête le ticker avant l'arrêt du coordinateur."""
        self.async_stop_ticker()
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        info = await fetch_balance(self.hass, self._api_key)
        currency = info.get("currency") or self._currency
        total = float(info.get("total_balance") or 0)
        granted = float(info.get("granted_balance") or 0)
        topped = float(info.get("topped_up_balance") or 0)

        self.spend_today, self.spend_month = await self.usage_store.record(
            total, granted, topped, self._max_gap_min
        )
        self.last_success_ts = time.time()

        det = await self.usage_store.details()
        # Meme decoupage que la plateforme (UTC+1 fixe), sinon les jours d'ete sont
        # decales d'une heure et incomparables au cout affiche par DeepSeek.
        now_local = dt.datetime.now().astimezone().astimezone(PLATFORM_TZ)
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
        tariff = tariff_at(now_utc)
        next_state, next_ts = next_tariff_change(now_utc)
        self._next_ts = next_ts

        remaining_min = max(0.0, (next_ts.timestamp() - time.time()) / 60.0)
        remaining_int = int(round(remaining_min))

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
            "tariff_change_in_min": remaining_int,
            "spend_today_peak": today_split.get("peak", 0.0),
            "spend_today_offpeak": today_split.get("off-peak", 0.0),
            "spend_month_peak": month_peak,
            "spend_month_offpeak": month_offpeak,
            "potential_savings_month": potential_savings,
            "pricing_grid": PRICING_GRID,
            "last_success_ts": self.last_success_ts,
            "last_poll_ts": det.get("last_ts"),
            "unallocated_spend": det.get("unallocated", 0.0),
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
        new_rounded = int(round(remaining_min))
        if not tariff_changed and new_rounded == new_data.get("tariff_change_in_min"):
            return  # rien de nouveau à publier
        new_data["tariff_change_in_min"] = new_rounded
        # NE PAS appeler async_set_updated_data ici : il annule le refresh programme
        # puis le recale d'un intervalle complet (cf. _schedule_refresh) a CHAQUE tick
        # de 60 s -> le poll periodique ne se declenche jamais (un seul poll par
        # demarrage de HA, constate les 29/10 -> 01/11/2026). On publie sans timer.
        self.data = new_data
        self.async_update_listeners()
