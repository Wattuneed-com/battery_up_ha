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
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BatteryUpConfigEntry
from .entity import BatteryUpEntity, BatteryUpInverterEntity, electricals_valid, soc_value, soh_value


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
        suggested_display_precision=0,
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
        suggested_display_precision=0,
        value_fn=_power_value,
    ),
    BatteryUpSensorDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_electrical("v"),
    ),
    BatteryUpSensorDescription(
        key="current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_electrical("itot"),
    ),
    BatteryUpSensorDescription(
        key="cell_temperature",
        name="Cell temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_electrical("avg_cell_t"),
    ),
    BatteryUpSensorDescription(
        key="soh",
        name="State of health",
        icon="mdi:battery-heart-variant",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
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
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=_raw_number("mod_cnt"),
    ),
)


@dataclass(frozen=True, kw_only=True)
class InverterSensorDescription(SensorEntityDescription):
    """One value of the inverter payload: source "reading" (live) or "energy"
    (counters). Created only when the inverter gives it at setup, unless
    always is set: a single-phase Deye has no L2/L3, a Deye no battery totals."""

    source: str = "reading"
    field: str
    always: bool = False


def _power(key: str, name: str, field: str, *, enabled: bool = True, always: bool = False, icon: str | None = None) -> InverterSensorDescription:
    return InverterSensorDescription(
        key=key, name=name, field=field, always=always, icon=icon,
        device_class=SensorDeviceClass.POWER, native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
        entity_registry_enabled_default=enabled,
    )


def _energy(key: str, name: str, field: str, *, enabled: bool = True) -> InverterSensorDescription:
    # Counters only grow; the day ones fall back to 0 at the inverter's midnight,
    # which TOTAL_INCREASING reads as a new cycle: both feed the Energy dashboard.
    return InverterSensorDescription(
        key=key, name=name, field=field, source="energy",
        device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
    )


def _voltage(key: str, name: str, field: str, *, enabled: bool = True) -> InverterSensorDescription:
    return InverterSensorDescription(
        key=key, name=name, field=field,
        device_class=SensorDeviceClass.VOLTAGE, native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
    )


INVERTER_SENSORS: tuple[InverterSensorDescription, ...] = (
    InverterSensorDescription(
        key="battery_soc", name="Battery state of charge", field="soc", always=True,
        device_class=SensorDeviceClass.BATTERY, native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    # Signs as Home Assistant's: battery positive while discharging, grid positive while importing.
    _power("battery_power", "Battery power", "battery_w", always=True),
    _voltage("battery_voltage", "Battery voltage", "battery_v"),
    InverterSensorDescription(
        key="battery_current", name="Battery current", field="battery_a",
        device_class=SensorDeviceClass.CURRENT, native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    InverterSensorDescription(
        key="battery_temperature", name="Battery temperature", field="battery_temp",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
    ),
    _power("solar_power", "Solar power", "pv_w", always=True, icon="mdi:solar-power"),
    _power("solar_power_1", "Solar power string 1", "pv1_w", enabled=False, icon="mdi:solar-power"),
    _power("solar_power_2", "Solar power string 2", "pv2_w", enabled=False, icon="mdi:solar-power"),
    _power("solar_power_3", "Solar power string 3", "pv3_w", enabled=False, icon="mdi:solar-power"),
    _power("solar_power_4", "Solar power string 4", "pv4_w", enabled=False, icon="mdi:solar-power"),
    _voltage("solar_voltage_1", "Solar voltage string 1", "pv1_v", enabled=False),
    _voltage("solar_voltage_2", "Solar voltage string 2", "pv2_v", enabled=False),
    _power("grid_power", "Grid power", "grid_w", always=True, icon="mdi:transmission-tower"),
    _power("grid_power_l1", "Grid power L1", "grid_l1_w", enabled=False, icon="mdi:transmission-tower"),
    _power("grid_power_l2", "Grid power L2", "grid_l2_w", enabled=False, icon="mdi:transmission-tower"),
    _power("grid_power_l3", "Grid power L3", "grid_l3_w", enabled=False, icon="mdi:transmission-tower"),
    _voltage("grid_voltage_l1", "Grid voltage L1", "grid_l1_v"),
    _voltage("grid_voltage_l2", "Grid voltage L2", "grid_l2_v"),
    _voltage("grid_voltage_l3", "Grid voltage L3", "grid_l3_v"),
    InverterSensorDescription(
        key="grid_frequency", name="Grid frequency", field="grid_hz",
        device_class=SensorDeviceClass.FREQUENCY, native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
    ),
    _power("load_power", "House consumption", "load_w", always=True, icon="mdi:home-lightning-bolt"),
    _power("load_power_l1", "House consumption L1", "load_l1_w", enabled=False, icon="mdi:home-lightning-bolt"),
    _power("load_power_l2", "House consumption L2", "load_l2_w", enabled=False, icon="mdi:home-lightning-bolt"),
    _power("load_power_l3", "House consumption L3", "load_l3_w", enabled=False, icon="mdi:home-lightning-bolt"),
    _power("backup_power", "Backup output power", "ups_w", icon="mdi:power-plug-battery"),
    _power("inverter_power", "Inverter power", "inverter_w", enabled=False),
    _power("generator_power", "Generator power", "gen_w", enabled=False),
    InverterSensorDescription(
        key="inverter_temperature", name="Inverter temperature", field="heatsink_temp",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    InverterSensorDescription(
        key="inverter_state", name="Inverter state", field="state", icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _energy("solar_energy_today", "Solar energy today", "day_pv_kwh"),
    _energy("load_energy_today", "House consumption today", "day_load_kwh"),
    _energy("grid_import_today", "Grid import today", "day_grid_import_kwh"),
    _energy("grid_export_today", "Grid export today", "day_grid_export_kwh"),
    _energy("battery_charge_today", "Battery charge today", "day_battery_charge_kwh"),
    _energy("battery_discharge_today", "Battery discharge today", "day_battery_discharge_kwh"),
    _energy("generator_energy_today", "Generator energy today", "day_gen_kwh", enabled=False),
    _energy("solar_energy_total", "Solar energy total", "total_pv_kwh"),
    _energy("load_energy_total", "House consumption total", "total_load_kwh"),
    _energy("grid_import_total", "Grid import total", "total_grid_import_kwh"),
    _energy("grid_export_total", "Grid export total", "total_grid_export_kwh"),
    _energy("battery_charge_total", "Battery charge total", "total_battery_charge_kwh"),
    _energy("battery_discharge_total", "Battery discharge total", "total_battery_discharge_kwh"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryUpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        BatteryUpSensor(coordinator, mac, description)
        for mac in coordinator.devices
        for description in SENSORS
    ]
    for mac in coordinator.inverters:
        first = ((coordinator.data or {}).get(mac) or {}).get("inverter") or {}
        for description in INVERTER_SENSORS:
            given = (first.get(description.source) or {}).get(description.field) is not None
            if description.always or given:
                entities.append(BatteryUpInverterSensor(coordinator, mac, description))
    async_add_entities(entities)


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


class BatteryUpInverterSensor(BatteryUpInverterEntity, SensorEntity):
    entity_description: InverterSensorDescription

    @property
    def available(self) -> bool:
        age_key = "energy_age_seconds" if self.entity_description.source == "energy" else "age_seconds"
        return super(BatteryUpInverterEntity, self).available and self._fresh_for(age_key)

    @property
    def native_value(self) -> float | str | None:
        payload = self._inverter
        if payload is None:
            return None
        value = (payload.get(self.entity_description.source) or {}).get(self.entity_description.field)
        if self.entity_description.field == "state":
            return value if isinstance(value, str) else None
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
