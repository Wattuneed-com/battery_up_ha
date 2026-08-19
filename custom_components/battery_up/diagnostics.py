"""Support dump: everything needed to debug a report, nothing secret."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BatteryUpConfigEntry
from .const import CONF_API_TOKEN

TO_REDACT = {CONF_API_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BatteryUpConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": coordinator.devices,
        "data": coordinator.data,
        "last_update_success": coordinator.last_update_success,
    }
