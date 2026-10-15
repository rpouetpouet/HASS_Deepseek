"""Constantes pour l'intégration DeepSeek Usage & Balance."""

from __future__ import annotations

DOMAIN = "hass_deepseek"

CONF_API_KEY = "api_key"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes (24 h)

API_BALANCE_URL = "https://api.deepseek.com/user/balance"

# Fenêtres tarifaires officielles DeepSeek (heures UTC).
# ATTENTION : trois dates distinctes, ne pas les confondre.
#   - grille de PRIX (montants ci-dessous) : 16/08/2026, révisée le 10/09/2026
#     (baisse V4.1-Flash) ; ligne V4-Pro rétablie le 15/10/2026 (cf. PRO_RATES) ;
#   - règle de JOUR : « jours ouvrés uniquement » annoncée le 22/08/2026,
#     effective le 23/08/2026 00:00 heure de Pékin (week-end = creux toute la
#     journée). Avant cette date, les fenêtres s'appliquaient 7 j/7 ;
#   - règle des JOURS FÉRIÉS : « excluding Chinese public holidays… including
#     weekends and Chinese public holidays in full » ajoutée à la page pricing
#     entre le 17/09/2026 (snapshot sans la clause) et le 22/09/2026 (avec).
# Heures pleines : 01:00-04:00 et 06:00-10:00 UTC du lundi au vendredi, hors
# jours fériés chinois ; tout le reste = heures creuses (-50 %), week-end et
# jours fériés chinois inclus.
# Source : https://api-docs.deepseek.com/quick_start/pricing (vérifiée en direct
# le 15/10/2026 18:51 UTC).
PEAK_WINDOWS_UTC: tuple[tuple[int, int], ...] = ((1, 4), (6, 10))
PRICING_EFFECTIVE = "2026-10-15"

# Grille tarifaire officielle en USD par million de tokens : (peak, off-peak).
FLASH_RATES: dict[str, tuple[float, float]] = {
    "cache_hit": (0.006, 0.003),
    "cache_miss": (0.30, 0.15),
    "output": (1.20, 0.60),
}

# V4-Pro : service maintenu et facturé à ses propres tarifs (V4-Pro-0813).
# La page pricing a publié du 11/09 au 17/09/2026 la note « we have decided to
# continue providing API services for DeepSeek V4 Pro after September 14, 2026,
# with the billing method remaining unchanged » ; cette note a disparu entre le
# 17/09 et le 22/09/2026 et le modèle est redevenu une ligne normale du tableau.
# Vérifié le 15/10/2026 : GET /models renvoie exactement {deepseek-flash,
# deepseek-v4-pro}, et /chat/completions avec model=deepseek-v4-pro ré-écho
# « deepseek-v4-pro » (alors que les alias flash legacy ré-échoent
# « deepseek-flash ») ⇒ ce n'est PAS un alias routé vers V4.1-Flash.
PRO_RATES: dict[str, tuple[float, float]] = {
    "cache_hit": (0.044, 0.022),
    "cache_miss": (1.32, 0.66),
    "output": (3.96, 1.98),
}

PRICING_GRID: dict[str, dict[str, tuple[float, float]]] = {
    # Nom canonique depuis le 10/09/2026 (DeepSeek-V4.1-Flash).
    "deepseek-flash": FLASH_RATES,
    # Alias legacy encore acceptés par l'API : servis par V4.1-Flash,
    # facturés au prix Flash.
    "deepseek-v4-flash": FLASH_RATES,
    "deepseek-v4-flash-vision-exp": FLASH_RATES,
    # Modèle V4-Pro, toujours servi (cf. PRO_RATES).
    "deepseek-v4-pro": PRO_RATES,
}

# ---------------------------------------------------------------------------
# Jours fériés chinois (dates locales CN, format ISO « AAAA-MM-JJ »).
#
# DeepSeek applique les heures creuses EN ENTIER sur ces journées : « Peak hours
# are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday, excluding
# Chinese public holidays. All other hours are off-peak, including weekends and
# Chinese public holidays in full. » Les samedis/dimanches fériés figurent dans
# la liste par lisibilité (ils sont creux de toute façon), et les samedis ou
# dimanches de rattrapage (调休 travaillés) RESTENT creux : DeepSeek précise
# « weekends off-peak in full ».
#
# ⚠️ DeepSeek ne publie PAS la liste des jours fériés : elle doit être tenue à
# jour ici. Source officielle = avis annuel du Conseil d'État, publié vers
# début novembre pour l'année suivante (english.www.gov.cn) ; la liste
# statutaire de base est fixée par le décret n° 795 du Conseil d'État.
# ---------------------------------------------------------------------------

# 2026 — liste OFFICIELLE, texte intégral : 国务院办公厅关于2026年部分节假日安排的通知,
# 国办发明电〔2025〕7号, publié le 04/11/2025, vérifié le 15/10/2026 sur
# https://www.gov.cn/zhengce/zhengceku/202511/content_7047091.htm
# (identique à la version du bulletin officiel du Conseil d'État).
HOLIDAYS_CN_2026: tuple[str, ...] = (
    "2026-01-01", "2026-01-02", "2026-01-03",  # 元旦
    "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19",  # 春节
    "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23",
    "2026-04-04", "2026-04-05", "2026-04-06",  # 清明
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",  # 劳动节
    "2026-06-19", "2026-06-20", "2026-06-21",  # 端午
    "2026-09-25", "2026-09-26", "2026-09-27",  # 中秋
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",  # 国庆
    "2026-10-05", "2026-10-06", "2026-10-07",
)

# 2027 — PROVISOIRE. L'avis annuel du Conseil d'État pour 2027 n'était PAS
# publié au 15/10/2026 (il paraît vers début novembre) : seules les dates
# statutaires du décret n° 795 sont certaines (元旦 1 j ; 春节 4 j = veille +
# 3 premiers jours ; 清明 1 j ; 劳动节 2 j ; 端午 1 j ; 中秋 1 j ; 国庆 3 j).
# Les ponts (调休) allongeront ces fenêtres : À COMPLÉTER dès la publication de
# l'avis 2027, sinon quelques heures de « peak » seront annoncées à tort.
HOLIDAYS_CN_2027_PROVISIONAL: tuple[str, ...] = (
    "2027-01-01",  # 元旦
    "2027-02-05", "2027-02-06", "2027-02-07",  # 春节 (除夕 / 初一 / 初二-初三 tombent le we)
    "2027-04-05",  # 清明
    "2027-05-01", "2027-05-02",  # 劳动节
    "2027-06-09",  # 端午
    "2027-09-15",  # 中秋
    "2027-10-01", "2027-10-02", "2027-10-03",  # 国庆
)

HOLIDAYS_CN: frozenset[str] = frozenset(
    HOLIDAYS_CN_2026 + HOLIDAYS_CN_2027_PROVISIONAL
)

PLATFORMS = ["binary_sensor", "sensor"]

# Nom du fichier JSON de stockage des dépenses (par config entry)
STORAGE_VERSION = 1
