"""
CRUD Tests
==========
Full Create → Read → Update → Delete lifecycle for both
Integrations and Assets.

Spec-specific notes that shape these tests
------------------------------------------
- PUT /integrations  — id goes in the request BODY, not the path
- PATCH /assets      — id goes in the request BODY, not the path
- DELETE /integrations/{id} → 200 (not 204)
- DELETE /assets/{id}       → 204
- GET /assets requires ?integrationId=<id>  (mandatory query param)
- POST /assets returns 409 Conflict on duplicate name within same integration
"""
import pytest
import uuid

from api.helpers import IntegrationClient, AssetClient
from config.settings import HTTP_POST_CREATE_OK, settings

pytestmark = pytest.mark.crud


# ------------------------------------------------------------------ #
# Integration CRUD
# ------------------------------------------------------------------ #

class TestIntegrationCreate:

    def test_create_with_all_fields_returns_200(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="full-create-test", type_="aws")
        assert resp.status_code in HTTP_POST_CREATE_OK, f"POST /integrations: {resp.status_code} {resp.text}"
        integrations1.delete(resp.json()["id"])

    def test_create_without_name_returns_4xx(self, client1):
        resp = client1.post("/integrations", json={"type": "aws"})
        assert 400 <= resp.status_code < 500, (
            f"Missing name should return 4xx, got {resp.status_code}"
        )

    def test_create_without_type_returns_4xx(self, client1):
        resp = client1.post("/integrations", json={"name": "no-type"})
        assert 400 <= resp.status_code < 500, (
            f"Missing type should return 4xx, got {resp.status_code}"
        )

    def test_create_with_empty_body_returns_4xx(self, client1):
        resp = client1.post("/integrations", json={})
        assert 400 <= resp.status_code < 500, (
            f"POST /integrations with empty body should return 4xx, got {resp.status_code}"
        )

    def test_created_id_is_non_empty_string(self, integrations1: IntegrationClient):
        resp = integrations1.create()
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        body = resp.json()
        assert isinstance(body.get("id"), str) and body["id"], "id must be a non-empty string"
        integrations1.delete(body["id"])


class TestIntegrationRead:

    def test_get_by_id_returns_correct_resource(self, integration_u1: dict, integrations1: IntegrationClient):
        resp = integrations1.get(integration_u1["id"])
        assert resp.status_code == 200, (
            f"GET /integrations/{{id}} should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        assert resp.json()["id"] == integration_u1["id"], (
            f"GET body id should be {integration_u1['id']!r}, got {resp.json().get('id')!r}"
        )

    def test_get_nonexistent_id_returns_404(self, integrations1: IntegrationClient):
        resp = integrations1.get("00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404, (
            f"GET nonexistent integration should return 404, got {resp.status_code}"
        )

    def test_list_returns_200(self, integrations1: IntegrationClient):
        resp = integrations1.list()
        assert resp.status_code == 200, (
            f"GET /integrations should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )

    def test_list_contains_created_integration(self, integration_u1: dict, integrations1: IntegrationClient):
        resp = integrations1.list()
        assert resp.status_code == 200, (
            f"GET /integrations should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        ids = [item["id"] for item in resp.json()]
        assert integration_u1["id"] in ids, (
            f"Newly created integration {integration_u1['id']!r} not found in list"
        )

    def test_pagination_page_and_limit(self, integrations1: IntegrationClient):
        resp = integrations1.list(page=1, limit=5)
        assert resp.status_code == 200, (
            f"GET /integrations with pagination should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        body = resp.json()
        assert isinstance(body, list), (
            f"Paginated GET /integrations must return a JSON array, got {type(body).__name__}"
        )
        assert len(body) <= 5, f"limit=5 should return ≤5 items, got {len(body)}"

    def test_list_response_is_array(self, integrations1: IntegrationClient):
        resp = integrations1.list()
        assert isinstance(resp.json(), list), "GET /integrations must return a JSON array"


class TestIntegrationUpdate:

    def test_update_name_via_body_id(self, integration_u1: dict, integrations1: IntegrationClient):
        """PUT /integrations takes id in the body, NOT in the path."""
        new_name = f"updated-{uuid.uuid4().hex[:6]}"
        resp = integrations1.update(integration_u1["id"], name=new_name)
        assert resp.status_code == 200, f"PUT /integrations: {resp.status_code} {resp.text}"
        assert resp.json()["name"] == new_name, (
            f"PUT /integrations should return name {new_name!r}, got {resp.json().get('name')!r}"
        )

    def test_update_without_id_in_body_returns_4xx(self, client1):
        """id is required in body — omitting it must fail."""
        resp = client1.put("/integrations", json={"name": "no-id"})
        assert 400 <= resp.status_code < 500, (
            f"PUT without id in body should fail, got {resp.status_code}"
        )

    def test_update_nonexistent_id_returns_404(self, integrations1: IntegrationClient):
        resp = integrations1.update("00000000-0000-0000-0000-000000000000", name="ghost")
        assert resp.status_code == 404, (
            f"PUT nonexistent integration should return 404, got {resp.status_code}"
        )


class TestIntegrationDelete:

    def test_delete_returns_200(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="to-delete", type_="azure")
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations (setup) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        del_resp = integrations1.delete(resp.json()["id"])
        assert del_resp.status_code == 200, (
            f"DELETE /integrations/{{id}} should return 200, got {del_resp.status_code}"
        )

    def test_deleted_integration_returns_404_on_get(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="to-delete-2", type_="aws")
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations (setup) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        iid = resp.json()["id"]
        integrations1.delete(iid)
        get_resp = integrations1.get(iid)
        assert get_resp.status_code == 404, (
            f"Deleted integration should return 404 on GET, got {get_resp.status_code}"
        )

    def test_double_delete_returns_404(self, integrations1: IntegrationClient):
        resp = integrations1.create(name="double-delete", type_="aws")
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations (setup) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        iid = resp.json()["id"]
        integrations1.delete(iid)
        second_delete = integrations1.delete(iid)
        assert second_delete.status_code == 404, (
            f"Second DELETE should return 404, got {second_delete.status_code}"
        )

    def test_delete_nonexistent_returns_404(self, integrations1: IntegrationClient):
        resp = integrations1.delete("00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404, (
            f"DELETE nonexistent integration should return 404, got {resp.status_code}"
        )


# ------------------------------------------------------------------ #
# Asset CRUD
# ------------------------------------------------------------------ #

class TestAssetCreate:

    def test_create_with_all_fields_returns_200(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(
            integration_id=integration_u1["id"],
            name="full-asset-test",
            description="a test asset",
        )
        assert resp.status_code in HTTP_POST_CREATE_OK, f"POST /assets: {resp.status_code} {resp.text}"
        assets1.delete(resp.json()["id"])

    def test_create_without_integration_id_returns_4xx(self, client1):
        resp = client1.post("/assets", json={"name": "no-integration"})
        assert 400 <= resp.status_code < 500, (
            f"POST /assets without integration_id should return 4xx, got {resp.status_code}"
        )

    def test_create_without_name_returns_4xx(self, integration_u1: dict, client1):
        resp = client1.post("/assets", json={"integration_id": integration_u1["id"]})
        assert 400 <= resp.status_code < 500, (
            f"POST /assets without name should return 4xx, got {resp.status_code}"
        )

    def test_duplicate_asset_name_in_same_integration_returns_409(
        self, integration_u1: dict, assets1: AssetClient
    ):
        """Spec declares 409 Conflict for duplicate assets."""
        name = f"dup-asset-{uuid.uuid4().hex[:6]}"
        resp1 = assets1.create(integration_id=integration_u1["id"], name=name)
        assert resp1.status_code in HTTP_POST_CREATE_OK, (
            f"First POST /assets (setup) should return 200 or 201, got {resp1.status_code}: {resp1.text[:500]!r}"
        )

        resp2 = assets1.create(integration_id=integration_u1["id"], name=name)
        assets1.delete(resp1.json()["id"])
        assert resp2.status_code == 409, (
            f"Duplicate asset name should return 409, got {resp2.status_code}. "
            f"Body: {resp2.text}"
        )

    def test_same_asset_name_allowed_across_different_integrations(
        self, integrations1: IntegrationClient, assets1: AssetClient
    ):
        """Same name is fine as long as integration_id differs."""
        resp_i1 = integrations1.create()
        resp_i2 = integrations1.create()
        assert resp_i1.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations (setup i1) should return 200 or 201, got {resp_i1.status_code}: {resp_i1.text[:500]!r}"
        )
        assert resp_i2.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations (setup i2) should return 200 or 201, got {resp_i2.status_code}: {resp_i2.text[:500]!r}"
        )
        id1, id2 = resp_i1.json()["id"], resp_i2.json()["id"]

        name = f"shared-name-{uuid.uuid4().hex[:6]}"
        a1 = assets1.create(integration_id=id1, name=name)
        a2 = assets1.create(integration_id=id2, name=name)

        # Cleanup
        if a1.status_code in HTTP_POST_CREATE_OK:
            assets1.delete(a1.json()["id"])
        if a2.status_code in HTTP_POST_CREATE_OK:
            assets1.delete(a2.json()["id"])
        integrations1.delete(id1)
        integrations1.delete(id2)

        assert (
            a1.status_code in HTTP_POST_CREATE_OK and a2.status_code in HTTP_POST_CREATE_OK
        ), (
            "Same asset name in different integrations should be allowed "
            f"(got {a1.status_code} and {a2.status_code})"
        )

    def test_create_asset_under_nonexistent_integration_returns_4xx(self, assets1: AssetClient):
        resp = assets1.create(
            integration_id="00000000-0000-0000-0000-000000000000",
            name="orphan-asset",
        )
        assert 400 <= resp.status_code < 500, (
            f"Creating asset under nonexistent integration should fail, got {resp.status_code}"
        )


class TestAssetRead:

    def test_get_asset_by_id_returns_correct_resource(self, asset_u1: dict, assets1: AssetClient):
        resp = assets1.get(asset_u1["id"])
        assert resp.status_code == 200, (
            f"GET /assets/{{id}} should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        assert resp.json()["id"] == asset_u1["id"], (
            f"GET body id should be {asset_u1['id']!r}, got {resp.json().get('id')!r}"
        )

    @pytest.mark.parametrize(
        "missing_id",
        ["00000000-0000-0000-0000-000000000000", "999999"],
        ids=["nil_uuid", "numeric_id"],
    )
    def test_get_nonexistent_asset_returns_404(self, assets1: AssetClient, missing_id: str):
        resp = assets1.get(missing_id)
        assert resp.status_code == 404, (
            f"GET nonexistent asset {missing_id!r} should return 404, got {resp.status_code}"
        )

    def test_list_assets_by_integration_id(self, integration_u1: dict, asset_u1: dict, assets1: AssetClient):
        resp = assets1.list(integration_id=integration_u1["id"])
        assert resp.status_code == 200, (
            f"GET /assets should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        ids = [a["id"] for a in resp.json()]
        assert asset_u1["id"] in ids, (
            f"Asset {asset_u1['id']!r} not in list for integration {integration_u1['id']!r}"
        )

    def test_list_assets_without_integration_id_returns_400(self, client1):
        resp = client1.get("/assets")  # missing required integrationId
        assert resp.status_code == 400, (
            f"Missing integrationId should return 400, got {resp.status_code}"
        )

    def test_list_assets_pagination(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.list(integration_id=integration_u1["id"], page=1, limit=3)
        assert resp.status_code == 200, (
            f"GET /assets with pagination should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        assert len(resp.json()) <= 3, (
            f"limit=3 should return ≤3 items, got {len(resp.json())}"
        )


class TestAssetUpdate:

    def test_update_asset_name_via_body_id(self, asset_u1: dict, assets1: AssetClient):
        """PATCH /assets takes id in the body, NOT in the path."""
        new_name = f"patched-{uuid.uuid4().hex[:6]}"
        resp = assets1.update(asset_u1["id"], name=new_name)
        assert resp.status_code == 200, f"PATCH /assets: {resp.status_code} {resp.text}"
        assert resp.json()["name"] == new_name, (
            f"PATCH /assets should return name {new_name!r}, got {resp.json().get('name')!r}"
        )

    def test_update_asset_description(self, asset_u1: dict, assets1: AssetClient):
        new_desc = "updated description"
        resp = assets1.update(asset_u1["id"], description=new_desc)
        assert resp.status_code == 200, (
            f"PATCH /assets should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        assert resp.json()["description"] == new_desc, (
            f"PATCH /assets should return description {new_desc!r}, got {resp.json().get('description')!r}"
        )

    def test_update_asset_without_id_in_body_returns_4xx(self, client1):
        resp = client1.patch("/assets", json={"name": "no-id"})
        assert 400 <= resp.status_code < 500, (
            f"PATCH /assets without id in body should return 4xx, got {resp.status_code}"
        )

    def test_update_nonexistent_asset_returns_404(self, assets1: AssetClient):
        resp = assets1.update("00000000-0000-0000-0000-000000000000", name="ghost")
        assert resp.status_code == 404, (
            f"PATCH nonexistent asset should return 404, got {resp.status_code}"
        )


class TestAssetDelete:

    def test_delete_returns_204(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"], name="delete-me")
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /assets (setup) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        del_resp = assets1.delete(resp.json()["id"])
        assert del_resp.status_code == 204, (
            f"DELETE /assets/{{id}} should return 204, got {del_resp.status_code}"
        )

    def test_deleted_asset_returns_404_on_get(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"], name="delete-then-get")
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /assets (setup) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        aid = resp.json()["id"]
        assets1.delete(aid)
        get_resp = assets1.get(aid)
        assert get_resp.status_code == 404, (
            f"GET deleted asset should return 404, got {get_resp.status_code}"
        )

    def test_double_delete_returns_404(self, integration_u1: dict, assets1: AssetClient):
        resp = assets1.create(integration_id=integration_u1["id"], name="double-delete-asset")
        assert resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /assets (setup) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
        )
        aid = resp.json()["id"]
        assets1.delete(aid)
        second = assets1.delete(aid)
        assert second.status_code == 404, (
            f"Second DELETE asset should return 404, got {second.status_code}"
        )

    def test_deleting_integration_cascades_to_assets(
        self, integrations1: IntegrationClient, assets1: AssetClient
    ):
        """
        When an integration is deleted, its assets should no longer be accessible.
        This tests referential integrity.
        """
        int_resp = integrations1.create(name="cascade-test")
        assert int_resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /integrations (setup) should return 200 or 201, got {int_resp.status_code}: {int_resp.text[:500]!r}"
        )
        iid = int_resp.json()["id"]

        asset_resp = assets1.create(integration_id=iid, name="orphan-asset")
        assert asset_resp.status_code in HTTP_POST_CREATE_OK, (
            f"POST /assets (setup) should return 200 or 201, got {asset_resp.status_code}: {asset_resp.text[:500]!r}"
        )
        aid = asset_resp.json()["id"]

        integrations1.delete(iid)

        # Asset should now be gone or inaccessible
        get_resp = assets1.get(aid)
        assert get_resp.status_code in (404, 400), (
            f"After deleting parent integration, asset should return 404/400, "
            f"got {get_resp.status_code}"
        )
