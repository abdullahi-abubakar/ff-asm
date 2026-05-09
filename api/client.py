"""
Authenticated HTTP client.  One instance = one tenant session.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from requests import Response

from config.settings import User, settings

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, user: Optional[User] = None) -> None:
        self._session = requests.Session()
        if user:
            self._session.auth = user.auth
        self._session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    # ------------------------------------------------------------------ #
    # HTTP verbs
    # ------------------------------------------------------------------ #

    def get(self, path: str, **kwargs) -> Response:
        return self._req("GET", path, **kwargs)

    def post(self, path: str, json: Optional[Dict] = None, **kwargs) -> Response:
        return self._req("POST", path, json=json, **kwargs)

    def put(self, path: str, json: Optional[Dict] = None, **kwargs) -> Response:
        return self._req("PUT", path, json=json, **kwargs)

    def patch(self, path: str, json: Optional[Dict] = None, **kwargs) -> Response:
        return self._req("PATCH", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> Response:
        return self._req("DELETE", path, **kwargs)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _req(self, method: str, path: str, **kwargs) -> Response:
        url = settings.url(path) if not path.startswith("http") else path
        kwargs.setdefault("timeout", settings.request_timeout)
        resp = self._session.request(method, url, **kwargs)
        logger.info(
            "[%s] %s → %s (%dms)",
            method,
            resp.request.url,
            resp.status_code,
            int(resp.elapsed.total_seconds() * 1000),
        )
        return resp

    def close(self) -> None:
        self._session.close()


# ------------------------------------------------------------------ #
# Factories
# ------------------------------------------------------------------ #

def as_user(user: User) -> APIClient:
    return APIClient(user)


def as_anon() -> APIClient:
    return APIClient(user=None)