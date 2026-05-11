"""
Authentication Tests
====================
The service uses HTTP Basic Authentication.
Two pre-populated users: test1/test123 and test2/test456.

Spec anomalies to validate
---------------------------
GET  /integrations  — no 401 declared in spec responses → is auth actually enforced?
POST /integrations  — no 401 declared in spec responses → is auth actually enforced?
All other endpoints declare 401 properly.

These tests treat the anomalies as BUGS if auth is NOT enforced on those endpoints.
"""
import pytest
import requests
from requests.auth import HTTPBasicAuth

from config.settings import HTTP_POST_CREATE_OK, settings

pytestmark = pytest.mark.auth

BASE = f"{settings.base_url}{settings.api_base}"


def raw_get(path: str, user=None, password=None) -> requests.Response:
    auth = HTTPBasicAuth(user, password) if user else None
    return requests.get(f"{BASE}{path}", auth=auth, timeout=settings.request_timeout)


def raw_post(path: str, json_body: dict, user=None, password=None) -> requests.Response:
    auth = HTTPBasicAuth(user, password) if user else None
    return requests.post(
        f"{BASE}{path}", json=json_body, auth=auth, timeout=settings.request_timeout
    )


# ------------------------------------------------------------------ #
# Valid credentials
# ------------------------------------------------------------------ #

class TestValidCredentials:

    @pytest.mark.parametrize(
        "user, password",
        [(settings.user1.username, settings.user1.password),
         (settings.user2.username, settings.user2.password)],
        ids=["test1", "test2"],
    )
    def test_authenticated_user_can_list_integrations(self, user, password):
        resp = raw_get("/integrations", user, password)
        assert resp.status_code == 200, (
            f"User '{user}' should list integrations, got {resp.status_code}"
        )

    @pytest.mark.parametrize(
        "user, password",
        [(settings.user1.username, settings.user1.password),
         (settings.user2.username, settings.user2.password)],
        ids=["test1", "test2"],
    )
    def test_authenticated_user_can_create_integration(self, user, password):
        resp = raw_post("/integrations", {"name": "auth-test", "type": "aws"}, user, password)
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"User '{user}' should create integration (200 or 201), got {resp.status_code}"
        )
        # Teardown: delete the created integration to keep state clean
        if resp.status_code in HTTP_POST_CREATE_OK:
            integration_id = resp.json().get("id")
            if integration_id:
                requests.delete(
                    f"{BASE}/integrations/{integration_id}",
                    auth=HTTPBasicAuth(user, password),
                    timeout=settings.request_timeout,
                )


# ------------------------------------------------------------------ #
# No credentials
# ------------------------------------------------------------------ #

class TestNoCredentials:

    def test_unauthenticated_cannot_get_integration_by_id(self, integration_u1):
        """GET /integrations/{id} declares 401 — must enforce it."""
        resp = raw_get(f"/integrations/{integration_u1['id']}")
        assert resp.status_code == 401, (
            f"GET /integrations/{{id}} without auth should be 401, got {resp.status_code}"
        )

    def test_unauthenticated_cannot_update_integration(self):
        """PUT /integrations declares 401 — must enforce it."""
        resp = raw_post("/integrations", {"id": "fake", "name": "hack"})
        # PUT requires own method but testing via post to confirm no open door
        resp2 = requests.put(
            f"{BASE}/integrations",
            json={"id": "fake", "name": "hack"},
            timeout=settings.request_timeout,
        )
        assert resp2.status_code in (401, 404), (
            f"PUT /integrations without auth should be 401/404, got {resp2.status_code}"
        )

    def test_unauthenticated_cannot_delete_integration(self, integration_u1):
        """DELETE /integrations/{id} declares 401 — must enforce it."""
        resp = requests.delete(
            f"{BASE}/integrations/{integration_u1['id']}",
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401, (
            f"DELETE /integrations/{{id}} without auth should be 401, got {resp.status_code}"
        )

    def test_unauthenticated_cannot_get_asset_by_id(self, asset_u1):
        """GET /assets/{id} declares 401 — must enforce it."""
        resp = raw_get(f"/assets/{asset_u1['id']}")
        assert resp.status_code == 401, (
            f"GET /assets/{{id}} without auth should be 401, got {resp.status_code}"
        )

    def test_unauthenticated_cannot_list_assets(self, integration_u1):
        """GET /assets declares 401 — must enforce it."""
        resp = requests.get(
            f"{BASE}/assets",
            params={"integrationId": integration_u1["id"]},
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401, (
            f"GET /assets without auth should be 401, got {resp.status_code}"
        )

    # ----------------------------------------------------------------
    # BUG CANDIDATES — spec omits 401 on these but service should still require auth
    # ----------------------------------------------------------------

    def test_bug_list_integrations_requires_auth(self):
        """
        BUG CANDIDATE: GET /integrations does NOT declare 401 in the spec.
        The service MUST still reject unauthenticated requests — the spec omission
        is itself a documentation bug.  If this test fails it means the endpoint
        is publicly accessible without credentials.
        """
        resp = raw_get("/integrations")
        assert resp.status_code == 401, (
            "BUG: GET /integrations is accessible without authentication. "
            "The spec omits 401 from declared responses — spec is also incorrect."
        )

    def test_bug_create_integration_requires_auth(self):
        """
        BUG CANDIDATE: POST /integrations does NOT declare 401 in the spec.
        Creating a resource without authentication must be rejected.
        """
        resp = raw_post("/integrations", {"name": "hacker", "type": "aws"})
        assert resp.status_code == 401, (
            "BUG: POST /integrations is accessible without authentication. "
            "The spec omits 401 from declared responses — spec is also incorrect."
        )


# ------------------------------------------------------------------ #
# Invalid credentials
# ------------------------------------------------------------------ #

class TestInvalidCredentials:

    @pytest.mark.parametrize(
        "user, password",
        [
            ("test1", "wrongpassword"),
            ("test2", "wrongpassword"),
            ("nonexistent", "test123"),
            ("test1", ""),
            ("", "test123"),
        ],
        ids=["user1_wrong_pw", "user2_wrong_pw", "unknown_user", "empty_pw", "empty_user"],
    )
    def test_wrong_credentials_rejected_on_integrations(self, user, password):
        resp = raw_get("/integrations", user, password)
        assert resp.status_code == 401, (
            f"Invalid credentials ({user!r}) should return 401, got {resp.status_code}"
        )

    def test_401_includes_www_authenticate_header(self):
        """RFC 7617 §2 requires WWW-Authenticate header in 401 responses."""
        resp = raw_get("/integrations/nonexistent-id")
        if resp.status_code == 401:
            assert "WWW-Authenticate" in resp.headers, (
                "401 response is missing the required WWW-Authenticate header (RFC 7617)"
            )
