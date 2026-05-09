"""
Domain-specific helpers that mirror the actual API surface exactly.

Integrations
  POST   /integrations          body: {name, type}
  GET    /integrations          query: page, limit
  GET    /integrations/{id}
  PUT    /integrations          body: {id, name}   ← id in body, not path
  DELETE /integrations/{id}

Assets
  POST   /assets                body: {name, description, integration_id}
  GET    /assets                query: integrationId (required!), page, limit
  GET    /assets/{id}
  PATCH  /assets                body: {id, name, description}  ← id in body, not path
  DELETE /assets/{id}
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from requests import Response

from api.client import APIClient


# ------------------------------------------------------------------ #
# Integration helpers
# ------------------------------------------------------------------ #

class IntegrationClient:
    def __init__(self, client: APIClient) -> None:
        self._c = client

    def create(self, name: str = None, type_: str = "aws") -> Response:
        name = name or f"integration-{uuid.uuid4().hex[:8]}"
        return self._c.post("/integrations", json={"name": name, "type": type_})

    def list(self, page: int = None, limit: int = None) -> Response:
        params = {}
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
        return self._c.get("/integrations", params=params)

    def get(self, integration_id: str) -> Response:
        return self._c.get(f"/integrations/{integration_id}")

    def update(self, integration_id: str, name: str) -> Response:
        return self._c.put("/integrations", json={"id": integration_id, "name": name})

    def delete(self, integration_id: str) -> Response:
        return self._c.delete(f"/integrations/{integration_id}")


# ------------------------------------------------------------------ #
# Asset helpers
# ------------------------------------------------------------------ #

class AssetClient:
    def __init__(self, client: APIClient) -> None:
        self._c = client

    def create(
        self,
        integration_id: str,
        name: str = None,
        description: str = "test asset",
    ) -> Response:
        name = name or f"asset-{uuid.uuid4().hex[:8]}"
        return self._c.post(
            "/assets",
            json={"name": name, "description": description, "integration_id": integration_id},
        )

    def list(self, integration_id: str, page: int = None, limit: int = None) -> Response:
        params = {"integrationId": integration_id}
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
        return self._c.get("/assets", params=params)

    def get(self, asset_id: str) -> Response:
        return self._c.get(f"/assets/{asset_id}")

    def update(self, asset_id: str, name: str = None, description: str = None) -> Response:
        payload: Dict[str, Any] = {"id": asset_id}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        return self._c.patch("/assets", json=payload)

    def delete(self, asset_id: str) -> Response:
        return self._c.delete(f"/assets/{asset_id}")