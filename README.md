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
| `SECRET_KEY` | Set, at least 32 characters, not a known placeholder (e.g. `changeme`). Reserved for future token signing (Phase 1.5 authentication); enforced now so the bar is never lowered later. |
| `DATABASE_URL` | Points at a server database (not SQLite) and explicitly requests an encrypted connection: `sslmode=require`/`verify-ca`/`verify-full`, or an equivalent driver-supported TLS parameter (e.g. `ssl=true`, `tls=1`), e.g. `postgresql+psycopg://user:pass@host:5432/db?sslmode=require`. `sslmode=disable`/`allow`/`prefer` do not count as explicit (`prefer` silently allows an unencrypted fallback). |
| `CORS_ALLOWED_ORIGINS` | Non-empty, comma-separated list of explicit origins; must not contain `*`. |
| `TRUSTED_HOSTS` | Non-empty, comma-separated list of explicit hostnames; must not contain `*`. |
| `DEBUG` | Must be `false`. |
| `API_KEY` | If `REQUIRE_API_KEY=true`, must be at least 16 characters and not a known placeholder. |

**Staging is intentionally not enforced by this validation.** `ENVIRONMENT=staging` behaves like `development`/`test` for these checks in this baseline — staging is expected to *resemble* production operationally (see `docs/ARCHITECTURE.md`), but tightening its own startup validation is deferred to a later PR rather than bundled into this configuration baseline.

`CORS_ALLOWED_ORIGINS` and `TRUSTED_HOSTS` accept a comma-separated string (e.g. `CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com`) rather than requiring JSON-array syntax.

This PR adds the settings and their validation only — no CORS or trusted-host middleware is wired into the application yet; that is deferred to a later, separately-reviewed PR.

## Tests

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

This runs the full application test suite against SQLite, matching the CI `test` job exactly.

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
