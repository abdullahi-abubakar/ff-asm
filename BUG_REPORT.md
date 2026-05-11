# Bug & failure analysis report

This document summarises failure **categories** observed during integration test runs against the API at `http://localhost:8080`, together with **likely causes** and **recommended actions**. It is intended for developers and reviewers triaging test output (e.g. pytest HTML / terminal summary).

---

## Executive summary

Failures grouped into five themes:

| # | Theme | Primary nature |
|---|--------|----------------|
| 1 | **ReadTimeout (10s)** | Environment / availability / load — not always an application logic defect |
| 2 | **OpenAPI “spec bug” tests** | Test vs **current** spec — may indicate **outdated tests** if the spec was fixed |
| 3 | **500 on invalid input** | Server should return **4xx** for validation errors |
| 4 | **404 / error JSON shape** | Response body **`{ "error": ... }`** vs contract **`{ "code", "message" }`** |
| 5 | **Pagination query validation** | **500** or **200** where tests expect **4xx** or **strict validation** |

---

## Mitigation applied in this repository (test client)

### POST create returns **200** where **201 Created** would be more REST-typical

**Observation:** Some deployments respond with **200 OK** for successful **`POST /integrations`** and **`POST /assets`**; others correctly use **201 Created**. The test suite originally asserted **200 only**, which failed when the API returned **201**.

**Resolution (client / test side — not an API change):** Centralised acceptance of both success codes in `config/settings.py` as:

```python
HTTP_POST_CREATE_OK = frozenset((200, 201))
```

All create-path assertions that must treat “resource created successfully” use **`status_code in HTTP_POST_CREATE_OK`** (fixtures in `conftest.py`, auth create teardown, contract/CRUD tests, Locust bootstrap where applicable).

**Note:** A **`frozenset`** is used (immutable set of allowed codes). This does **not** change server behaviour; it only aligns the **harness** with either valid convention. The **ideal** API contract is still **201** for creation if the OpenAPI spec says so.

---

## 1. ReadTimeout (`read timeout=10`) — usually the largest bucket

### What it means

The HTTP client (`requests`) waited **10 seconds** for a complete response from `http://localhost:8080` and the deadline was exceeded. No response body is available for that call; the failure is a **client-side timeout**, not an HTTP status code from the API.

### Typical causes

- **Overload or contention**: Another process (e.g. **Locust**, manual load, parallel suites) is saturating the API or database.
- **Server stall**: Long GC pause, deadlock, or **blocked I/O** (e.g. DB lock, stuck external call).
- **Unhealthy process**: Application **hangs** on some code paths while still keeping the port open.
- **Cold start / resource limits**: First requests or container CPU/memory limits cause extreme latency (still often manifests as timeout at fixed 10s).

### Impact on pytest results

- **FAILED**: The test issued the request directly and `requests` raised `ReadTimeout`.
- **ERROR** (especially `::setup`): Shared fixtures such as **`integration_u1`** / **`asset_u1`** create resources via `POST` in **setup**. If that call times out, **every** test depending on that fixture may **error** without running assertions — producing a **burst of ERRORs** from a **single** underlying condition.

### Recommended actions

1. **Isolate the run**: Stop load generators (Locust, other scripts) while executing pytest.
2. **Stabilise the API**: Restart the service; confirm DB and dependencies are healthy.
3. **Narrow reproduction**:  
   `pytest tests/test_auth.py::TestValidCredentials::test_authenticated_user_can_create_integration -x -vv --tb=short`
4. **Raise timeout only after root-cause review**: If the API is legitimately slow under supported SLOs, configure a higher timeout (e.g. env-driven `REQUEST_TIMEOUT`) — avoid masking overload.

### Suggested owner

- **Ops / environment** first; **backend** if timeouts persist under light, exclusive load.

---

## 2. Spec “bug” tests — `test_spec_bug_*`

### Affected tests (examples)

- `test_spec_bug_list_integrations_missing_401`
- `test_spec_bug_post_integrations_missing_401`

### What they assert

The **Swagger/OpenAPI** document **does not** declare **401** on **`GET /integrations`** and **`POST /integrations`** respectively. The suite treats that omission as a **documentation defect** (auth failures should be documented).

### Why they “fail” after a spec update

If **401** was **added** to the spec for those operations, the assertion **fails** because the test still encodes the **old** expectation (“401 missing”). That is **test drift**, not necessarily a runtime API bug.

### Recommended actions

- If the spec is **correct** now: **remove**, **skip**, **invert** the assertions (e.g. require `"401"` in declared responses), or replace with a neutral contract check.
- If the spec is **still** missing 401: treat as **documentation defect**; fix the OpenAPI source, not only the tests.

### Suggested owner

- **API / docs** for the spec; **QA / test maintainers** if only tests need updating.

---

## 3. HTTP 500 where tests expect 4xx (validation)

### Examples (patterns)

- `POST /integrations` with **missing required field** (e.g. no `name`).
- `POST /integrations` with **empty JSON object** `{}`.

### Expected behaviour (per suite)

- **4xx** (typically **400 Bad Request** or validation-specific code), **not** **500 Internal Server Error**.

### Meaning

The server **mishandles** malformed or incomplete input — uncaught exception, missing validation layer, or intentional “buggy API” exercise. The **tests are aligned** with common REST expectations for client errors.

### Recommended actions

- Add or fix **input validation** and map validation failures to **4xx** with a stable error body.
- Add **server-side logging** for these paths to capture stack traces.

### Suggested owner

- **Backend** application team.

---

## 4. 404 / error response body — `code` + `message` vs `error`

### Example observed shape

```json
{"error": "integration not found"}
```

### What the suite expects

A structured error object matching **`HTTP_ERROR_SCHEMA`** (and related tests), typically including:

- **`code`** (e.g. numeric, aligned with HTTP status where applicable)
- **`message`** (human-readable explanation)

### Failure modes in pytest

- `Schema violation ... 'code' is a required property`
- `404 body missing 'code' field`
- `KeyError: 'code'` when tests read `body["code"]`

### Meaning

**Runtime JSON** and **documented contract** (and test schema) are **misaligned**. Clients and contract tests cannot rely on a single parsing rule.

### Recommended actions

- **Preferred**: Align the **API** with the published spec (`code` + `message`).
- **Transitional**: Extend tests/schema to accept **both** shapes during migration (document deprecation of `error`-only payloads).

### Suggested owner

- **Backend** for response contract; **QA** for temporary dual-shape tests if needed.

---

## 5. Pagination — negative and non-integer query parameters

### Observed mismatches (examples)

| Scenario | Observed (example) | Test expectation (summary) |
|----------|--------------------|----------------------------|
| `page=-1` | **500** | **200** (ignore) **or** **400** — **not** **500** |
| `page=-1` & `limit=0` | **200** | **400** or **422** (strict validation) |
| `page=abc` / `limit=abc` | **500** | **4xx** (client error for bad type) |

### Meaning

- **500** on bad query parameters indicates **server-side** failure (parse/cast not guarded).
- **200** on clearly invalid combinations may be **lenient** implementation; tests encoding **strict** validation will fail until product decides **ignore vs reject**.

### Recommended actions

- Define **product rules**: ignore invalid pagination vs return **400**.
- Implement consistent validation; **never** return **500** for predictable bad input unless documented as server bug.

### Suggested owner

- **Backend**; **Product** for ignore-vs-reject policy.

---

## Appendix — quick reference

### Timeout and fixture cascade

- **Config**: `config/settings.py` — `request_timeout` (default **10** s).
- **Fixtures**: `conftest.py` — `integration_u1`, `integration_u2`, `asset_u1`, `asset_u2` depend on successful `POST` in setup.

### Reproduce a single auth + create path

```bash
pytest tests/test_auth.py::TestValidCredentials::test_authenticated_user_can_create_integration \
  -x -vv --tb=short
```

---

## Document control

| Field | Value |
|-------|--------|
| Purpose | Triage guide for pytest failures vs `localhost:8080` |
| Scope | Timeouts, spec tests, validation, error JSON, pagination |
| Maintenance | Update when OpenAPI or error contract changes |
