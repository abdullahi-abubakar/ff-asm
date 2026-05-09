from locust import HttpUser, task, between, events
import uuid, random

API_BASE = "/api/v1"

def rnd(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class Tenant1User(HttpUser):
    wait_time = between(0.05, 0.2)
    weight = 1

    def on_start(self):
        self.client.auth = ("test1", "test123")
        self.client.headers.update({"Content-Type": "application/json"})

    @task(4)
    def list_integrations(self):
        self.client.get(f"{API_BASE}/integrations",
                        name="LIST integrations")

    @task(2)
    def create_integration(self):
        self.client.post(f"{API_BASE}/integrations",
                         json={"name": rnd("t1-"), "type": "aws"},
                         name="CREATE integration")

    @task(1)
    def list_assets_no_id(self):
        # Tests the required param validation — must return 400
        self.client.get(f"{API_BASE}/assets",
                        name="LIST assets (no integrationId)")


class Tenant2User(HttpUser):
    wait_time = between(0.05, 0.2)
    weight = 1

    def on_start(self):
        self.client.auth = ("test2", "test456")
        self.client.headers.update({"Content-Type": "application/json"})

    @task(4)
    def list_integrations(self):
        self.client.get(f"{API_BASE}/integrations",
                        name="LIST integrations")

    @task(2)
    def create_integration(self):
        self.client.post(f"{API_BASE}/integrations",
                         json={"name": rnd("t2-"), "type": "gcp"},
                         name="CREATE integration")

    @task(1)
    def list_assets_no_id(self):
        self.client.get(f"{API_BASE}/assets",
                        name="LIST assets (no integrationId)")


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
    print(f"  RPS            : {stats.total_rps:.1f}  (min: 17)")
    print(f"{'='*60}\n")