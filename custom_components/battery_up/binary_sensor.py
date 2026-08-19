"""Flag entities: BMS permissions, protections, alarms.

The CAN protocol carries bit flags only — there is no message text behind
them, the flag name IS the diagnosis. The two aggregate entities are the
ones meant for dashboards; the fourteen individual flags exist for people
who want them and ship disabled.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BatteryUpConfigEntry
from .entity import BatteryUpEntity

# Every problem-shaped flag the reading carries.
PROBLEM_FLAGS: tuple[str, ...] = (
    "prot_cell_ot",
    "prot_cell_ov",
    "prot_cell_ut",
    "prot_cell_uv",
    "prot_chg_oi",
    "prot_disc_oi",
    "prot_sys_err",
    "alar_cell_ht",
    "alar_cell_hv",
    "alar_cell_lt",
    "alar_cell_lv",
    "alar_chg_hi",
    "alar_comm_fail",
    "alar_dischg_hi",
)

PROBLEM_FLAG_NAMES: dict[str, str] = {
    "prot_cell_ot": "Protection cell overtemperature",
    "prot_cell_ov": "Protection cell overvoltage",
    "prot_cell_ut": "Protection cell undertemperature",
    "prot_cell_uv": "Protection cell undervoltage",
    "prot_chg_oi": "Protection charge overcurrent",
    "prot_disc_oi": "Protection discharge overcurrent",
    "prot_sys_err": "Protection system error",
    "alar_cell_ht": "Alarm cell high temperature",
    "alar_cell_hv": "Alarm cell high voltage",
    "alar_cell_lt": "Alarm cell low temperature",
    "alar_cell_lv": "Alarm cell low voltage",
    "alar_chg_hi": "Alarm charge current high",
    "alar_comm_fail": "Alarm communication failure",
    "alar_dischg_hi": "Alarm discharge current high",
}


def _flag(key: str, invert: bool = False) -> Callable[[dict[str, Any]], bool | None]:
    def value(reading: dict[str, Any]) -> bool | None:
        raw = reading.get(key)
        if raw is None:
            return None
        return (not raw) if invert else bool(raw)

    return value


def _any_problem(reading: dict[str, Any]) -> bool | None:
    """Any protection or alarm bit set. None only when the reading carries
    no flags at all (never observed, but the pipeline whitelist decides)."""
    seen_one = False
    for key in PROBLEM_FLAGS:
        raw = reading.get(key)
        if raw is None:
            continue
        seen_one = True
        if raw:
            return True
    return False if seen_one else None


@dataclass(frozen=True, kw_only=True)
class BatteryUpBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


DESCRIPTIONS: tuple[BatteryUpBinarySensorDescription, ...] = (
    BatteryUpBinarySensorDescription(
        key="problem",
        name="Problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_any_problem,
    ),
    BatteryUpBinarySensorDescription(
        key="bms_communication",
        name="BMS communication",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_flag("alar_comm_fail", invert=True),
    ),
    BatteryUpBinarySensorDescription(
        key="charge_allowed",
        name="Charge allowed",
        value_fn=_flag("req_charge_enable"),
    ),
    BatteryUpBinarySensorDescription(
        key="discharge_allowed",
        name="Discharge allowed",
        value_fn=_flag("req_dischg_enable"),
    ),
    BatteryUpBinarySensorDescription(
        key="force_charge_1",
        name="Force charge request 1",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_flag("req_forcechg_1"),
    ),
    BatteryUpBinarySensorDescription(
        key="force_charge_2",
        name="Force charge request 2",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_flag("req_forcechg_2"),
    ),
) + tuple(
    BatteryUpBinarySensorDescription(
        key=flag,
        name=PROBLEM_FLAG_NAMES[flag],
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_flag(flag),
    )
    for flag in PROBLEM_FLAGS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryUpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BatteryUpBinarySensor(coordinator, mac, description)
        for mac in coordinator.devices
        for description in DESCRIPTIONS
    )


class BatteryUpBinarySensor(BatteryUpEntity, BinarySensorEntity):
    entity_description: BatteryUpBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        reading = self._reading
        if reading is None:
            return None
        return self.entity_description.value_fn(reading)
