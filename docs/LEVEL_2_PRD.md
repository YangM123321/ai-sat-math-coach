# Level 2 Product Requirements Document — Student Knowledge Model

## Executive Summary

The Student Knowledge Model converts isolated diagnostic results into a persistent, explainable representation of what each learner appears to know. It records evidence over time, estimates mastery by SAT Math skill, exposes prerequisite relationships, and supplies Level 3 with the data required to generate personalized learning plans.

Level 2 is not a generic social graph and is not an opaque AI score. It is an auditable learner model whose state can be traced back to diagnostic and practice evidence.

## Product Vision

Give every student, tutor, and future recommendation engine a continuously updated answer to three questions:

1. What skills has the student demonstrated?
2. Where are the most important weaknesses?
3. How certain is the system about each estimate?

## Business Goals

- Increase personalization beyond one-question feedback.
- Create longitudinal data that supports subscription value and retention.
- Reduce tutor time spent manually identifying recurring weaknesses.
- Provide the foundation for personalized learning plans and progress dashboards.
- Differentiate the product from general-purpose chatbots.

## Problem Statement

A diagnostic result is valuable for one question, but it does not answer whether the error is recurring, whether prerequisite gaps are involved, or whether the student is improving. Without a persistent knowledge model, recommendations remain generic and progress claims are difficult to defend.

## Users

### Student
Needs a clear view of strengths, weaknesses, and progress without being labeled by a single mistake.

### Tutor or Teacher
Needs evidence-backed mastery estimates and the ability to understand why a skill changed.

### Parent
Needs a simplified progress summary and confidence that recommendations are based on actual work.

### Internal Learning Engine
Needs normalized skill mastery, confidence, prerequisites, and recency data.

## User Stories

- As a student, I can see my strongest and weakest SAT Math skills.
- As a student, one wrong answer does not permanently classify me as weak.
- As a tutor, I can inspect the evidence that changed a mastery score.
- As a curriculum administrator, I can define skill and prerequisite relationships.
- As the learning engine, I can retrieve a structured profile for recommendations.
- As an auditor, I can rebuild current mastery from immutable events.

## User Journey

1. A diagnostic is completed in Level 1.
2. The result identifies an affected skill and confidence.
3. Level 2 records a mastery event.
4. The mastery estimator updates the student-skill state.
5. The profile API ranks strengths and weaknesses.
6. The graph API combines curriculum relationships with student mastery.
7. Level 3 consumes this profile to select learning activities.

## Functional Requirements

- Maintain a canonical SAT Math skill catalog.
- Support hierarchical and prerequisite relationships.
- Store one current mastery state per student and skill.
- Store immutable mastery events with source identifiers.
- Prevent duplicate application of the same evidence.
- Weight evidence by correctness, difficulty, and diagnostic confidence.
- Return mastery score, mastery status, confidence, attempts, and recency.
- Return strongest and weakest skills.
- Return graph-shaped nodes and edges without requiring a graph database.
- Support future teacher overrides through the evidence contract.

## Non-Functional Requirements

- Mastery updates must be transactional and idempotent.
- Scores must remain between 0 and 1.
- Every state change must have an evidence event.
- Profile reads should complete within 300 ms at portfolio scale.
- APIs must be documented in OpenAPI.
- Existing Level 1 endpoints and tests must remain operational.

## Acceptance Criteria

- A skill can be created and retrieved.
- A relationship cannot reference a missing skill or itself.
- Correct evidence raises mastery; incorrect evidence lowers it.
- Replaying the same source does not alter mastery twice.
- Missing skills return an explicit error.
- A student profile returns mastery and confidence per skill.
- The graph endpoint returns curriculum edges and student-specific node state.
- Alembic can upgrade and downgrade Level 2 tables.
- The complete test suite passes.

## Edge Cases

- No student evidence: return an empty profile, not invented mastery.
- One attempt: expose low confidence even when the score moves.
- Duplicate webhook or retry: return the existing event.
- Ambiguous diagnosis: reduce evidence weight.
- Skill renamed: preserve stable code and event history.
- Removed curriculum skill: mark inactive rather than delete historical evidence.
- Conflicting simultaneous updates: enforce database uniqueness and transactional handling.

## Risks and Mitigations

- **False precision:** show both mastery and confidence.
- **Overreaction to one attempt:** use bounded incremental updates.
- **Taxonomy drift:** use stable skill codes and version future catalogs.
- **Opaque scores:** persist previous score, delta, weight, and source.
- **Premature graph infrastructure:** expose graph semantics over PostgreSQL first.

## Success Metrics

- Duplicate-event rate blocked successfully: 100%.
- Mastery events with traceable source: 100%.
- Profile API success rate: above 99% in test environment.
- Human agreement that top weakness is reasonable on evaluation set: target 80% for V1.
- Reduction in repeated errors after Level 3 integration: future outcome metric.

## V1 Scope

- Skill catalog
- Skill hierarchy and prerequisite relationships
- Student-skill mastery state
- Immutable evidence events
- Transparent incremental mastery update
- Profile and graph APIs
- Seed script
- Alembic migration
- Unit and integration tests

## Out of Scope

- Bayesian Knowledge Tracing
- Deep Knowledge Tracing
- Neo4j
- Cross-student collaborative models
- Teacher dashboard UI
- Automated learning-plan generation
- Psychometric score claims

## Future Enhancements

- Calibrated Bayesian mastery estimator
- Time decay and spaced-repetition strength
- Teacher review and override workflow
- Curriculum versioning
- Cohort analytics
- What-if simulations for recommendation ranking
