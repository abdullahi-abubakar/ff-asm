# QA Test Automation Suite

### `infralightio/test-integration-api`

A production-grade test automation framework for the QA Test API — a multi-tenant REST service with intentional bugs, built to be found.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [API Under Test](#api-under-test)
- [Test Suite Breakdown](#test-suite-breakdown)
- [Known Bugs Targeted](#known-bugs-targeted)
- [Running the Tests](#running-the-tests)
- [Configuration](#configuration)
- [Reports](#reports)
- [Design Decisions](#design-decisions)
- [Extending the Suite](#extending-the-suite)

---

## Prerequisites


| Tool                       | Version    | Required for                       |
| -------------------------- | ---------- | ---------------------------------- |
| Docker + Docker Compose v2 | any recent | `make run` (one-command execution) |
| Python                     | 3.12+      | Local runs only                    |
| pip                        | any        | Local runs only                    |


If you only want to use the one-command runner, **Docker is the only requirement**.

---

## Quick Start

```bash
# 1. Unzip the project
unzip test-integration-suite-v2.zip
cd test-integration

# 2. Run everything — pulls image, starts service, runs all tests, generates reports
make run
```

That single command:

1. Pulls `infralightio/test-integration-api` from Docker Hub
2. Starts the service container and waits for it to be healthy
3. Runs the full functional test suite under `tests/` (pytest collection; count grows as cases are added)
4. Runs the load test (see **Load test (Locust)** section below — **Docker** vs local **`make load`** differ)
5. Writes two HTML reports to `./reports/`

---

## Project Structure

```
test-integration/
│
├── config/
│   └── settings.py              # All configuration — env-driven, zero hardcoded values
│
├── api/
│   ├── client.py                # Authenticated HTTP client wrapper
│   └── helpers.py               # Domain-specific clients: IntegrationClient, AssetClient
│
├── tests/
│   ├── test_auth.py             # Authentication and authorization (11 tests)
│   ├── test_contract.py         # OpenAPI schema and response contracts (26 tests)
│   ├── test_crud.py             # Full Create→Read→Update→Delete lifecycle (37 tests)
│   ├── test_negative.py         # Edge cases, malformed input, security probes (22 tests)
│   └── test_tenant_segregation.py  # Multi-tenant data isolation (19 tests)
│
├── load_tests/
│   └── locustfile.py            # Locust load test — ≥1000 req/min validation
│
├── conftest.py                  # Shared pytest fixtures (clients, resources, OpenAPI spec)
├── pytest.ini                   # Test markers and logging config
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Orchestrates service + test runner
├── Dockerfile.tests             # Test runner container image
├── Makefile                     # Entry points: run / test / load / clean
├── BUG_REPORT.md               # Failure triage guide (timeouts, contract vs API, pagination, etc.)
└── reports/                     # Generated HTML reports (created at runtime)
```

---

## API Under Test

**Base URL:** `http://localhost:8080`  
**Base path:** `/api/v1`  
**Auth:** HTTP Basic Authentication  
**Swagger UI:** `http://localhost:8080/swagger/index.html`  
**OpenAPI JSON:** `http://localhost:8080/swagger/doc.json`

**Pre-populated test users:**


| Username | Password  |
| -------- | --------- |
| `test1`  | `test123` |
| `test2`  | `test456` |


**Resources:**

```
Integrations
  POST   /api/v1/integrations           Create    body: {name, type}
  GET    /api/v1/integrations           List      query: page, limit
  GET    /api/v1/integrations/{id}      Get by ID
  PUT    /api/v1/integrations           Update    body: {id, name}  ← id is in the body
  DELETE /api/v1/integrations/{id}      Delete    → 200

Assets
  POST   /api/v1/assets                 Create    body: {name, description, integration_id}
  GET    /api/v1/assets                 List      query: integrationId (required!), page, limit
  GET    /api/v1/assets/{id}            Get by ID
  PATCH  /api/v1/assets                 Update    body: {id, name, description}  ← id is in the body
  DELETE /api/v1/assets/{id}            Delete    → 204
```

**Structural quirks worth noting:**

- `PUT /integrations` and `PATCH /assets` pass the resource `id` in the **request body**, not in the URL path — unlike typical REST conventions.
- `GET /assets` requires `integrationId` as a **mandatory** query parameter. A bare `GET /assets` with no query string returns `400`.
- `DELETE /integrations` returns **200**, while `DELETE /assets` returns **204** — two different success codes on the same API.

---

## Test Suite Breakdown

### `test_auth.py` — 11 tests

Verifies that Basic Authentication is correctly enforced across all endpoints.

- Both pre-populated users authenticate successfully
- No credentials → `401` on all protected endpoints
- Wrong password, wrong username, empty fields → `401`
- `WWW-Authenticate` header present on `401` responses (RFC 7617)
- **Bug candidates:** `GET /integrations` and `POST /integrations` are missing `401` from their declared spec responses — tests check whether the service actually enforces auth regardless

### `test_contract.py` — 26 tests

Validates that every live response conforms to the schemas declared in the OpenAPI spec.

- Spec document is reachable, valid JSON, and contains both resource paths
- Base path is correctly declared as `/api/v1`
- `Integration` response shape: `{id, name, tenant_id, type}`
- `Asset` response shape: `{id, name, description, integration_id, tenant_id}`
- Error response shape: `{code, message}` — and the `code` field matches the HTTP status code
- `DELETE /integrations/{id}` returns `200` (not `204`)
- `DELETE /assets/{id}` returns `204`
- `POST /assets` returns `409 Conflict` on duplicate name within the same integration
- **Spec bug tests:** flags the two missing `401` declarations as documentation failures

### `test_crud.py` — 37 tests

Exercises the complete lifecycle for both resources.

**Integrations:** create with all fields, missing fields, get by ID, list with pagination, update via body-id, delete, double-delete, cascading deletion checks

**Assets:** create with all fields, duplicate name → `409`, same name across different integrations (allowed), create under nonexistent integration, list by `integrationId`, missing `integrationId` → `400`, pagination, update name/description via body-id, delete, double-delete, cascade after parent integration is deleted

### `test_negative.py` — 22 tests

Ensures the service handles unexpected and malicious input gracefully — always `4xx`, never `5xx`.

- Malformed JSON body → `4xx`
- Null body, array body to object endpoints → `4xx`
- Path traversal: `../../etc/passwd` in ID fields
- XSS attempt: `<script>alert(1)</script>` in ID fields
- SQL injection: `' OR '1'='1` in ID fields
- Very long IDs (500 characters)
- Negative page numbers, zero limit, non-integer pagination values
- Wrong HTTP methods on collection endpoints
- Error body format validation: `code` and `message` fields always present

### `test_tenant_segregation.py` — 19 tests

The most critical category for a multi-tenant service. A failure here represents a **data breach**.

- `user1` and `user2` have different `tenant_id` values
- All resources created by the same user share a consistent `tenant_id`
- Asset `tenant_id` matches its parent integration's `tenant_id`
- List endpoints return only the requesting user's resources
- `GET /integrations/{id}` with another user's ID → `403` or `404`
- `PUT /integrations` with another user's ID in body → `403` or `404`
- `DELETE /integrations/{id}` targeting another user's resource → `403` or `404`
- `GET /assets?integrationId=<other_user's_id>` → `403` or `404`
- `GET /assets/{id}` for another user's asset → `403` or `404`
- `PATCH /assets` and `DELETE /assets/{id}` across tenant boundaries → `403` or `404`

### `load_tests/locustfile.py` — Load test

Exercises the service under **Locust** with **two tenant user classes**. Each user runs an **ordered bootstrap** first (≥10 integrations: create → list → get each → delete all but one → PUT; then ≥10 assets on the **reserved** integration: create → list → get each → delete all but one → PATCH), then **steady-state** traffic that only uses the **reserved** integration and asset (no steady-state deletes of those).

**How load is invoked (two different defaults):**

| Command | Users | Spawn rate | Duration | Host |
| --------|-------|------------|----------|------|
| **`make run`** (via `docker-compose.yml`) | 50 | 10/s | 60s | `http://api:8080` in container |
| **`make load`** (local Makefile) | **1000** | 10/s | 60s | `http://localhost:8080` |

Tune `docker-compose.yml` or the `Makefile` if you need gentler or heavier load.

**Pass/fail thresholds (enforced automatically):**


| Metric              | Threshold             |
| ------------------- | --------------------- |
| Error rate          | < 1%                  |
| p95 response time   | < 1000 ms             |
| Requests per second | ≥ 17 (= 1000 req/min) |


The load test exits with a non-zero code if any threshold is breached, making it CI-friendly.

---

## Known Bugs Targeted

The API is described as having intentional bugs. The suite is written to surface them:


| #   | Location | Bug                                                            | Test                                                        |
| --- | -------- | -------------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | Spec     | `GET /integrations` missing `401` in declared responses        | `test_spec_bug_list_integrations_missing_401`               |
| 2   | Spec     | `POST /integrations` missing `401` in declared responses       | `test_spec_bug_post_integrations_missing_401`               |
| 3   | Runtime  | `GET /integrations` may be accessible without credentials      | `test_bug_list_integrations_requires_auth`                  |
| 4   | Runtime  | `POST /integrations` may be accessible without credentials     | `test_bug_create_integration_requires_auth`                 |
| 5   | Runtime  | Cross-tenant asset list via `?integrationId=<other_user's_id>` | `test_user1_cannot_list_assets_under_user2_integration`     |
| 6   | Runtime  | `DELETE /integrations` cascading to orphaned assets            | `test_deleting_integration_cascades_to_assets`              |
| 7   | Runtime  | Duplicate asset names within same integration → `409`          | `test_duplicate_asset_name_in_same_integration_returns_409` |


When a test targeting a known bug fails, the assertion message explicitly labels it as a **BUG** and describes the expected vs actual behaviour.

---

## Running the Tests

### Option A — Full run via Docker (recommended)

```bash
make run
```

No Python installation needed. Handles everything end to end.

### Option B — Functional tests only (service already running)

```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run all functional tests
make test

# Or run a specific category
pytest tests/ -m auth
pytest tests/ -m contract
pytest tests/ -m tenant
pytest tests/ -m crud
pytest tests/ -m negative
```

### Option C — Load test only (service already running)

```bash
make load
```

`make load` uses the parameters in the **Makefile** (currently **1000** users, **10**/s spawn rate — adjust there if your machine or API cannot sustain it). For the lighter profile used inside **`make run`**, see `docker-compose.yml` (**50** users).

Or with the Locust web UI for live monitoring:

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8080
# Open http://localhost:8089 in your browser
```

### Cleanup

```bash
make clean   # stops containers, removes reports
```

---

## Configuration

Settings are centralised in `config/settings.py`. **`BASE_URL`** is the main environment override; other values below use **defaults in code** unless you edit the file.


| Variable   | Default                 | Description  |
| ---------- | ----------------------- | ------------ |
| `BASE_URL` | `http://localhost:8080` | API origin (scheme + host + port); API paths still use `api_base` below |

**Code-only defaults** (edit `config/settings.py` if needed):

- `api_base` — `"/api/v1"` (prefix for all REST calls).
- `request_timeout` — seconds for each `requests` call (default **10**).
- `HTTP_POST_CREATE_OK` — `frozenset((200, 201))` so successful **POST creates** pass whether the service returns **200 OK** or **201 Created** (test-harness tolerance, not an API change).

To run against a different host or port:

```bash
BASE_URL=http://staging.example.com:9090 pytest tests/ -v
```

The docker-compose setup automatically sets `BASE_URL=http://api:8080` for the test runner container.

---

## Reports

After a run, two self-contained HTML files are written to `./reports/`:


| File                       | Contents                                                                                                                      |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `reports/report.html`      | Pytest HTML report — full `tests/` run: pass/fail/skip, durations, assertion detail on failures |
| `reports/load_report.html` | Locust HTML report — RPS chart, response time percentiles, per-endpoint breakdown, error summary                              |


Open either file directly in any browser — no server needed.

---

## Design Decisions

**POST create status codes.** Some stacks return **201 Created** for `POST /integrations` and `POST /assets`; others return **200**. The suite accepts either via `HTTP_POST_CREATE_OK` in `config/settings.py`.

**No hardcoded URLs in tests.** URLs are built from `BASE_URL` + `api_base` via `APIClient` / `settings.url()`.

**Domain-specific clients.** `IntegrationClient` and `AssetClient` in `api/helpers.py` mirror the actual API surface exactly, including the non-standard id-in-body pattern for `PUT /integrations` and `PATCH /assets`. Tests call these helpers, not raw HTTP verbs, so an endpoint change requires one fix in one place.

**Fixtures handle teardown.** Every test that creates a resource uses a pytest fixture that deletes it afterwards. Tests never leave dirty state, can run in any order, and are safe to run in parallel.

**Tenant segregation is domain-accurate.** The cross-tenant tests don't just check `GET /resource/{other_user's_id}`. They also test `GET /assets?integrationId=<other_user's_integration_id>`, which is the actual attack vector on this specific API design.

**Bug tests are first-class.** Tests targeting known spec bugs are not skipped or marked xfail — they run and fail loudly, with assertion messages that explicitly label the finding as a bug and explain the expected behaviour. This is intentional: a failing test is a bug report.

**Self-contained execution.** `make run` is the only command a reviewer needs. It requires no prior setup beyond having Docker installed.

---

## Extending the Suite

**Add a new endpoint:** Create a method on `IntegrationClient` or `AssetClient` in `api/helpers.py`, then write tests in the appropriate `tests/test_*.py` file. Fixtures in `conftest.py` are available automatically.

**Add a new resource:** Add a new `XyzClient` class in `api/helpers.py`, add corresponding fixtures to `conftest.py`, and create a `tests/test_xyz_*.py` file.

**Change the target environment:** Set `BASE_URL` — no code changes needed.

**Add a new pytest marker:** Declare it in `pytest.ini` under `markers`, then tag tests with `@pytest.mark.your_marker`.