# AI SAT Math Coach — Production Portfolio Project (Levels 1–6)

A production-style portfolio milestone implementing the first core layer of AI SAT Math Coach.

## Delivered artifacts

- `docs/LEVEL_1_PRD.md` — formal product requirements
- `docs/LEVEL_1_ENGINEERING_SPEC.md` — detailed engineering specification
- `docs/ARCHITECTURE.md` — component, sequence, and deployment diagrams
- `docs/API_CONTRACTS.md` — request, response, and error contracts
- `docs/EVALUATION_PLAN.md` — labeled dataset and evaluation strategy
- `docs/adr/` — architecture decision records
- `app/` — runnable FastAPI implementation
- `alembic/` — reproducible database migration
- `tests/` — service and API tests
- `.github/workflows/ci.yml` — CI with coverage gate
- `Dockerfile` and `docker-compose.yml` — local container deployment

## Implemented V1

- Typed question and work submission
- Deterministic numeric/text answer grading
- Strict diagnostic taxonomy and Pydantic structured output
- Rule-based local provider for reproducible demos and tests
- Transparent confidence scoring and human-review rules
- SQLAlchemy persistence for attempts, diagnoses, and reviewer feedback
- Diagnostic retrieval and student history
- Versioned prompts and provider metadata
- Optional API-key protection
- Request IDs and privacy-safe HTTP logging
- OpenAPI documentation
- Alembic migrations
- Dockerized PostgreSQL deployment
- Automated CI and test coverage threshold

## Deliberately not misrepresented as complete

The included rule-based provider is a local development implementation, not a claim of production diagnostic intelligence. A vendor-backed LLM adapter and production mathematical OCR remain explicit integration work. The architecture supports them without changing domain contracts.

## Quick Start

**Requirements:** Python 3.12 (the version this project is developed and tested against — see `.github/workflows/ci.yml`).

Run every command below from the repository root.

```bash
python -m venv .venv

# Activate the virtual environment (pick the line for your shell):
source .venv/bin/activate          # macOS / Linux
source .venv/Scripts/activate      # Windows, Git Bash
.venv\Scripts\activate             # Windows, cmd.exe or PowerShell

pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

### Why run `alembic upgrade head` if SQLite can create tables automatically?

For local SQLite development, `app/main.py` also calls `Base.metadata.create_all()` on startup as a convenience, so the app will still run even if this step is skipped. Running `alembic upgrade head` anyway is still recommended, because it's the only local way to actually exercise the real migration chain — the same chain that PostgreSQL (the production-representative database, see `docker-compose.yml`) relies on exclusively, with no such convenience fallback. Skipping this step locally means migrations go unverified until they're run against PostgreSQL.

## Configuration

Configuration is centralized in `app/core/config.py` as a typed, validated `Settings` object (`pydantic-settings`), loaded from environment variables or a local `.env` file. `ENVIRONMENT` selects one of four values: `development`, `test`, `staging`, `production`.

`development` and `test` require no additional configuration beyond `.env.example` — every new setting below has a permissive default so the existing local workflow is unaffected.

### Production startup validation

When `ENVIRONMENT=production`, `Settings` refuses to construct (the app fails to start, with every violation listed at once) unless all of the following hold:

| Setting | Production requirement |
|---|---|
| `SECRET_KEY` | Set, at least 32 characters, not a known placeholder (e.g. `changeme`). Signs JWT access tokens (see Authentication, below). |
| `DATABASE_URL` | Points at a server database (not SQLite) and explicitly requests an encrypted connection: `sslmode=require`/`verify-ca`/`verify-full`, or an equivalent driver-supported TLS parameter (e.g. `ssl=true`, `tls=1`), e.g. `postgresql+psycopg://user:pass@host:5432/db?sslmode=require`. `sslmode=disable`/`allow`/`prefer` do not count as explicit (`prefer` silently allows an unencrypted fallback). |
| `CORS_ALLOWED_ORIGINS` | Non-empty, comma-separated list of explicit origins; must not contain `*`. |
| `TRUSTED_HOSTS` | Non-empty, comma-separated list of explicit hostnames; must not contain `*`. |
| `DEBUG` | Must be `false`. |
| `API_KEY` | If `REQUIRE_API_KEY=true`, must be at least 16 characters and not a known placeholder. |
| `RATE_LIMIT_ENABLED` | Must be `true`. Protects `/api/v1/auth/*` from credential-stuffing/brute-force abuse (see Rate Limiting, below). |

**Staging is intentionally not enforced by this validation.** `ENVIRONMENT=staging` behaves like `development`/`test` for these checks in this baseline — staging is expected to *resemble* production operationally (see `docs/ARCHITECTURE.md`), but tightening its own startup validation is deferred to a later PR rather than bundled into this configuration baseline.

`CORS_ALLOWED_ORIGINS` and `TRUSTED_HOSTS` accept a comma-separated string (e.g. `CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com`) rather than requiring JSON-array syntax.

This PR adds the settings and their validation only — no CORS or trusted-host middleware is wired into the application yet; that is deferred to a later, separately-reviewed PR.

## Tests

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

This runs the full application test suite against SQLite, matching the CI `test` job exactly.

Each pytest **session** (process) uses its own SQLite database file, created fresh in a pytest-managed temporary directory outside the repository (`tests/conftest.py`'s `pytest_configure`/`pytest_unconfigure`) — never a fixed path in the repo root. This means two full test-suite runs can be started at the same time (e.g. two terminals, or CI matrix jobs) without one run's `drop_all`/`create_all` interfering with the other's. Within a session, tables are still dropped and recreated before every individual test, exactly as before.

A separate set of PostgreSQL-only migration reconciliation tests (`tests/test_migration_reconciliation.py`) is skipped automatically unless `MIGRATION_TEST_DATABASE_URL` points at a reachable PostgreSQL instance:

```bash
MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://sat:sat@localhost:5432/sat_coach \
    pytest tests/test_migration_reconciliation.py -v
```

## Docker

### Build and start

```bash
docker compose up -d --build
```

This builds the API image, starts PostgreSQL, waits for it to become healthy, runs `alembic upgrade head` inside the API container, then starts `uvicorn`. No `.env` file is required — the defaults below apply automatically.

### Check status

```bash
docker compose ps
```

Both `api` and `db` should show as healthy (`db` uses `pg_isready`; `api` polls its own `/health` endpoint).

### Verify it's working

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Swagger UI: `http://localhost:8000/docs`

### View logs

```bash
docker compose logs -f api
docker compose logs -f db
```

### Stop

```bash
docker compose down
```

Stops and removes the containers but **preserves** the PostgreSQL data in the named `postgres_data` volume — starting the stack again with `docker compose up -d --build` will see the same data.

```bash
docker compose down -v
```

Same as above, but also **deletes** the `postgres_data` volume — the next `up` starts from a completely empty database.

### Default ports

| Service | Port | Purpose |
|---|---|---|
| `api` | `8000` | FastAPI application |
| `db` | `5432` | PostgreSQL, published to the host |

### Port 5432 conflicts

If you already have a local PostgreSQL installation running on your machine, it may already be using port `5432`. Docker Compose can still report `db` as started and healthy in this situation — the healthcheck runs *inside* the container, not against the host port — but anything on your host trying to connect to `localhost:5432` (a GUI DB client, `psql`, etc.) may silently reach your existing local PostgreSQL instead of the container. The application itself is unaffected either way, since `api` always talks to the container over the internal Docker network (`db:5432`), never through the host-published port.

To avoid this, publish PostgreSQL on a different host port with `POSTGRES_PORT`:

```bash
POSTGRES_PORT=5433 docker compose up -d --build
```

PowerShell:

```powershell
$env:POSTGRES_PORT = "5433"
docker compose up -d --build
```

`api` continues to connect to `db:5432` internally regardless of `POSTGRES_PORT` — this only changes which host port reaches the container from outside Docker.

### Testing API-key protection in Docker

`REQUIRE_API_KEY` and `API_KEY` are read from your shell environment when present, defaulting to `REQUIRE_API_KEY=false` (open, matching local dev) if unset — no override file needed:

```bash
REQUIRE_API_KEY=true API_KEY=change-me docker compose up -d --build

curl http://localhost:8000/api/v1/skills                              # 401, no key
curl -H "x-api-key: change-me" http://localhost:8000/api/v1/skills    # 200
```

PowerShell:

```powershell
$env:REQUIRE_API_KEY = "true"
$env:API_KEY = "change-me"
docker compose up -d --build
```

`/health` and `/ready` remain public regardless of `REQUIRE_API_KEY`.

## Example

```bash
curl -X POST http://127.0.0.1:8000/api/v1/diagnostics \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "stu_001",
    "question": {
      "question_text": "If 2x + 5 = 17, what is x?",
      "correct_answer": "6",
      "domain": "algebra",
      "skill": "linear_equations"
    },
    "student_answer": "7",
    "work_text": "2x = 17 + 5, so 2x = 22 and x = 7"
  }'
```


## Level 2: Student Knowledge Model

Level 2 extends the diagnostic engine with a skill catalog, prerequisite relationships, immutable mastery evidence, student-skill mastery estimates, profile APIs, and a graph-shaped curriculum view.

Seed the development catalog after migrations:

```bash
python scripts/seed_sat_skills.py
```

Key endpoints:

- `POST /api/v1/skills`
- `POST /api/v1/skill-relationships`
- `POST /api/v1/mastery/evidence`
- `GET /api/v1/students/{student_id}/knowledge-profile`
- `GET /api/v1/students/{student_id}/knowledge-graph`

## Level 3 — Personalized Learning Engine

The cumulative repository now generates persistent, explainable learning plans from Level 2 mastery data.

```bash
curl -X POST http://localhost:8000/api/v1/learning-plans \
  -H 'Content-Type: application/json' \
  -d '{"student_id":"stu_001","daily_minutes":30,"duration_days":7}'
```

Level 3 adds plan versioning, profile snapshots, prerequisite-aware ranking, scheduled activities, and progress updates. See `docs/LEVEL_3_PRD.md` and `docs/LEVEL_3_ENGINEERING_SPEC.md`.


## Level 4 — AI Tutor
Adds persisted Socratic tutoring sessions, ordered messages, progressive hints, completion/reflection, feedback, and a provider abstraction. See `docs/LEVEL_4_PRD.md`.

## Level 5 — Teacher and Parent Dashboard

Level 5 adds role-aware student summaries, viewer overviews, actionable alerts, access grants, daily progress snapshots, and trend APIs. Dashboard metrics are deterministic and traceable to Levels 1–4; no raw student work or tutor transcript is exposed.

## Level 6 — Evaluation and Continuous Improvement Loop

Level 6 adds versioned offline evaluation runs, case-level expected/actual comparisons, quality metric snapshots, and controlled improvement experiments. It records quality, latency, cost, and guardrail-aware release decisions without automatically deploying unverified changes.

See `docs/LEVEL_6_PRD.md`, `docs/LEVEL_6_ENGINEERING_SPEC.md`, and `docs/LEVEL_6_API_EXAMPLES.md`.

## Identity Schema (Phase 1.5)

Adds the database identity foundation for authentication and future authorization work: a `users` table (unique email, password hash, role, active/disabled state, email-verification state, timestamps) and a `refresh_tokens` table (hashed token records with expiration and revocation tracking).

Authentication and authorization built on top of this schema are described below (Phase 1.5 PR 3 and PR 4). See `docs/security/THREAT_MODEL.md` for the security architecture this schema is designed against.

## Authentication (Phase 1.5 PR 3)

`/api/v1/auth` provides registration, login, token refresh, logout, and logout-all, built on the identity schema above. Registration is API-key-protected (no public sign-up surface yet); login/refresh/logout authenticate a different way per endpoint instead of the shared API key. Access is via short-lived JWT access tokens plus rotated, hashed refresh tokens; passwords are hashed with Argon2id.

## Authorization (Phase 1.5 PR 4)

Every domain route (diagnostics, knowledge/mastery, learning plans, tutor, dashboard, evaluation) now requires a valid access token and derives access from the authenticated caller — never from a caller-supplied `student_id`, `viewer_id`, or `role`. Policy: students have full access to their own records; teachers have read-only access to students they're explicitly assigned to (via the same access-grant relationship the dashboard already used); admins have full access. Evaluation and skill-catalog management are admin-only.

See `docs/security/THREAT_MODEL.md` (T6/T7) for the authorization design and residual scope, and `app/services/authorization_service.py` for the implementation.

Not yet implemented: password reset, email verification, MFA, OAuth/social login, rate limiting on login/refresh, and route-level authorization on any endpoint outside `/api/v1/auth` itself.

See `docs/security/THREAT_MODEL.md` (T1/T4/T5) for the token/claim design, replay-detection behavior, and hashing rationale, and `app/services/auth_service.py`/`app/security/tokens.py` for the implementation.

## Security Audit Logging (Phase 1.5 PR 5)

Authentication outcomes, authorization denials, refresh-token reuse detection, and administrative access-grant creation are recorded to an append-only `audit_events` table via a centralized `AuditService`, kept separate from ordinary HTTP request logging. No password, password hash, raw JWT, or raw refresh token is ever stored.

See `docs/security/THREAT_MODEL.md` (T16) for the full event matrix, schema, and fail-open rationale, and `app/services/audit_service.py` for the implementation.

## Rate Limiting (Phase 1.5 PR 6)

`/api/v1/auth/*` is throttled by a sliding-window `RateLimiter`: login has its own per-IP and per-account (normalized email) tiers, the other four auth endpoints share a coarser per-IP tier. A tripped limit returns `429` with `Retry-After`/`X-RateLimit-*` headers and is recorded as an audit event. Off by default (`RATE_LIMIT_ENABLED=false`); production startup refuses to boot without it explicitly enabled.

See `docs/security/THREAT_MODEL.md` (T2) for the algorithm, configuration, fail-open rationale, and the Redis migration path, and `app/services/rate_limiter_service.py` for the implementation.

## CORS & Trusted Host Enforcement (Phase 1.5 PR 7)

`CORSMiddleware` and `TrustedHostMiddleware` (Starlette built-ins, `app/middleware/security.py`) are wired at runtime, consuming the same `CORS_ALLOWED_ORIGINS`/`TRUSTED_HOSTS` settings PR1 already validates — no new configuration, no duplicate validation logic.

**Empty-list semantics are deliberately asymmetric between the two settings** (they come from how each Starlette middleware treats an empty allowlist, not a choice made here):
- Empty `TRUSTED_HOSTS` → **allow all hosts.** An empty Python list is passed to `TrustedHostMiddleware` as `None`, which Starlette itself defaults to `["*"]` — matching today's already-open local-dev behavior.
- Empty `CORS_ALLOWED_ORIGINS` → **allow no browser origins.** No `Origin` ever receives `Access-Control-Allow-Origin`, so cross-origin browser JS is blocked; non-browser callers (curl, TestClient, mobile apps, server-to-server) are entirely unaffected, since CORS is enforced by the browser, not this API.

Both settings are already required to be non-empty and wildcard-free in production (PR1's startup validation, unchanged by this PR).

`allow_methods`/`allow_headers` are **explicit lists**, not `"*"`: `GET`/`POST`/`PATCH` (every method any route in this app actually declares) and `Authorization`/`Content-Type`/`X-API-Key`/`X-Request-ID` (every non-safelisted header a legitimate client needs). This API's surface is small and fully known, so there's no compatibility reason to fall back to a wildcard the way a large or evolving public API might need — see `app/middleware/security.py` for the derivation. `allow_credentials=False` throughout (Bearer-token auth, no cookies) and `www_redirect=False` (a 301 on a non-`GET` request is broken for most HTTP clients; this is an API, not a browser-navigated site).

See `docs/security/THREAT_MODEL.md` (T12) for the full behavior (including the built-in `400` responses for a mismatched `Host` header or disallowed CORS preflight, deliberately left as Starlette's default shape rather than wrapped in this app's JSON error envelope) and `app/middleware/security.py` for the implementation.
