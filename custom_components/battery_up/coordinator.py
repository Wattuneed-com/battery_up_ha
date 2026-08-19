"""One coordinator per config entry: polls every battery's latest reading."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    BatteryUpAuthError,
    BatteryUpClient,
    BatteryUpConnectionError,
    BatteryUpError,
    BatteryUpForbiddenError,
)
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_SECONDS


class BatteryUpCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /state for each battery device on the account.

    coordinator.data maps mac -> the API's state payload
    ({"reading": ..., "age_seconds": ...}) or None when the device has no
    data or was removed from the account.
    """

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: BatteryUpClient
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        # mac -> device dict from /api/ha/devices, batteries only.
        self.devices: dict[str, dict[str, Any]] = {}
        self._forbidden_logged: set[str] = set()

    async def _async_setup(self) -> None:
        """Fetch the device list once, when the entry loads.

        The list is intentionally not re-fetched on every poll — a new box
        on the account appears after a reload of the integration, which is
        also when its entities would be created anyway.
        """
        try:
            devices = await self.client.async_get_devices()
        except BatteryUpAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BatteryUpConnectionError as err:
            raise UpdateFailed("cannot reach the Battery UP API: %s" % err) from err

        self.devices = {
            d["mac"]: d for d in devices if self._is_battery(d)
        }

        if not self.devices:
            LOGGER.warning(
                "No battery device on this Battery UP account (found %d other devices)",
                len(devices),
            )

    @staticmethod
    def _is_battery(device: dict[str, Any]) -> bool:
        """Only the Pylontech battery chain is live; trackers (ST-) and the
        dormant meter protocols have no data behind /state."""
        mac = device.get("mac") or ""
        protocol = device.get("protocol") or {}
        return mac.startswith("BU-") and protocol.get("brand") == "PylonTech"

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}

        for mac in self.devices:
            try:
                data[mac] = await self.client.async_get_state(mac)
            except BatteryUpAuthError as err:
                # Token revoked or account gone: every device is affected,
                # stop and ask the user to re-link.
                raise ConfigEntryAuthFailed from err
            except BatteryUpForbiddenError:
                # This one device left the account (sold, moved by support).
                # Its entities go unavailable; the others keep working.
                if mac not in self._forbidden_logged:
                    self._forbidden_logged.add(mac)
                    LOGGER.warning(
                        "Battery UP refuses access to %s — it is no longer on this account",
                        mac,
                    )
                data[mac] = None
            except (BatteryUpConnectionError, BatteryUpError) as err:
                raise UpdateFailed(str(err)) from err

        return data
