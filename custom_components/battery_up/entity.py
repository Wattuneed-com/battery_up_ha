"""Shared entity base and the reading-validity rules.

The validity rules exist because the fleet lies in two specific ways,
both verified on live devices (2026-08-19):

  - some boxes publish soc=0 / soh=0 while visibly charging at 40+ A;
  - some frames carry v / itot / temperature all exactly 0 while soc is
    real — and a given box interleaves both kinds from one 15 s reading
    to the next.

An automation switching a 3 kW load must see "unknown", never a plausible
zero. Raw values stay visible as attributes on the SOC sensor.
"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MIN_PLAUSIBLE_PACK_VOLTAGE, STALE_AFTER_SECONDS
from .coordinator import BatteryUpCoordinator


def electricals_valid(reading: dict[str, Any]) -> bool:
    """Is this frame's electrical block (v, itot, temperature) a measurement?

    A 48 V pack reporting under MIN_PLAUSIBLE_PACK_VOLTAGE is a padding
    frame, and its itot/temperature zeros are padding too.
    """
    v = reading.get("v")
    return isinstance(v, (int, float)) and v > MIN_PLAUSIBLE_PACK_VOLTAGE


def soc_value(reading: dict[str, Any]) -> float | None:
    """SOC, or None when the device's claim is not credible.

    0 is indistinguishable from the known soc=0 defect (a truly empty
    Pylontech protects itself long before reporting 0), and values outside
    0..100 are noise. The raw claim stays visible as an attribute.
    """
    soc = reading.get("soc")
    if not isinstance(soc, (int, float)):
        return None
    if soc <= 0 or soc > 100:
        return None
    return float(soc)


def soh_value(reading: dict[str, Any]) -> float | None:
    """SOH, with the same skepticism as SOC: 0 means 'not reported'."""
    soh = reading.get("soh")
    if not isinstance(soh, (int, float)):
        return None
    if soh <= 0 or soh > 100:
        return None
    return float(soh)


class BatteryUpEntity(CoordinatorEntity[BatteryUpCoordinator]):
    """Base: one entity belongs to one physical box (one MAC)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BatteryUpCoordinator,
        mac: str,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self.entity_description = description
        self._attr_unique_id = "%s_%s" % (mac, description.key)

        device = coordinator.devices.get(mac) or {}
        protocol = device.get("protocol") or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=device.get("name") or mac,
            manufacturer=protocol.get("brand") or "Battery UP",
            model=protocol.get("product"),
            serial_number=mac,
        )

    @property
    def _payload(self) -> dict[str, Any] | None:
        """The API's /state answer for this box, or None."""
        if self.coordinator.data is None:
            return None
        entry = self.coordinator.data.get(self._mac)
        if entry is None:
            return None
        return entry.get("state")

    @property
    def _relays(self) -> dict[str, Any] | None:
        """The API's /relays answer, or None (not opted in, or feature dark)."""
        if self.coordinator.data is None:
            return None
        entry = self.coordinator.data.get(self._mac)
        if entry is None:
            return None
        return entry.get("relays")

    @property
    def _reading(self) -> dict[str, Any] | None:
        payload = self._payload
        if payload is None:
            return None
        reading = payload.get("reading")
        return reading if isinstance(reading, dict) else None

    @property
    def _fresh(self) -> bool:
        payload = self._payload
        if payload is None:
            return False
        age = payload.get("age_seconds")
        return isinstance(age, (int, float)) and age <= STALE_AFTER_SECONDS

    @property
    def available(self) -> bool:
        """Unavailable beats stale: nominal cadence is 15 s, and an
        automation acting on a 30-minute-old SOC is worse than one that
        pauses."""
        return super().available and self._reading is not None and self._fresh
