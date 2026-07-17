# Level 3 Product Requirements Document — Personalized Learning Engine

## Executive Summary

Level 3 converts the Student Knowledge Model into an actionable, time-bounded SAT Math study plan. It selects the highest-value skills, accounts for prerequisite gaps and uncertainty, schedules daily activities, explains each recommendation, and records progress against the exact plan shown to the student.

## Product Vision

Every student should receive a practical next step—not merely a mastery dashboard. The engine should answer: **What should I study today, why, and for how long?**

## Business Goals

- Increase completion of recommended practice.
- Reduce wasted practice on already-mastered skills.
- Differentiate the product from generic question generators.
- Create a measurable bridge between diagnosis and score improvement.
- Provide an auditable recommendation system suitable for educator review.

## Primary Users

- SAT Math students studying independently.
- Tutors assigning targeted work.
- Parents monitoring whether study time is focused.
- Future teacher dashboards consuming plan and completion data.

## User Stories

- As a student, I want a seven-day plan based on my weaknesses so I know what to do next.
- As a student, I want each recommendation explained so the plan feels credible.
- As a tutor, I want a student’s old plans preserved so I can review changes over time.
- As a system, I want prerequisite gaps prioritized before dependent concepts.
- As a product analyst, I want algorithm and profile snapshots stored for evaluation.

## Functional Requirements

1. Generate a plan from the current skill catalog and mastery profile.
2. Support configurable start date, duration, daily minutes, target score, and exam date.
3. Rank skills using mastery, confidence, unseen-skill status, and prerequisite relevance.
4. Create one scheduled activity per day in V1.
5. Assign activity type, difficulty, time, question count, priority, and rationale.
6. Persist the profile snapshot and algorithm version.
7. Supersede, rather than delete, an existing active plan.
8. Retrieve a plan and the student’s active plan.
9. Update activity progress and completion counts.

## Non-Functional Requirements

- Deterministic output for the same persisted inputs and configuration.
- P95 generation target below 500 ms for a V1 catalog under 500 skills.
- Idempotent data integrity through one active plan version at a time.
- Explainable recommendations with no hidden LLM dependency.
- Full type validation and migration-backed persistence.

## Acceptance Criteria

- A student with at least one configured skill can receive a persisted plan.
- A seven-day request returns seven dated activities.
- Weak and uncertain skills rank above mastered, high-confidence skills.
- A second plan supersedes the first and increments version.
- Activity completion cannot report more correct answers than completed answers.
- An empty skill catalog returns a typed conflict response.

## Edge Cases

- No mastery evidence: use a neutral mastery score and high uncertainty.
- Fewer skills than days: rotate focus skills across days.
- No skill catalog: reject generation rather than fabricate content.
- Exam date before start date: validation error.
- Student requests a new plan midweek: preserve the old version.
- Missing prerequisite relationships: continue without prerequisite bonus.

## Risks and Mitigations

- **False precision:** Store transparent scores and rationale; do not claim causal effectiveness.
- **Over-prioritizing unseen skills:** Cap unseen bonus and allow later calibration.
- **Stale mastery:** Store generation snapshot and regenerate explicitly.
- **Plan fatigue:** Limit V1 to one bounded activity per day.
- **Algorithm bias:** Evaluate completion and learning outcomes by skill and student segment.

## Success Metrics

- Plan generation success rate.
- Activity completion rate.
- Seven-day plan completion rate.
- Accuracy improvement on targeted skills.
- Percentage of recommendations rated helpful.
- Regeneration rate and reason.

## V1 Scope

Deterministic seven-day plan generation, explainable ranking, persistence, versioning, retrieval, and activity progress.

## Out of Scope

Question generation, live tutoring, notification delivery, calendar synchronization, reinforcement-learning policies, and proven SAT score prediction.

## Future Enhancements

Spaced repetition, availability calendars, goal optimization, content inventory matching, adaptive mid-plan changes, cohort experiments, and educator overrides.
