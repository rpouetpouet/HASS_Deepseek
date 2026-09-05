"""Capteurs DeepSeek : soldes + dépenses dérivées."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
)


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
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None:
            return None
        return data.get(self.entity_description.key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("currency", "USD")
        return "USD"

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data or {}
        return {
            "last_success_ts": data.get("last_success_ts"),
            "api_is_available": self.coordinator.last_update_success,
        }
