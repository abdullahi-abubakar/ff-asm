from locust import HttpUser, task, between, events
import uuid
import random

from config.settings import HTTP_POST_CREATE_OK

API_BASE = "/api/v1"
INTEGRATION_TYPES = ["aws", "gcp", "azure", "github", "datadog"]


def _rnd(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class Tenant1User(HttpUser):
    wait_time = between(0.05, 0.2)
    weight = 1

    def on_start(self):
        self.client.auth = ("test1", "test123")
        self.client.headers.update({"Content-Type": "application/json"})
        self._integration_ids = []
        self._asset_ids = []

        # Step 1 — fetch all existing integrations and store their IDs
        resp = self.client.get(
            f"{API_BASE}/integrations",
            name="SETUP get all integrations",
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    iid = item.get("id")
                    if iid:
                        self._integration_ids.append(iid)

    # -------------------------------------------------- #
    # Integration tasks
    # -------------------------------------------------- #

    @task(3)
    def list_integrations(self):
        """GET all integrations and refresh stored IDs."""
        resp = self.client.get(
            f"{API_BASE}/integrations",
            name="GET LIST integrations",
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    iid = item.get("id")
                    if iid and iid not in self._integration_ids:
                        self._integration_ids.append(iid)

    @task(2)
    def create_integration(self):
        """POST — random name and type each time."""
        resp = self.client.post(
            f"{API_BASE}/integrations",
            json={
                "name": _rnd("t1-int-"),
                "type": random.choice(INTEGRATION_TYPES),
            },
            name="POST CREATE integration",
        )
        if resp.status_code in HTTP_POST_CREATE_OK:
            iid = resp.json().get("id")
            if iid:
                self._integration_ids.append(iid)

    @task(2)
    def get_integration_by_id(self):
        """GET one — pick a single stored ID."""
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(
            f"{API_BASE}/integrations/{iid}",
            name="GET integration by id",
        )

    @task(1)
    def update_integration(self):
        """
        PUT — spec takes id in the body, not the path.
        Pick one stored ID, update its name.
        """
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.put(
            f"{API_BASE}/integrations",
            json={"id": iid, "name": _rnd("updated-")},
            name="PUT UPDATE integration",
        )

    @task(1)
    def delete_integration(self):
        """DELETE — pop from stored IDs so we don't delete the same one twice."""
        if not self._integration_ids:
            return
        iid = self._integration_ids.pop(0)
        self.client.delete(
            f"{API_BASE}/integrations/{iid}",
            name="DELETE integration",
        )

    # -------------------------------------------------- #
    # Asset tasks
    # -------------------------------------------------- #

    @task(2)
    def list_assets(self):
        """GET assets — use one stored integration ID as the required query param."""
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(
            f"{API_BASE}/assets",
            params={"integrationId": iid},
            name="GET LIST assets",
        )

    @task(2)
    def create_asset(self):
        """POST asset — use one stored integration ID as the parent."""
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        resp = self.client.post(
            f"{API_BASE}/assets",
            json={
                "name": _rnd("t1-asset-"),
                "description": f"load test asset for {iid}",
                "integration_id": iid,
            },
            name="POST CREATE asset",
        )
        if resp.status_code in HTTP_POST_CREATE_OK:
            aid = resp.json().get("id")
            if aid:
                self._asset_ids.append(aid)

    @task(1)
    def get_asset_by_id(self):
        """GET asset by its own ID."""
        if not self._asset_ids:
            return
        aid = random.choice(self._asset_ids)
        self.client.get(
            f"{API_BASE}/assets/{aid}",
            name="GET asset by id",
        )

    @task(1)
    def update_asset(self):
        """
        PATCH — spec takes id in the body, not the path.
        Pick one stored asset ID, update its name.
        """
        if not self._asset_ids:
            return
        aid = random.choice(self._asset_ids)
        self.client.patch(
            f"{API_BASE}/assets",
            json={"id": aid, "name": _rnd("patched-")},
            name="PATCH UPDATE asset",
        )

    @task(1)
    def delete_asset(self):
        """DELETE — pop from stored asset IDs."""
        if not self._asset_ids:
            return
        aid = self._asset_ids.pop(0)
        self.client.delete(
            f"{API_BASE}/assets/{aid}",
            name="DELETE asset",
        )


class Tenant2User(HttpUser):
    wait_time = between(0.05, 0.2)
    weight = 1

    def on_start(self):
        self.client.auth = ("test2", "test456")
        self.client.headers.update({"Content-Type": "application/json"})
        self._integration_ids = []
        self._asset_ids = []

        # Step 1 — fetch all existing integrations for this tenant
        resp = self.client.get(
            f"{API_BASE}/integrations",
            name="SETUP get all integrations",
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    iid = item.get("id")
                    if iid:
                        self._integration_ids.append(iid)

    @task(3)
    def list_integrations(self):
        resp = self.client.get(
            f"{API_BASE}/integrations",
            name="GET LIST integrations",
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    iid = item.get("id")
                    if iid and iid not in self._integration_ids:
                        self._integration_ids.append(iid)

    @task(2)
    def create_integration(self):
        resp = self.client.post(
            f"{API_BASE}/integrations",
            json={
                "name": _rnd("t2-int-"),
                "type": random.choice(INTEGRATION_TYPES),
            },
            name="POST CREATE integration",
        )
        if resp.status_code in HTTP_POST_CREATE_OK:
            iid = resp.json().get("id")
            if iid:
                self._integration_ids.append(iid)

    @task(2)
    def get_integration_by_id(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(
            f"{API_BASE}/integrations/{iid}",
            name="GET integration by id",
        )

    @task(1)
    def update_integration(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.put(
            f"{API_BASE}/integrations",
            json={"id": iid, "name": _rnd("updated-")},
            name="PUT UPDATE integration",
        )

    @task(1)
    def delete_integration(self):
        if not self._integration_ids:
            return
        iid = self._integration_ids.pop(0)
        self.client.delete(
            f"{API_BASE}/integrations/{iid}",
            name="DELETE integration",
        )

    @task(2)
    def list_assets(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(
            f"{API_BASE}/assets",
            params={"integrationId": iid},
            name="GET LIST assets",
        )

    @task(2)
    def create_asset(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        resp = self.client.post(
            f"{API_BASE}/assets",
            json={
                "name": _rnd("t2-asset-"),
                "description": f"load test asset for {iid}",
                "integration_id": iid,
            },
            name="POST CREATE asset",
        )
        if resp.status_code in HTTP_POST_CREATE_OK:
            aid = resp.json().get("id")
            if aid:
                self._asset_ids.append(aid)

    @task(1)
    def get_asset_by_id(self):
        if not self._asset_ids:
            return
        aid = random.choice(self._asset_ids)
        self.client.get(
            f"{API_BASE}/assets/{aid}",
            name="GET asset by id",
        )

    @task(1)
    def update_asset(self):
        if not self._asset_ids:
            return
        aid = random.choice(self._asset_ids)
        self.client.patch(
            f"{API_BASE}/assets",
            json={"id": aid, "name": _rnd("patched-")},
            name="PATCH UPDATE asset",
        )

    @task(1)
    def delete_asset(self):
        if not self._asset_ids:
            return
        aid = self._asset_ids.pop(0)
        self.client.delete(
            f"{API_BASE}/assets/{aid}",
            name="DELETE asset",
        )


MAX_ERROR_RATE = 0.01
P95_THRESHOLD_MS = 1_000
MIN_RPS = 17


@events.quitting.add_listener
def check_thresholds(environment, **_kwargs):
    stats = environment.runner.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    failure_rate = stats.fail_ratio

    print(f"\n{'='*60}")
    print(f"  Total requests : {stats.num_requests:,}")
    print(f"  Failures       : {stats.num_failures:,}")
    print(f"  Error rate     : {failure_rate:.2%}  (max: 1%)")
    print(f"  p95 resp time  : {p95:.0f} ms  (max: 1000ms)")
    print(f"  RPS            : {stats.total_rps:.1f}  (min: {MIN_RPS})")
    print(f"{'='*60}\n")

    failed = False
    if failure_rate > MAX_ERROR_RATE:
        print(f"  FAIL: error rate {failure_rate:.2%} > {MAX_ERROR_RATE:.0%}")
        failed = True
    if p95 > P95_THRESHOLD_MS:
        print(f"  FAIL: p95 {p95:.0f}ms > {P95_THRESHOLD_MS}ms")
        failed = True
    if not failed:
        print("  PASS: all thresholds met ✓")