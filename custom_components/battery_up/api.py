"""The one network module: every byte to or from the Battery UP API goes
through this file. Auth, timeouts, and the error taxonomy live here so the
rest of the integration can reason in exceptions, not status codes."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import DEFAULT_BASE_URL

TIMEOUT = aiohttp.ClientTimeout(total=20)


class BatteryUpError(Exception):
    """Base error for the Battery UP API."""


class BatteryUpConnectionError(BatteryUpError):
    """Network-level failure: DNS, TLS, timeout, connection refused."""


class BatteryUpAuthError(BatteryUpError):
    """The credential was refused (401, or a failed login)."""


class BatteryUpForbiddenError(BatteryUpError):
    """Authenticated, but not entitled to this device (403)."""


class BatteryUpClient:
    """Minimal async client for the /api/ha/* surface.

    Holds a bup_ integration token for normal operation. The two calls of
    the linking flow (login, token minting) take their credential as an
    argument instead, because at that moment no bup_ token exists yet.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self.token = token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """One HTTP exchange. Returns (status, decoded-json-or-None).

        Network problems raise BatteryUpConnectionError; HTTP statuses are
        returned, not raised — what a status means depends on the endpoint,
        so the caller decides.
        """
        headers = {"Accept": "application/json"}
        credential = token if token is not None else self.token
        if credential:
            headers["Authorization"] = "Bearer " + credential

        try:
            async with self._session.request(
                method,
                self._base_url + path,
                headers=headers,
                json=json_body,
                timeout=TIMEOUT,
            ) as resp:
                status = resp.status
                try:
                    data = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    data = None
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise BatteryUpConnectionError(str(err)) from err

        return status, data

    async def async_login(self, email: str, password: str) -> str:
        """Exchange account credentials for a short-lived portal token.

        Used exactly once per (re)link; the password is never stored.

        The API's login endpoint answers 500 — not 401 — on wrong
        credentials (it array-accesses the upstream error response), so any
        completed HTTP exchange that does not carry an access_token is
        treated as bad credentials. Only network-level failures surface as
        cannot-connect.
        """
        status, data = await self._request(
            "POST", "/api/login", json_body={"email": email, "password": password}
        )

        if status == 200 and isinstance(data, dict) and data.get("access_token"):
            return str(data["access_token"])

        raise BatteryUpAuthError("login refused (status %s)" % status)

    async def async_create_integration_token(
        self, portal_token: str, name: str
    ) -> str:
        """Mint the durable bup_ token this integration will actually store.

        Requires the portal token from async_login — a bup_ token cannot
        mint successors of itself, by server-side design.
        """
        status, data = await self._request(
            "POST",
            "/api/integration-tokens",
            token=portal_token,
            json_body={"name": name[:64]},
        )

        if status in (200, 201) and isinstance(data, dict) and data.get("token"):
            return str(data["token"])

        if status == 401:
            raise BatteryUpAuthError("portal token refused while minting")

        raise BatteryUpError("token minting failed (status %s)" % status)

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """The account's registered devices (all protocols, unfiltered)."""
        status, data = await self._request("GET", "/api/ha/devices")

        if status == 200 and isinstance(data, dict) and isinstance(data.get("devices"), list):
            return data["devices"]

        if status == 401:
            raise BatteryUpAuthError("token refused")

        raise BatteryUpError("device list failed (status %s)" % status)

    async def async_get_state(self, mac: str) -> dict[str, Any] | None:
        """Latest reading for one device, or None when it has no data.

        404 is a normal answer (registered box that has not published within
        the raw collection's retention), not an error.
        """
        status, data = await self._request("GET", "/api/ha/devices/%s/state" % mac)

        if status == 200 and isinstance(data, dict):
            return data

        if status == 404:
            return None

        if status == 401:
            raise BatteryUpAuthError("token refused")

        if status == 403:
            raise BatteryUpForbiddenError("not entitled to %s" % mac)

        raise BatteryUpError("state read failed (status %s)" % status)
