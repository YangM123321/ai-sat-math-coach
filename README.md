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

```bash
docker compose up --build
```

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
