# Level 1 Architecture

## Context Diagram

```mermaid
flowchart LR
    Student[Student Client] --> API[FastAPI Diagnostic API]
    Teacher[Teacher/Tutor Client] --> API
    API --> DB[(PostgreSQL)]
    API --> Provider[Diagnostic Provider]
    API --> OCR[Math OCR Provider]
    API --> Logs[Structured Logs / Metrics]
```

## Component Diagram

```mermaid
flowchart TD
    Route[API Routes] --> Auth[API-Key/Auth Dependency]
    Route --> Service[Diagnostic Service]
    Service --> Grader[Deterministic Grading]
    Service --> DiagnosticProvider[Diagnostic Provider Interface]
    Service --> Confidence[Confidence Service]
    Service --> Repository[Repository]
    Repository --> SQLA[SQLAlchemy]
    SQLA --> PG[(PostgreSQL)]
    DiagnosticProvider --> Prompt[Versioned Prompt]
    DiagnosticProvider --> Schema[Pydantic Structured Output]
```

## Create-Diagnostic Sequence

```mermaid
sequenceDiagram
    actor C as Client
    participant A as FastAPI
    participant G as Grading Service
    participant P as Diagnostic Provider
    participant CFS as Confidence Service
    participant R as Repository
    participant D as PostgreSQL

    C->>A: POST /api/v1/diagnostics
    A->>A: Authenticate + validate
    A->>G: Compare answers
    G-->>A: deterministic_correct
    A->>R: Create attempt
    R->>D: INSERT attempt
    A->>P: Diagnose structured reasoning
    P-->>A: Validated provider output
    A->>CFS: Calculate confidence/review
    CFS-->>A: Decision + breakdown
    A->>R: Save diagnostic
    R->>D: INSERT diagnostic
    A-->>C: 201 DiagnosticResponse
```

## Design Decisions

- Deterministic grading is authoritative for final-answer correctness because it is cheaper and more reproducible than LLM grading.
- Provider output uses strict Pydantic validation to keep prose from leaking into machine-consumed fields.
- Repository boundaries isolate persistence from business logic.
- Confidence is calculated outside the model so review behavior is auditable.
- Prompt and model versions are persisted for reproducibility.
- OCR fails closed in V1 to avoid pretending that unreliable handwriting extraction is production-ready.

## Deployment Architecture

```mermaid
flowchart LR
    User --> LB[HTTPS Load Balancer]
    LB --> API1[FastAPI Container]
    LB --> API2[FastAPI Container]
    API1 --> PG[(Managed PostgreSQL)]
    API2 --> PG
    API1 --> Secret[Secret Manager]
    API2 --> Secret
    API1 --> Obs[Logs Metrics Traces]
    API2 --> Obs
    API1 --> AI[External AI Provider]
    API2 --> AI
```
