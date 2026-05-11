"""
Negative / Edge Case Tests
==========================
The API description says it has intentional bugs.
These tests are specifically designed to find them.

Scenarios covered
-----------------
- Missing required fields
- Malformed JSON
- Invalid / malicious ID values
- Wrong HTTP methods
- Invalid pagination parameters
- Asset list without required integrationId
- Edge cases around the id-in-body pattern (PUT/PATCH)
"""
import pytest
import requests

from config.settings import settings

pytestmark = pytest.mark.negative

BASE = f"{settings.base_url}{settings.api_base}"


class TestMalformedRequests:

    def test_invalid_json_to_post_integrations_returns_4xx(self, client1):
        resp = client1._session.post(
            f"{BASE}/integrations",
            data="not json {{{{",
            headers={"Content-Type": "application/json"},
            timeout=settings.request_timeout,
        )
        assert 400 <= resp.status_code < 500, (
            f"Invalid JSON body should return 4xx, got {resp.status_code}"
        )

    def test_invalid_json_to_post_assets_returns_4xx(self, client1):
        resp = client1._session.post(
            f"{BASE}/assets",
            data="[not json",
            headers={"Content-Type": "application/json"},
            timeout=settings.request_timeout,
        )
        assert 400 <= resp.status_code < 500, (
            f"Invalid JSON body to POST /assets should return 4xx, got {resp.status_code}"
        )

    def test_null_body_to_post_integrations_returns_4xx(self, client1):
        resp = client1.post("/integrations", json=None)
        assert 400 <= resp.status_code < 500, (
            f"Null body to POST /integrations should return 4xx, got {resp.status_code}"
        )

    def test_array_body_to_post_integrations_returns_4xx(self, client1):
        resp = client1.post("/integrations", json=["name", "type"])
        assert 400 <= resp.status_code < 500, (
            f"Non-object JSON body to POST /integrations should return 4xx, got {resp.status_code}"
        )


class TestInvalidIds:

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../etc/passwd",
            "<script>alert(1)</script>",
            "' OR '1'='1",
            "a" * 500,
            "../admin",
        ],
        ids=["path_traversal", "xss_attempt", "sql_injection", "very_long_id", "relative_path"],
    )
    def test_malicious_integration_id_returns_4xx_not_500(self, client1, bad_id):
        resp = client1.get(f"/integrations/{bad_id}")
        assert resp.status_code < 500, (
            f"GET /integrations/{bad_id!r} caused a 500 — server must not crash on bad input"
        )
        assert resp.status_code >= 400, (
            f"Malicious id should return 4xx, got {resp.status_code}"
        )

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../etc/passwd",
            "<script>alert(1)</script>",
            "' OR '1'='1",
            "a" * 500,
        ],
        ids=["path_traversal", "xss_attempt", "sql_injection", "very_long_id"],
    )
    def test_malicious_asset_id_returns_4xx_not_500(self, client1, bad_id):
        resp = client1.get(f"/assets/{bad_id}")
        assert resp.status_code < 500, (
            f"GET /assets/{bad_id!r} caused a 500 — server must not crash on bad input"
        )


class TestMissingRequiredFields:

    def test_assets_list_without_integration_id_returns_400(self, client1):
        resp = client1.get("/assets")
        assert resp.status_code == 400, (
            f"GET /assets without integrationId must return 400, got {resp.status_code}"
        )

    def test_create_integration_missing_name(self, client1):
        resp = client1.post("/integrations", json={"type": "aws"})
        assert 400 <= resp.status_code < 500, (
            f"POST /integrations without name should return 4xx, got {resp.status_code}"
        )

    def test_create_integration_missing_type(self, client1):
        resp = client1.post("/integrations", json={"name": "no-type"})
        assert 400 <= resp.status_code < 500, (
            f"POST /integrations without type should return 4xx, got {resp.status_code}"
        )

    def test_create_asset_missing_name(self, integration_u1, client1):
        resp = client1.post("/assets", json={"integration_id": integration_u1["id"]})
        assert 400 <= resp.status_code < 500, (
            f"POST /assets without name should return 4xx, got {resp.status_code}"
        )

    def test_create_asset_missing_integration_id(self, client1):
        resp = client1.post("/assets", json={"name": "no-integration-id"})
        assert 400 <= resp.status_code < 500, (
            f"POST /assets without integration_id should return 4xx, got {resp.status_code}"
        )

    def test_create_asset_description_only_missing_required_fields(self, client1):
        """Body has only description — integration_id and name are required."""
        resp = client1.post(
            "/assets",
            json={"description": "missing integration_id and name"},
        )
        assert 400 <= resp.status_code < 500, (
            f"POST /assets with only description should return 4xx, got {resp.status_code}"
        )

    def test_update_integration_missing_id_in_body(self, client1):
        """PUT /integrations: id MUST be in the body — omitting it should fail."""
        resp = client1.put("/integrations", json={"name": "no-id-field"})
        assert 400 <= resp.status_code < 500, (
            f"PUT without id in body should return 4xx, got {resp.status_code}"
        )

    def test_update_asset_missing_id_in_body(self, client1):
        """PATCH /assets: id MUST be in the body — omitting it should fail."""
        resp = client1.patch("/assets", json={"name": "no-id-field"})
        assert 400 <= resp.status_code < 500, (
            f"PATCH without id in body should return 4xx, got {resp.status_code}"
        )


class TestInvalidPagination:

    def test_negative_page_returns_4xx_or_ignores(self, client1):
        resp = client1.get("/integrations", params={"page": -1})
        assert resp.status_code in (200, 400), (
            f"Negative page should return 200 (ignored) or 400, got {resp.status_code}"
        )
        # Must never 500
        assert resp.status_code != 500, "Negative page caused a 500 server error"

    def test_zero_limit_returns_4xx_or_ignores(self, client1):
        resp = client1.get("/integrations", params={"limit": 0})
        assert resp.status_code != 500, (
            f"limit=0 caused a 500 server error (got {resp.status_code})"
        )

    def test_negative_page_and_zero_limit_returns_400_or_422(self, client1):
        """Invalid page/limit together should be rejected as bad request (strict validation)."""
        resp = client1.get("/integrations", params={"page": -1, "limit": 0})
        assert resp.status_code in (400, 422), (
            f"GET /integrations with page=-1 and limit=0 should return 400 or 422, "
            f"got {resp.status_code}"
        )

    def test_non_integer_page_returns_4xx(self, client1):
        resp = client1.get("/integrations", params={"page": "abc"})
        assert 400 <= resp.status_code < 500, (
            f"Non-integer page should return 4xx, got {resp.status_code}"
        )

    def test_non_integer_limit_returns_4xx(self, client1):
        resp = client1.get("/integrations", params={"limit": "abc"})
        assert 400 <= resp.status_code < 500, (
            f"Non-integer limit should return 4xx, got {resp.status_code}"
        )


class TestWrongHttpMethods:

    def test_delete_on_integrations_collection_returns_405(self, client1):
        resp = client1._session.delete(
            f"{BASE}/integrations", timeout=settings.request_timeout
        )
        assert resp.status_code in (404, 405), (
            f"DELETE /integrations (no id) should return 405/404, got {resp.status_code}"
        )

    def test_post_on_assets_by_id_returns_405(self, asset_u1, client1):
        resp = client1.post(f"/assets/{asset_u1['id']}", json={})
        assert resp.status_code in (404, 405), (
            f"POST /assets/{{id}} should return 405/404, got {resp.status_code}"
        )


class TestErrorResponseFormat:

    def test_404_body_contains_code_and_message(self, client1):
        resp = client1.get("/integrations/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404, (
            f"GET nonexistent integration should return 404, got {resp.status_code}"
        )
        body = resp.json()
        assert "code" in body, f"404 body missing 'code' field: {body}"
        assert "message" in body, f"404 body missing 'message' field: {body}"

    def test_error_code_field_matches_http_status(self, client1):
        resp = client1.get("/integrations/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404, (
            f"GET nonexistent integration should return 404, got {resp.status_code}"
        )
        body = resp.json()
        assert body["code"] == 404, (
            f"error body 'code' field should be 404, got {body['code']}"
        )

    def test_400_body_is_valid_json(self, client1):
        resp = client1.get("/assets")  # missing integrationId → 400
        assert resp.status_code == 400, (
            f"GET /assets without integrationId should return 400, got {resp.status_code}"
        )
        try:
            resp.json()
        except Exception:
            pytest.fail("400 response body is not valid JSON")
