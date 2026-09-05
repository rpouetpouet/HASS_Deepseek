"""Capteurs DeepSeek : soldes + dépenses dérivées."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DeepSeekCoordinator
from .const import DOMAIN

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="total_balance",
        translation_key="total_balance",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="topped_up_balance",
        translation_key="topped_up_balance",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="granted_balance",
        translation_key="granted_balance",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="spend_today",
        translation_key="spend_today",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="spend_month",
        translation_key="spend_month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="last_topup_amount",
        translation_key="last_topup_amount",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="monthly_projection",
        translation_key="monthly_projection",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="avg_daily_spend_30d",
        translation_key="avg_daily_spend_30d",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="days_left",
        translation_key="days_left",
        device_class=None,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="tariff",
        translation_key="tariff",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="spend_today_peak",
        translation_key="spend_today_peak",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="spend_today_offpeak",
        translation_key="spend_today_offpeak",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="spend_month_peak",
        translation_key="spend_month_peak",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="spend_month_offpeak",
        translation_key="spend_month_offpeak",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="potential_savings_month",
        translation_key="potential_savings_month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
    ),
)

# Clés dont la valeur est un montant (unit = devise)
_MONETARY_KEYS = {
    "total_balance",
    "topped_up_balance",
    "granted_balance",
    "spend_today",
    "spend_month",
    "last_topup_amount",
    "monthly_projection",
    "avg_daily_spend_30d",
    "spend_today_peak",
    "spend_today_offpeak",
    "spend_month_peak",
    "spend_month_offpeak",
    "potential_savings_month",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute les capteurs pour cette entrée."""
    coordinator: DeepSeekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DeepSeekSensor(coordinator, entry, description) for description in SENSORS
    )


class DeepSeekSensor(CoordinatorEntity[DeepSeekCoordinator], SensorEntity):
    """Capteur lié au coordinateur."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DeepSeekCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "DeepSeek",
            "model": "API Account",
        }

    @property
    def native_value(self) -> float | str | None:
        data = self.coordinator.data
        if data is None:
            return None
        return data.get(self.entity_description.key)

    @property
    def icon(self) -> str | None:
        """Icône dynamique pour le capteur de période tarifaire."""
        if self.entity_description.key != "tariff":
            return None
        data = self.coordinator.data
        return (
            "mdi:white-balance-sunny" if data and data.get("tariff") == "peak" else "mdi:weather-night"
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.key in _MONETARY_KEYS:
            if self.coordinator.data:
                return self.coordinator.data.get("currency", "USD")
            return "USD"
        return self.entity_description.native_unit_of_measurement

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data or {}
        attrs: dict[str, object] = {
            "last_success_ts": data.get("last_success_ts"),
            "api_is_available": self.coordinator.last_update_success,
        }
        if self.entity_description.key == "last_topup_amount":
            attrs["last_topup_ts"] = data.get("last_topup_ts")
        if self.entity_description.key == "tariff":
            attrs["next_tariff_state"] = data.get("next_tariff_state")
            attrs["next_tariff_change"] = data.get("next_tariff_change")
            attrs["pricing_grid_usd_per_m"] = data.get("pricing_grid")
        return attrs
