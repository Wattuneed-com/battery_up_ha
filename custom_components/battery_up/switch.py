"""The box's two relays, as Home Assistant switches (phase 2).

A toggle here is a REQUEST, never a fact: the position shown is what the
device last confirmed (echo/probe through the reply pipeline); while a
command is in flight the entity reports assumed state and exposes the
server's status as attributes. Advisories from the server (battery low,
data stale) are surfaced as attributes too — informative, never blocking,
per the product rule.

Entities exist only when the user opted into relay control (Configure) and
become available only when the server-side feature is enabled AND the box
is in MANUAL mode and not deaf. Everything else is honest unavailability.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BatteryUpConfigEntry
from .const import LOGGER, OPT_RELAY_CONTROL
from .entity import BatteryUpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryUpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(OPT_RELAY_CONTROL, False):
        return

    coordinator = entry.runtime_data
    async_add_entities(
        BatteryUpRelaySwitch(coordinator, mac, relay)
        for mac in coordinator.devices
        for relay in (1, 2)
    )


class _RelayDescription:
    """Just enough description for the shared base entity."""

    def __init__(self, relay: int) -> None:
        self.key = "relay%d" % relay
        self.name = "Relay %d" % relay


class BatteryUpRelaySwitch(BatteryUpEntity, SwitchEntity):
    _attr_icon = "mdi:electric-switch"

    def __init__(self, coordinator, mac: str, relay: int) -> None:
        super().__init__(coordinator, mac, _RelayDescription(relay))
        self._relay = relay

    @property
    def available(self) -> bool:
        """Available only when a command could actually mean something:
        feature enabled server-side, box known to be in MANUAL, not deaf,
        and telemetry fresh (the base check)."""
        relays = self._relays

        return (
            super().available
            and relays is not None
            and bool(relays.get("enabled"))
            and relays.get("mode") == "manu"
            and not relays.get("deaf")
        )

    @property
    def is_on(self) -> bool | None:
        relays = self._relays
        if relays is None:
            return None

        applied = relays.get("applied") or {}
        value = applied.get("relay%d" % self._relay)

        return None if value is None else bool(value)

    @property
    def assumed_state(self) -> bool:
        """While desired differs from confirmed, the position is a guess."""
        relays = self._relays
        if relays is None:
            return False

        desired = (relays.get("desired") or {}).get("relay%d" % self._relay)
        applied = (relays.get("applied") or {}).get("relay%d" % self._relay)

        return desired is not None and desired != applied

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        relays = self._relays
        if relays is None:
            return None

        return {
            "status": relays.get("status"),
            "status_detail": relays.get("status_detail"),
            "mode": relays.get("mode"),
            "deaf": relays.get("deaf"),
            "advisories": relays.get("advisories", []),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._request(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._request(0)

    async def _request(self, value: int) -> None:
        result = await self.coordinator.client.async_set_relays(
            self._mac,
            relay1=value if self._relay == 1 else None,
            relay2=value if self._relay == 2 else None,
        )

        advisories = result.get("advisories") or []
        if advisories:
            # Informative, never blocking (product rule): the command went
            # through; the log is where a person can later see the context.
            LOGGER.warning(
                "Battery UP accepted relay %d=%s on %s with advisories: %s",
                self._relay, value, self._mac, ", ".join(advisories),
            )

        await self.coordinator.async_request_refresh()
