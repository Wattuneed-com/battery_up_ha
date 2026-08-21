"""Linking flow: account email + password, exchanged for one bup_ token.

What Home Assistant stores at the end is the token and the email (the
email doubles as the entry's unique id and the reauth identity). The
password exists only inside a single flow step.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    BatteryUpAuthError,
    BatteryUpClient,
    BatteryUpConnectionError,
    BatteryUpError,
)
from .const import (
    CONF_API_TOKEN,
    CONF_EMAIL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OPT_RELAY_CONTROL,
    OPT_SCAN_INTERVAL,
    UPDATE_INTERVAL_SECONDS,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class BatteryUpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Login -> mint a named integration token -> store only the token."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "BatteryUpOptionsFlow":
        return BatteryUpOptionsFlow()

    async def _mint_token(self, email: str, password: str) -> str:
        """The whole exchange. Raises the api.py taxonomy on failure."""
        client = BatteryUpClient(async_get_clientsession(self.hass))

        portal_token = await client.async_login(email, password)

        token = await client.async_create_integration_token(
            portal_token,
            "Home Assistant (%s)" % self.hass.config.location_name,
        )

        # Prove the minted token actually works before storing it.
        client.token = token
        await client.async_get_devices()

        return token

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()

            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            try:
                token = await self._mint_token(email, user_input[CONF_PASSWORD])
            except BatteryUpAuthError:
                errors["base"] = "invalid_auth"
            except BatteryUpConnectionError:
                errors["base"] = "cannot_connect"
            except BatteryUpError:
                LOGGER.exception("Unexpected error while linking Battery UP")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_API_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Token revoked or refused: ask for the password again."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        email = reauth_entry.data[CONF_EMAIL]

        if user_input is not None:
            try:
                token = await self._mint_token(email, user_input[CONF_PASSWORD])
            except BatteryUpAuthError:
                errors["base"] = "invalid_auth"
            except BatteryUpConnectionError:
                errors["base"] = "cannot_connect"
            except BatteryUpError:
                LOGGER.exception("Unexpected error while re-linking Battery UP")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_API_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": email},
            errors=errors,
        )


class BatteryUpOptionsFlow(OptionsFlow):
    """Post-setup settings: polling interval, and the relay-control opt-in
    (phase 2 — the switches stay unavailable until the server-side command
    feature is live and the box is in MANUAL mode)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPT_SCAN_INTERVAL,
                        default=options.get(OPT_SCAN_INTERVAL, UPDATE_INTERVAL_SECONDS),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Required(
                        OPT_RELAY_CONTROL,
                        default=options.get(OPT_RELAY_CONTROL, False),
                    ): bool,
                }
            ),
        )
