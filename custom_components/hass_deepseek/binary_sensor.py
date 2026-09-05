"""Capteur binaire : disponibilité de l'API DeepSeek."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DeepSeekCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute le capteur binaire pour cette entrée."""
    coordinator: DeepSeekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DeepSeekApiBinarySensor(coordinator, entry)])


class DeepSeekApiBinarySensor(
    CoordinatorEntity[DeepSeekCoordinator], BinarySensorEntity
):
    """État de connexion à l'API (on = API joignable et solde disponible)."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: DeepSeekCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_api"
        self.entity_description_key = "api_status"
        self._attr_translation_key = "api_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "DeepSeek",
            "model": "API Account",
        }

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.last_update_success)

    @property
    def available(self) -> bool:
        return True
