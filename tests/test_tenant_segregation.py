"""
Tenant Segregation Tests
========================
The API is multi-tenant.  Both Integrations and Assets carry a
`tenant_id` field.  The invariants are:

  1. Each user's tenant_id is consistent across all their resources.
  2. A user's list endpoints return ONLY their own resources.
  3. A user cannot read a resource owned by another tenant by ID.
  4. A user cannot update a resource owned by another tenant.
  5. A user cannot delete a resource owned by another tenant.
  6. Assets are doubly isolated: by tenant AND by integration_id.
     user1 must not access user2's assets even with user2's integration_id.

A failure in any of these tests represents a DATA BREACH, not just a bug.
"""
import pytest

from api.helpers import IntegrationClient, AssetClient
from config.settings import HTTP_POST_CREATE_OK

pytestmark = pytest.mark.tenant


# ------------------------------------------------------------------ #
# Tenant ID consistency
# ------------------------------------------------------------------ #

class TestTenantIdConsistency:

    def test_all_user1_integrations_share_same_tenant_id(self, integrations1: IntegrationClient):
        """Every integration created by user1 must carry the same tenant_id."""
        ids = []
        tenant_ids = set()
        for i in range(3):
            resp = integrations1.create(name=f"consistency-{i}")
            assert resp.status_code in HTTP_POST_CREATE_OK, (
                f"POST /integrations (consistency-{i}) should return 200 or 201, got {resp.status_code}: {resp.text[:500]!r}"
            )
            body = resp.json()
            ids.append(body["id"])
            tenant_ids.add(body["tenant_id"])

        for id_ in ids:
            integrations1.delete(id_)

        assert len(tenant_ids) == 1, (
            f"user1 created integrations with different tenant_ids: {tenant_ids}"
        )

    def test_user1_and_user2_have_different_tenant_ids(
        self, integration_u1: dict, integration_u2: dict
    ):
        """The two pre-populated users must belong to different tenants."""
        tid1 = integration_u1["tenant_id"]
        tid2 = integration_u2["tenant_id"]
        assert tid1 != tid2, (
            f"user1 and user2 share the same tenant_id {tid1!r} — "
            f"this means the service cannot distinguish tenants."
        )

    def test_asset_tenant_id_matches_integration_tenant_id(
        self, integration_u1: dict, asset_u1: dict
    ):
        """An asset's tenant_id must equal the tenant_id of its parent integration."""
        assert asset_u1["tenant_id"] == integration_u1["tenant_id"], (
            f"Asset tenant_id {asset_u1['tenant_id']!r} does not match "
            f"integration tenant_id {integration_u1['tenant_id']!r}"
        )


# ------------------------------------------------------------------ #
# Integration list isolation
# ------------------------------------------------------------------ #

class TestIntegrationListIsolation:

    def test_user1_list_excludes_user2_integration(
        self,
        integration_u2: dict,
        integrations1: IntegrationClient,
    ):
        resp = integrations1.list()
        assert resp.status_code == 200, (
            f"GET /integrations should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        ids = [item["id"] for item in resp.json()]
        assert integration_u2["id"] not in ids, (
            f"DATA BREACH: user1's integration list contains {integration_u2['id']!r} "
            f"which was created by user2."
        )

    def test_user2_list_excludes_user1_integration(
        self,
        integration_u1: dict,
        integrations2: IntegrationClient,
    ):
        resp = integrations2.list()
        assert resp.status_code == 200, (
            f"GET /integrations should return 200, got {resp.status_code}: {resp.text[:500]!r}"
        )
        ids = [item["id"] for item in resp.json()]
        assert integration_u1["id"] not in ids, (
            f"DATA BREACH: user2's integration list contains {integration_u1['id']!r} "
            f"which was created by user1."
        )


# ------------------------------------------------------------------ #
# Integration direct access isolation
# ------------------------------------------------------------------ #

class TestIntegrationReadIsolation:

    def test_user2_cannot_get_user1_integration_by_id(
        self,
        integration_u1: dict,
        integrations2: IntegrationClient,
    ):
        resp = integrations2.get(integration_u1["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 can GET user1's integration {integration_u1['id']!r} "
            f"(status {resp.status_code})"
        )

    def test_user1_cannot_get_user2_integration_by_id(
        self,
        integration_u2: dict,
        integrations1: IntegrationClient,
    ):
        resp = integrations1.get(integration_u2["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 can GET user2's integration {integration_u2['id']!r} "
            f"(status {resp.status_code})"
        )


# ------------------------------------------------------------------ #
# Integration mutation isolation
# ------------------------------------------------------------------ #

class TestIntegrationWriteIsolation:

    def test_user2_cannot_update_user1_integration(
        self,
        integration_u1: dict,
        integrations2: IntegrationClient,
    ):
        resp = integrations2.update(integration_u1["id"], name="hacked")
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 could UPDATE user1's integration "
            f"(id={integration_u1['id']!r}, status={resp.status_code})"
        )

    def test_user1_cannot_update_user2_integration(
        self,
        integration_u2: dict,
        integrations1: IntegrationClient,
    ):
        resp = integrations1.update(integration_u2["id"], name="hacked")
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 could UPDATE user2's integration "
            f"(id={integration_u2['id']!r}, status={resp.status_code})"
        )

    def test_user2_cannot_delete_user1_integration(
        self,
        integration_u1: dict,
        integrations2: IntegrationClient,
    ):
        resp = integrations2.delete(integration_u1["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 could DELETE user1's integration "
            f"(id={integration_u1['id']!r}, status={resp.status_code})"
        )

    def test_user1_cannot_delete_user2_integration(
        self,
        integration_u2: dict,
        integrations1: IntegrationClient,
    ):
        resp = integrations1.delete(integration_u2["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 could DELETE user2's integration "
            f"(id={integration_u2['id']!r}, status={resp.status_code})"
        )


# ------------------------------------------------------------------ #
# Asset list isolation
# ------------------------------------------------------------------ #

class TestAssetListIsolation:

    def test_user1_cannot_list_assets_under_user2_integration(
        self,
        integration_u2: dict,
        asset_u2: dict,
        assets1: AssetClient,
    ):
        """
        user1 querying GET /assets?integrationId=<user2's id>
        must receive 403/404, not user2's assets.
        """
        resp = assets1.list(integration_id=integration_u2["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 listed assets under user2's integration "
            f"(integrationId={integration_u2['id']!r}, status={resp.status_code}). "
            f"Body: {resp.text[:200]}"
        )

    def test_user2_cannot_list_assets_under_user1_integration(
        self,
        integration_u1: dict,
        asset_u1: dict,
        assets2: AssetClient,
    ):
        resp = assets2.list(integration_id=integration_u1["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 listed assets under user1's integration "
            f"(integrationId={integration_u1['id']!r}, status={resp.status_code}). "
            f"Body: {resp.text[:200]}"
        )


# ------------------------------------------------------------------ #
# Asset direct access isolation
# ------------------------------------------------------------------ #

class TestAssetReadIsolation:

    def test_user2_cannot_get_user1_asset_by_id(
        self,
        asset_u1: dict,
        assets2: AssetClient,
    ):
        resp = assets2.get(asset_u1["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 can GET user1's asset {asset_u1['id']!r} "
            f"(status {resp.status_code})"
        )

    def test_user1_cannot_get_user2_asset_by_id(
        self,
        asset_u2: dict,
        assets1: AssetClient,
    ):
        resp = assets1.get(asset_u2["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 can GET user2's asset {asset_u2['id']!r} "
            f"(status {resp.status_code})"
        )


# ------------------------------------------------------------------ #
# Asset mutation isolation
# ------------------------------------------------------------------ #

class TestAssetWriteIsolation:

    def test_user2_cannot_update_user1_asset(
        self,
        asset_u1: dict,
        assets2: AssetClient,
    ):
        resp = assets2.update(asset_u1["id"], name="hijacked")
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 could UPDATE user1's asset {asset_u1['id']!r} "
            f"(status {resp.status_code})"
        )

    def test_user1_cannot_update_user2_asset(
        self,
        asset_u2: dict,
        assets1: AssetClient,
    ):
        resp = assets1.update(asset_u2["id"], name="hijacked")
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 could UPDATE user2's asset {asset_u2['id']!r} "
            f"(status {resp.status_code})"
        )

    def test_user2_cannot_delete_user1_asset(
        self,
        asset_u1: dict,
        assets2: AssetClient,
    ):
        resp = assets2.delete(asset_u1["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user2 could DELETE user1's asset {asset_u1['id']!r} "
            f"(status {resp.status_code})"
        )

    def test_user1_cannot_delete_user2_asset(
        self,
        asset_u2: dict,
        assets1: AssetClient,
    ):
        resp = assets1.delete(asset_u2["id"])
        assert resp.status_code in (403, 404), (
            f"DATA BREACH: user1 could DELETE user2's asset {asset_u2['id']!r} "
            f"(status {resp.status_code})"
        )
