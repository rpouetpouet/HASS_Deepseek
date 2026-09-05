"""Constantes pour l'intégration DeepSeek Usage & Balance."""

from __future__ import annotations

DOMAIN = "hass_deepseek"

CONF_API_KEY = "api_key"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes (24 h)

API_BALANCE_URL = "https://api.deepseek.com/user/balance"

# Fenêtres tarifaires officielles DeepSeek (heures UTC) — depuis le 16/08/2026
# Heures pleines : 01:00-04:00 et 06:00-10:00 UTC ; le reste = heures creuses (−50 %).
PEAK_WINDOWS_UTC: tuple[tuple[int, int], ...] = ((1, 4), (6, 10))
PRICING_EFFECTIVE = "2026-08-16"

# Grille tarifaire officielle en USD par million de tokens : (peak, off-peak).
PRICING_GRID: dict[str, dict[str, tuple[float, float]]] = {
    "deepseek-v4-flash": {
        "cache_hit": (0.014, 0.007),
        "cache_miss": (0.44, 0.22),
        "output": (1.32, 0.66),
    },
    "deepseek-v4-pro": {
        "cache_hit": (0.044, 0.022),
        "cache_miss": (1.32, 0.66),
        "output": (3.96, 1.98),
    },
}

PLATFORMS = ["binary_sensor", "sensor"]

# Nom du fichier JSON de stockage des dépenses (par config entry)
STORAGE_VERSION = 1
