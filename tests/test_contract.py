"""
Contract Validation Tests
=========================
Every response from the live service is validated against the exact
schemas declared in the Swagger doc.

Schemas under test
------------------
model.Integration        {id, name, tenant_id, type}
model.Asset              {id, integration_id, name, description, tenant_id}
model.CreateIntegrationRequest  {name, type}
model.CreateAssetRequest        {name, description, integration_id}
httputil.HTTPError       {code, message}

Notable spec findings
----------------------
- DELETE /integrations/{id} returns 200 with no body schema (just "OK")
- DELETE /assets/{id}       returns 204 with a string body "asset deleted"
- The base path is /api/v1 (must not be omitted in requests)
"""
import pytest
import jsonschema
from typing import Any, Dict

from api.helpers import IntegrationClient, AssetClient
from config.settings import settings

pytestmark = pytest.mark.contract

# ------------------------------------------------------------------ #
# Inline schemas derived directly from the spec definitions
# ------------------------------------------------------------------ #

INTEGRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "id":        {"type": "string"},
        "name":      {"type": "string"},
        "tenant_id": {"type": "string"},
        "type":      {"type": "string"},
    },
}

ASSET_SCHEMA = {
    "type": "object",
    "properties": {
        "id":             {"type": "string"},
        "name":           {"type": "string"},
        "description":    {"type": "string"},
        "integration_id": {"type": "string"},
        "tenant_id":      {"type": "string"},
    },
}

HTTP_ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "code":    {"type": "integer"},
        "message": {"type": "string"},
    },
    "required": ["code", "message"],
}

INTEGRATION_LIST_SCHEMA = {
    "type": "array",
    "items": INTEGRATION_SCHEMA,
}

ASSET_LIST_SCHEMA = {
    "type": "array",
    "items": ASSET_SCHEMA,
}


def assert_schema(body: Any, schema: Dict, context: str = "") -> None:
    try:
        jsonschema.validate(instance=body, schema=schema)
    except jsonschema.ValidationError as exc:
        pytest.fail(f"Schema violation{' in ' + context if context else ''}: {exc.message}")


# ------------------------------------------------------------------ #
# Spec document itself
# ------------------------------------------------------------------ #

class TestSpecDocument:

    def test_spec_is_reachable_and_valid_json(self, openapi_spec):
        assert "paths" in openapi_spec
        assert "definitions" in openapi_spec

    def test_spec_declares_both_resources(self, openapi_spec):
        paths = openapi_spec["paths"]
        assert "/integrations" in paths, "Spec is missing /integrations"
        assert "/assets" in paths, "Spec is missing /assets"

    def test_spec_basepath_is_api_v1(self, openapi_spec):
        assert openapi_spec.get("basePath") == "/api/v1", (
            f"basePath must be /api/v1, got {openapi_spec.get('basePath')!r}"
        )

    def test_spec_declares_integration_schema(self, openapi_spec):
        schema = openapi_spec["definitions"].get("model.Integration", {})
        props = schema.get("properties", {})
        assert "id" in props
        assert "name" in props
        assert "tenant_id" in props
        assert "type" in props

    def test_spec_declares_asset_schema(self, openapi_spec):
        schema = openapi_spec["definitions"].get("model.Asset", {})
        props = schema.get("properties", {})
        assert "id" in props
        assert "name" in props
        assert "integration_id" in props
        assert "tenant_id" in props

    def test_spec_bug_list_integrations_missing_401(self, openapi_spec):
        """
        KNOWN BUG IN SPEC: GET /integrations does not declare 401.
        All authenticated endpoints must declare their auth failure codes.
        """
        responses = openapi_spec["paths"]["/integrations"]["get"]["responses"]
        assert "401" in responses, (
            "BUG IN SPEC: GET /integrations is missing 401 from declared responses. "
            "Service uses Basic Auth — 401 must be documented."
        )

    def test_spec_bug_post_integrations_missing_401(self, openapi_spec):
        """
        KNOWN BUG IN SPEC: POST /integrations does not declare 401.
        """
        responses = openapi_spec["paths"]["/integrations"]["post"]["responses"]
        assert "401" in responses, (
            "BUG IN SPEC: POST /integrations is missing 401 from declared responses."
        )

    def test_spec_bug_get_asset_list_requires_integration_id(self, openapi_spec):
        """
        GET /assets requires integrationId as a mandatory query param.
        Callers who omit it will get 400. This is easy to miss.
        """
        params = openapi_spec["paths"]["/assets"]["get"]["parameters"]
        integration_id_param = next(
            (p for p in params if p["name"] == "integrationId"), None
        )
        assert integration_id_param is not None, "GET /assets must declare integrationId param"
        assert integration_id_param.get("required") is True, (
            "integrationId must be marked required=true"
        )


# ------------------------------------------------------------------ #
# Integration response contracts
# ------------------------------------------------------------------ #

class TestIntegrationContracts:

    def test_create_response_matches_schema(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="contract-test", type_="aws")
        assert resp.status_code == 200
        assert_schema(resp.json(), INTEGRATION_SCHEMA, "POST /integrations")
        # Cleanup
        integrations1.delete(resp.json()["id"])

    def test_create_response_reflects_sent_name_and_type(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="my-integration", type_="gcp")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "my-integration", f"name mismatch: {body['name']!r}"
        assert body["type"] == "gcp", f"type mismatch: {body['type']!r}"
        integrations1.delete(body["id"])

    def test_create_response_has_id_and_tenant_id(self, integrations1: IntegrationClient):
        resp = integrations1.create()
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("id"), "created integration must have a non-empty id"
        assert body.get("tenant_id"), "created integration must have a non-empty tenant_id"
        integrations1.delete(body["id"])

    def test_get_by_id_response_matches_schema(self, integration_u1: dict, integrations1: IntegrationClient):
        resp = integrations1.get(integration_u1["id"])
        assert resp.status_code == 200
        assert_schema(resp.json(), INTEGRATION_SCHEMA, "GET /integrations/{id}")

    def test_list_response_is_array_of_integrations(self, integrations1: IntegrationClient):
        resp = integrations1.list()
        assert resp.status_code == 200
        assert_schema(resp.json(), INTEGRATION_LIST_SCHEMA, "GET /integrations")

    def test_update_response_matches_schema(self, integration_u1: dict, integrations1: IntegrationClient):
        resp = integrations1.update(integration_u1["id"], name="updated-name")
        assert resp.status_code == 200
        assert_schema(resp.json(), INTEGRATION_SCHEMA, "PUT /integrations")

    def test_update_reflects_new_name(self, integration_u1: dict, integrations1: IntegrationClient):
        resp = integrations1.update(integration_u1["id"], name="new-name")
        assert resp.status_code == 200
        assert resp.json()["name"] == "new-name", (
            f"PUT /integrations should return updated name, got {resp.json()['name']!r}"
        )

    def test_delete_returns_200(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="to-delete", type_="azure")
        assert resp.status_code == 200
        integration_id = resp.json()["id"]
        del_resp = integrations1.delete(integration_id)
        assert del_resp.status_code == 200, (
            f"DELETE /integrations/{{id}} should return 200, got {del_resp.status_code}"
        )

    def test_error_response_matches_http_error_schema(self, integrations1: IntegrationClient):
        resp = integrations1.get("nonexistent-id-xyz-000")
        assert resp.status_code == 404
        assert_schema(resp.json(), HTTP_ERROR_SCHEMA, "404 error body")


# ------------------------------------------------------------------ #
# Asset response contracts
# ------------------------------------------------------------------ #

class TestAssetContracts:

    def test_create_response_matches_schema(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"], name="contract-asset")
        assert resp.status_code == 200
        assert_schema(resp.json(), ASSET_SCHEMA, "POST /assets")
        assets1.delete(resp.json()["id"])

    def test_create_response_has_correct_integration_id(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["integration_id"] == integration_u1["id"], (
            f"Asset integration_id should be {integration_u1['id']!r}, got {body['integration_id']!r}"
        )
        assets1.delete(body["id"])

    def test_create_response_has_tenant_id(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"])
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("tenant_id"), "created asset must have a non-empty tenant_id"
        assets1.delete(body["id"])

    def test_list_response_is_array_of_assets(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.list(integration_id=integration_u1["id"])
        assert resp.status_code == 200
        assert_schema(resp.json(), ASSET_LIST_SCHEMA, "GET /assets")

    def test_get_by_id_response_matches_schema(self, asset_u1: dict, assets1: AssetClient):
        resp = assets1.get(asset_u1["id"])
        assert resp.status_code == 200
        assert_schema(resp.json(), ASSET_SCHEMA, "GET /assets/{id}")

    def test_update_response_matches_schema(self, asset_u1: dict, assets1: AssetClient):
        resp = assets1.update(asset_u1["id"], name="updated-asset")
        assert resp.status_code == 200
        assert_schema(resp.json(), ASSET_SCHEMA, "PATCH /assets")

    def test_update_reflects_new_name(self, asset_u1: dict, assets1: AssetClient):
        resp = assets1.update(asset_u1["id"], name="shiny-new-name")
        assert resp.status_code == 200
        assert resp.json()["name"] == "shiny-new-name"

    def test_delete_returns_204(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"])
        assert resp.status_code == 200
        asset_id = resp.json()["id"]
        del_resp = assets1.delete(asset_id)
        assert del_resp.status_code == 204, (
            f"DELETE /assets/{{id}} should return 204, got {del_resp.status_code}"
        )

    def test_list_without_integration_id_returns_400(self, client1):
        """integrationId is required — omitting it must yield 400."""
        resp = client1.get("/assets")
        assert resp.status_code == 400, (
            f"GET /assets without integrationId should return 400, got {resp.status_code}"
        )
