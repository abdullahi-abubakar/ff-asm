from locust import HttpUser, task, between, events
import uuid
import random

API_BASE = "/api/v1"
INTEGRATION_TYPES = ["aws", "gcp", "azure"]

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

    @task(4)
    def list_integrations(self):
        self.client.get(f"{API_BASE}/integrations", name="LIST integrations")

    @task(2)
    def create_integration(self):
        resp = self.client.post(
            f"{API_BASE}/integrations",
            json={"name": _rnd("t1-int-"), "type": random.choice(INTEGRATION_TYPES)},
            name="CREATE integration",
        )
        if resp.status_code == 200:
            iid = resp.json().get("id")
            if iid:
                self._integration_ids.append(iid)

    @task(2)
    def get_integration(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(f"{API_BASE}/integrations/{iid}", name="GET integration")

    @task(1)
    def list_assets(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(
            f"{API_BASE}/assets",
            params={"integrationId": iid},
            name="LIST assets",
        )

    @task(1)
    def create_asset(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.post(
            f"{API_BASE}/assets",
            json={"name": _rnd("t1-asset-"), "description": "load test", "integration_id": iid},
            name="CREATE asset",
        )


class Tenant2User(HttpUser):
    wait_time = between(0.05, 0.2)
    weight = 1

    def on_start(self):
        self.client.auth = ("test2", "test456")
        self.client.headers.update({"Content-Type": "application/json"})
        self._integration_ids = []
        self._asset_ids = []

    @task(4)
    def list_integrations(self):
        self.client.get(f"{API_BASE}/integrations", name="LIST integrations")

    @task(2)
    def create_integration(self):
        resp = self.client.post(
            f"{API_BASE}/integrations",
            json={"name": _rnd("t2-int-"), "type": random.choice(INTEGRATION_TYPES)},
            name="CREATE integration",
        )
        if resp.status_code == 200:
            iid = resp.json().get("id")
            if iid:
                self._integration_ids.append(iid)

    @task(2)
    def get_integration(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(f"{API_BASE}/integrations/{iid}", name="GET integration")

    @task(1)
    def list_assets(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.get(
            f"{API_BASE}/assets",
            params={"integrationId": iid},
            name="LIST assets",
        )

    @task(1)
    def create_asset(self):
        if not self._integration_ids:
            return
        iid = random.choice(self._integration_ids)
        self.client.post(
            f"{API_BASE}/assets",
            json={"name": _rnd("t2-asset-"), "description": "load test", "integration_id": iid},
            name="CREATE asset",
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
    print(f"{'='*60}\n")