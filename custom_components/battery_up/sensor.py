"""Numeric entities for one Battery UP box."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BatteryUpConfigEntry
from .entity import BatteryUpEntity, electricals_valid, soc_value, soh_value


def _power_value(reading: dict[str, Any]) -> float | None:
    """Pack power derived from v x itot. Positive = charging, negative =
    discharging — the sign convention of itot, kept as-is."""
    if not electricals_valid(reading):
        return None
    itot = reading.get("itot")
    if not isinstance(itot, (int, float)):
        return None
    return round(reading["v"] * itot, 1)


def _electrical(key: str) -> Callable[[dict[str, Any]], float | None]:
    def value(reading: dict[str, Any]) -> float | None:
        if not electricals_valid(reading):
            return None
        raw = reading.get(key)
        return float(raw) if isinstance(raw, (int, float)) else None

    return value


def _raw_number(key: str) -> Callable[[dict[str, Any]], float | None]:
    def value(reading: dict[str, Any]) -> float | None:
        raw = reading.get(key)
        return float(raw) if isinstance(raw, (int, float)) else None

    return value


@dataclass(frozen=True, kw_only=True)
class BatteryUpSensorDescription(SensorEntityDescription):
    """Adds the value extraction to the standard description."""

    value_fn: Callable[[dict[str, Any]], float | None]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[BatteryUpSensorDescription, ...] = (
    BatteryUpSensorDescription(
        key="soc",
        name="State of charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=soc_value,
        # The raw claim stays inspectable even while the sensor says unknown.
        attributes_fn=lambda reading: {"raw_soc": reading.get("soc")},
    ),
    BatteryUpSensorDescription(
        key="battery_power",
        name="Battery power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_power_value,
    ),
    BatteryUpSensorDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_electrical("v"),
    ),
    BatteryUpSensorDescription(
        key="current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_electrical("itot"),
    ),
    BatteryUpSensorDescription(
        key="cell_temperature",
        name="Cell temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_electrical("avg_cell_t"),
    ),
    BatteryUpSensorDescription(
        key="soh",
        name="State of health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=soh_value,
    ),
    BatteryUpSensorDescription(
        key="charge_voltage_limit",
        name="Charge voltage limit",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_raw_number("batt_chg_v"),
    ),
    BatteryUpSensorDescription(
        key="charge_current_limit",
        name="Charge current limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_raw_number("chg_i_limit"),
    ),
    BatteryUpSensorDescription(
        key="discharge_current_limit",
        name="Discharge current limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_raw_number("dischg_i_limit"),
    ),
    BatteryUpSensorDescription(
        key="module_count",
        name="Battery modules",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_raw_number("mod_cnt"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryUpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BatteryUpSensor(coordinator, mac, description)
        for mac in coordinator.devices
        for description in SENSORS
    )


class BatteryUpSensor(BatteryUpEntity, SensorEntity):
    entity_description: BatteryUpSensorDescription

    @property
    def native_value(self) -> float | None:
        reading = self._reading
        if reading is None:
            return None
        return self.entity_description.value_fn(reading)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        reading = self._reading
        if reading is None:
            return None
        return self.entity_description.attributes_fn(reading)
