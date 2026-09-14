"""Constantes pour l'intégration DeepSeek Usage & Balance."""

from __future__ import annotations

DOMAIN = "hass_deepseek"

CONF_API_KEY = "api_key"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes (24 h)

API_BALANCE_URL = "https://api.deepseek.com/user/balance"

# Fenêtres tarifaires officielles DeepSeek (heures UTC) — grille du 14/09/2026.
# ATTENTION : deux dates distinctes, ne pas les confondre.
#   - grille de PRIX (montants ci-dessous) : 16/08/2026, révisée le 10/09/2026
#     (baisse V4.1-Flash) et relevée le 14/09/2026 ;
#   - règle de JOUR : « jours ouvrés uniquement » annoncée le 22/08/2026,
#     effective le 23/08/2026 00:00 heure de Pékin (week-end = creux toute la
#     journée). Avant cette date, les fenêtres s'appliquaient 7 j/7.
# Heures pleines : 01:00-04:00 et 06:00-10:00 UTC du lundi au vendredi ;
# tout le reste = heures creuses (-50 %), week-end inclus.
# Source : https://api-docs.deepseek.com/quick_start/pricing (relevée le 14/09/2026).
PEAK_WINDOWS_UTC: tuple[tuple[int, int], ...] = ((1, 4), (6, 10))
PRICING_EFFECTIVE = "2026-09-14"

# Grille tarifaire officielle en USD par million de tokens : (peak, off-peak).
FLASH_RATES: dict[str, tuple[float, float]] = {
    "cache_hit": (0.006, 0.003),
    "cache_miss": (0.30, 0.15),
    "output": (1.20, 0.60),
}

PRICING_GRID: dict[str, dict[str, tuple[float, float]]] = {
    # Nom canonique depuis le 10/09/2026 (DeepSeek-V4.1-Flash).
    "deepseek-flash": FLASH_RATES,
    # Alias legacy encore acceptés par l'API : routés vers V4.1-Flash,
    # facturés au prix Flash.
    "deepseek-v4-flash": FLASH_RATES,
    "deepseek-v4-flash-vision-exp": FLASH_RATES,
    # V4-Pro : depuis le 14/09/2026 12:00 Pékin (04:00 UTC), les requêtes
    # `deepseek-v4-pro` sont routées vers V4.1-Flash et facturées au prix
    # Flash, en attendant la sortie de V4.1-Pro.
    "deepseek-v4-pro": FLASH_RATES,
}

PLATFORMS = ["binary_sensor", "sensor"]

# Nom du fichier JSON de stockage des dépenses (par config entry)
STORAGE_VERSION = 1
