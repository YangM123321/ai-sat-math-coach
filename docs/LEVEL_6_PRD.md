# Level 6 Product Requirements Document — Evaluation and Improvement Loop

## Executive Summary
Level 6 turns AI SAT Math Coach from a collection of AI features into a measurable product system. It records offline evaluation runs, production quality metrics, and controlled improvement experiments so changes to prompts, rules, models, and recommendation algorithms can be compared before promotion.

## Product Vision
Every material system change should be supported by evidence rather than intuition.

## Business Goals
- Reduce regressions in diagnostic, tutoring, mastery, learning-plan, and dashboard behavior.
- Measure quality, latency, cost, and user outcomes over time.
- Make model and prompt changes auditable.
- Create interview-ready evidence of responsible AI lifecycle engineering.

## Users
- AI engineers evaluating model and prompt versions.
- Product managers reviewing outcome and cost tradeoffs.
- Educators validating explanation quality.
- Engineering managers approving releases.

## Core User Stories
- As an AI engineer, I can run a labeled evaluation dataset against a system version.
- As a product manager, I can inspect pass rate, score, latency, and cost.
- As an engineer, I can store periodic quality metrics.
- As a team, we can register and complete controlled experiments.
- As a release owner, I can promote a treatment only when it improves the primary metric without violating guardrails.

## Functional Requirements
1. Create and persist evaluation runs with case-level results.
2. Compare expected and actual structured outputs.
3. Calculate pass rate, mean score, mean latency, and total cost.
4. Store version identifiers and evaluation thresholds.
5. Retrieve historical runs by component.
6. Store idempotent metric snapshots by component, metric, and period.
7. Create improvement experiments with control and treatment versions.
8. Complete experiments with a deterministic decision.
9. Preserve failure reasons and case-level evidence.

## Non-Functional Requirements
- Strict typed contracts.
- Immutable evaluation case results.
- Versioned datasets and system implementations.
- Idempotent metric periods.
- No automatic production rollout.
- Auditable decisions.
- Full regression test coverage for prior levels.

## Acceptance Criteria
- A two-case run returns correct aggregate metrics.
- Failed cases retain a human-readable reason.
- Reposting the same metric period updates rather than duplicates it.
- A treatment is promoted only when its primary metric improves and no guardrail is violated.
- Missing resources return typed 404 errors.
- Migrations upgrade and downgrade cleanly.

## Edge Cases
- Empty datasets are rejected.
- Missing scores are allowed when exact structured comparison is sufficient.
- Zero control metrics do not produce invalid relative-lift calculations.
- Guardrail violations force rollback regardless of primary-metric lift.
- Repeated case IDs in one run are rejected by the database constraint.

## Risks
- Evaluation datasets may not represent real users.
- Simple exact matching can under-credit semantically valid outputs.
- Small experiments may be statistically inconclusive.
- Outcome metrics can be gamed if guardrails are weak.

## V1 Scope
Offline structured evaluation, metric snapshots, and deterministic experiment decisions.

## Out of Scope
Automated traffic routing, statistical significance testing, production model deployment, real-time telemetry ingestion, and automatic prompt optimization.
