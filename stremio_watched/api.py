"""Stremio account API (api.strem.io). The only place that talks to it."""

from __future__ import annotations

from typing import Any

import requests

from .config import API_URL, HTTP_TIMEOUT, USER_AGENT


class StremioAPIError(Exception):
    def __init__(self, code: Any, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def is_auth_error(self) -> bool:
        # Observed: code 1 / "Session does not exist" for an invalid or expired authKey.
        return self.code == 1 or "session" in self.message.lower()


class StremioClient:
    def __init__(
        self,
        base_url: str = API_URL,
        timeout: int = HTTP_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", USER_AGENT)

    def _post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        try:
            response = self._session.post(f"{self._base_url}/{endpoint}", json=payload, timeout=self._timeout)
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            raise StremioAPIError(None, f"network error talking to Stremio ({exc})") from exc
        except ValueError as exc:
            raise StremioAPIError(None, "Stremio returned a non-JSON response") from exc

        error = body.get("error")
        if error:
            if isinstance(error, dict):
                raise StremioAPIError(error.get("code"), str(error.get("message", error)))
            raise StremioAPIError(None, str(error))
        return body.get("result")

    def login(self, email: str, password: str) -> str:
        """Return the long-lived authKey for these credentials."""
        result = self._post("login", {"type": "Login", "email": email, "password": password, "facebook": False})
        auth_key = (result or {}).get("authKey")
        if not auth_key:
            raise StremioAPIError(None, "login succeeded but no authKey was returned")
        return auth_key

    def fetch_library(self, auth_key: str) -> list[dict[str, Any]]:
        """Every `libraryItem` of the account (all types, including removed/temp ones)."""
        result = self._post(
            "datastoreGet",
            {"authKey": auth_key, "collection": "libraryItem", "ids": [], "all": True},
        )
        return list(result or [])
