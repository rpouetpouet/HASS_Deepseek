"""Constantes pour l'intégration DeepSeek Usage & Balance."""

from __future__ import annotations

DOMAIN = "hass_deepseek"

CONF_API_KEY = "api_key"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes (24 h)

API_BALANCE_URL = "https://api.deepseek.com/user/balance"

PLATFORMS = ["sensor"]

# Nom du fichier JSON de stockage des dépenses (par config entry)
STORAGE_VERSION = 1
