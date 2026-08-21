"""Battery UP: cloud-polling integration for the Wattuneed Battery UP box.

Read-only in this version. Relay control (phase 2 of the project plan) is
deliberately absent until the command path has an acknowledgement story.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BatteryUpClient
from .const import CONF_API_TOKEN
from .coordinator import BatteryUpCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

BatteryUpConfigEntry = ConfigEntry[BatteryUpCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BatteryUpConfigEntry) -> bool:
    """The entry holds one thing of value: the bup_ integration token.

    The account password was used once during the config flow and never
    stored; on a 401 the coordinator raises ConfigEntryAuthFailed, which
    sends the user through the reauth flow to mint a fresh token.
    """
    client = BatteryUpClient(
        async_get_clientsession(hass), token=entry.data[CONF_API_TOKEN]
    )

    coordinator = BatteryUpCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Options (interval, relay opt-in) apply via a clean reload.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: BatteryUpConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BatteryUpConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
