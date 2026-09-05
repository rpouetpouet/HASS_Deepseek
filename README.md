# HASS_Deepseek

Intégration **Home Assistant** (custom component) qui affiche le **solde et la consommation estimée** de ton compte **DeepSeek API**.

> ⚠️ **V1 — API-native.** DeepSeek n'expose publiquement que `/user/balance`. Les capteurs de dépense sont donc **calculés par différence de solde** (avec détection des recharges). Les stats détaillées par tokens/modèle ne sont pas disponibles via l'API publique.

## Fonctionnalités

- **Config flow** : saisie de la clé API + **intervalle de polling paramétrable** (5 min – 24 h, défaut 60 min), modifiable ensuite dans Options.
- Capteurs (par devise du compte, ex. USD) :
  - `Solde total` (monétaire)
  - `Crédit rechargé` (topped-up)
  - `Crédit offert` (granted — diagnostique)
  - `Dépense aujourd'hui` — delta de solde du jour
  - `Dépense ce mois-ci` — delta de solde du mois
- **Détection automatique des recharges** : quand `topped_up` augmente, la différence n'est pas comptée comme une dépense (stockage local HA, persistant entre redémarrages).
- Device « DeepSeek » avec entité de diagnostic, attributs (currency, is_available, dernière mise à jour).

## Installation

### Manuelle (recommandée pour un repo privé)

1. Copier le dossier `custom_components/hass_deepseek/` dans le dossier `custom_components/` de ton installation HA.
2. Redémarrer HA (ou *Paramètres → Système → Redémarrer*).
3. *Paramètres → Appareils & services → Ajouter une intégration → **DeepSeek Usage & Balance***.
4. Saisir ta clé API DeepSeek (`https://platform.deepseek.com/api_keys`) et l'intervalle de polling.
5. Valider — la connexion est testée avant création.

## Capteurs

| Entité | Classe | Description |
|---|---|---|
| `sensor.deepseek_balance` | monetary | Solde total du compte (USD) |
| `sensor.deepseek_topped_up_balance` | monetary | Crédit rechargé |
| `sensor.deepseek_granted_balance` | monetary | Crédit offert (diagnostic) |
| `sensor.deepseek_daily_spend` | monetary | Dépense estimée du jour (delta de solde) |
| `sensor.deepseek_monthly_spend` | monetary | Dépense estimée du mois (delta de solde) |

## Limites connues (V1)

- Le solde API a une granularité de **2 décimales** → les très petites dépenses journalières peuvent apparaître à `0.00`.
- La dépense est une **estimation par différence de solde**, pas la facture exacte de la plateforme (qui inclut tokens/cache).
- Une recharge **offerte** (granted) qui augmente sans `topped_up` n'est pas détectée (rare).

## Dépannage

- `cannot_connect` : API injoignable ou clé invalide.
- Logs : recherche `hass_deepseek` dans *Paramètres → Système → Journaux*.

## Licence

MIT — © 2026 rpouetpouet
