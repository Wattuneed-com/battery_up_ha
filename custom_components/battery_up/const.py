"""Constants for the Battery UP integration."""

from __future__ import annotations

import logging

DOMAIN = "battery_up"

LOGGER = logging.getLogger(__package__)

# Despite the name, this is production. See the API repo's docs.
DEFAULT_BASE_URL = "https://devapi.wattuneed.com"

CONF_EMAIL = "email"
CONF_API_TOKEN = "api_token"

# Devices publish every 15 s; polling faster reads the same value twice.
# bup_ tokens are validated locally by the API (no portal round-trip), so
# 30 s costs one local lookup + one Mongo read per device.
UPDATE_INTERVAL_SECONDS = 30

# Nominal cadence is 15 s. A reading older than this means the box is not
# talking, and an automation acting on old battery data is worse than one
# that pauses — entities go unavailable instead of lying.
STALE_AFTER_SECONDS = 120

# A 48 V pack that reports less than this is not a measurement, it is a
# padding frame. Live boxes interleave frames where v/itot/temperature are
# all exactly 0 with real ones (verified on the fleet 2026-08-19).
MIN_PLAUSIBLE_PACK_VOLTAGE = 10.0

# |current| above which the pack is clearly active, used to spot the
# "soc=0 while charging at 40 A" defect some devices exhibit.
ACTIVE_CURRENT_AMPS = 2.0
