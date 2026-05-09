"""
Shared pytest fixtures.

Scope strategy
--------------
session  – OpenAPI spec (fetched once)
function – clients, integrations, assets (fresh per test, cleaned up after)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Generator, Tuple

import pytest
import requests

from api.client import APIClient, as_anon, as_user
from api.helpers import AssetClient, IntegrationClient
from config.settings import settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# OpenAPI spec
# ------------------------------------------------------------------ #

@pytest.fixture(scope="session")
def openapi_spec() -> Dict[str, Any]:
    try:
        resp = requests.get(settings.swagger_url, timeout=settings.request_timeout)
        resp.raise_for_status()
        spec = resp.json()
        logger.info("Spec loaded — title: %s", spec.get("info", {}).get("title"))
        return spec
    except requests.exceptions.ConnectionError as exc:
        pytest.fail(
            f"Cannot reach {settings.base_url}.\n"
            f"Run the service first: docker run -d -p 8080:8080 infralightio/test-integration-api\n"
            f"Error: {exc}"
        )


# ------------------------------------------------------------------ #
# Authenticated clients
# ------------------------------------------------------------------ #

@pytest.fixture
def client1() -> Generator[APIClient, None, None]:
    c = as_user(settings.user1)
    yield c
    c.close()


@pytest.fixture
def client2() -> Generator[APIClient, None, None]:
    c = as_user(settings.user2)
    yield c
    c.close()


@pytest.fixture
def anon() -> Generator[APIClient, None, None]:
    c = as_anon()
    yield c
    c.close()


# ------------------------------------------------------------------ #
# Domain-specific clients
# ------------------------------------------------------------------ #

@pytest.fixture
def integrations1(client1: APIClient) -> IntegrationClient:
    return IntegrationClient(client1)


@pytest.fixture
def integrations2(client2: APIClient) -> IntegrationClient:
    return IntegrationClient(client2)


@pytest.fixture
def assets1(client1: APIClient) -> AssetClient:
    return AssetClient(client1)


@pytest.fixture
def assets2(client2: APIClient) -> AssetClient:
    return AssetClient(client2)


# ------------------------------------------------------------------ #
# Ready-made resources (created and torn down automatically)
# ------------------------------------------------------------------ #

@pytest.fixture
def integration_u1(integrations1: IntegrationClient) -> Generator[Dict, None, None]:
    """A live integration owned by user1. Deleted after the test."""
    resp = integrations1.create()
    assert resp.status_code == 200, f"Setup: could not create integration ({resp.status_code}): {resp.text}"
    resource = resp.json()
    yield resource
    integrations1.delete(resource["id"])


@pytest.fixture
def integration_u2(integrations2: IntegrationClient) -> Generator[Dict, None, None]:
    """A live integration owned by user2. Deleted after the test."""
    resp = integrations2.create()
    assert resp.status_code == 200, f"Setup: could not create integration ({resp.status_code}): {resp.text}"
    resource = resp.json()
    yield resource
    integrations2.delete(resource["id"])


@pytest.fixture
def asset_u1(
    assets1: AssetClient, integration_u1: Dict
) -> Generator[Dict, None, None]:
    """A live asset owned by user1 (under user1's integration). Deleted after the test."""
    resp = assets1.create(integration_id=integration_u1["id"])
    assert resp.status_code == 200, f"Setup: could not create asset ({resp.status_code}): {resp.text}"
    resource = resp.json()
    yield resource
    assets1.delete(resource["id"])


@pytest.fixture
def asset_u2(
    assets2: AssetClient, integration_u2: Dict
) -> Generator[Dict, None, None]:
    """A live asset owned by user2 (under user2's integration). Deleted after the test."""
    resp = assets2.create(integration_id=integration_u2["id"])
    assert resp.status_code == 200, f"Setup: could not create asset ({resp.status_code}): {resp.text}"
    resource = resp.json()
    yield resource
    assets2.delete(resource["id"])
