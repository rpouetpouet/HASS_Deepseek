# DeepSeek Usage & Balance for Home Assistant

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rpouetpouet&repository=HASS_Deepseek&category=integration)

A **Home Assistant custom integration** that shows your **DeepSeek API account balance and estimated spend** directly in Home Assistant.

> ⚠️ **V1 — API-native.** The DeepSeek public API only exposes `/user/balance`. Spend sensors are therefore **computed from balance deltas** (with automatic top-up detection). Detailed per-token / per-model statistics are not available through the public API.

## Features

- **Config flow**: paste your API key, choose a **polling interval** (5 min – 24 h, default 60 min) — changeable later via *Options*.
- Sensors (in your account currency, e.g. USD):
  - `Total balance`
  - `Topped-up credit`
  - `Granted credit` (diagnostics)
  - `Today's spend` — balance delta of the day
  - `This month's spend` — balance delta of the month
  - `Last top-up` — amount (with timestamp attribute)
  - `Projected month spend` — current burn rate extrapolated to month end
  - `Average daily spend (30d)` — rolling average from locally stored history
  - `Estimated days left` — balance ÷ average daily spend
- **Binary sensor `API status`**: on when the DeepSeek API is reachable (device class `connectivity`).
- **Automatic top-up detection**: when the topped-up balance increases, the difference is **not** counted as spend (local state, persists across restarts).
- **Daily spend history is stored locally** (~62 days), powering the rolling averages — no dependency on the platform CSV export.
- One “DeepSeek” device with a diagnostics entity exposing `currency`, `api_is_available` and last update attributes.

## Installation

### HACS (recommended)

1. Click the badge above — or add the repository manually:
   **HACS → ⋯ → Custom repositories** → `https://github.com/rpouetpouet/HASS_Deepseek` → category **Integration**.
2. **Download** the latest release.
3. **Restart Home Assistant.**
4. *Settings → Devices & Services → Add Integration → **DeepSeek Usage & Balance***.

### Manual

1. Copy the `custom_components/hass_deepseek/` folder into the `custom_components/` directory of your Home Assistant installation.
2. Restart Home Assistant.
3. Add the integration as above.

## Configuration

During setup you will be asked for:

| Field | Description |
|---|---|
| **API key** | Create one at <https://platform.deepseek.com/api_keys> |
| **Polling interval** | How often the balance is fetched (5 min – 24 h, default 60 min) |

The connection is tested before the configuration entry is created.

## Sensors

| Entity | Device class | Description |
|---|---|---|
| `sensor.deepseek_balance` | monetary | Total account balance |
| `sensor.deepseek_topped_up_balance` | monetary | Topped-up credit |
| `sensor.deepseek_granted_balance` | monetary | Granted credit (diagnostics) |
| `sensor.deepseek_daily_spend` | monetary | Estimated spend today (balance delta) |
| `sensor.deepseek_monthly_spend` | monetary | Estimated spend this month (balance delta) |
| `sensor.deepseek_last_topup_amount` | monetary | Amount of the last detected top-up (`last_topup_ts` attribute) |
| `sensor.deepseek_monthly_projection` | monetary | Projected spend at current pace for the ongoing month |
| `sensor.deepseek_avg_daily_spend_30d` | monetary | Rolling average daily spend (last ~30 days of local history) |
| `sensor.deepseek_days_left` | — (days) | Balance ÷ average daily spend — rough autonomy estimate |
| `binary_sensor.deepseek_api` | connectivity | ON when the DeepSeek API is reachable |

## Known limitations (V1)

- The balance API has a granularity of **2 decimals** — very small daily spends may show as `0.00`.
- Spend is an **estimate from balance deltas**, not the exact platform invoice (which includes tokens/cache pricing).
- A **granted** credit increase without a topped-up change is not detected (rare).

## Troubleshooting

- `cannot_connect`: API unreachable or invalid key.
- Logs: search for `hass_deepseek` in *Settings → System → Logs*.
- **Icons**: the DeepSeek brand images require Home Assistant **2026.3+** (`brand/` folder support); the integration itself works on older versions.

## Disclaimer

Unofficial project — not affiliated with or endorsed by DeepSeek.

## License

MIT — © 2026 rpouetpouet
