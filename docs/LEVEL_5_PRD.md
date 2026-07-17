# Level 5 Product Requirements Document — Teacher and Parent Dashboard

## Executive Summary
Level 5 converts the operational data produced by Levels 1–4 into concise, actionable views for teachers, tutors, and parents. The dashboard does not create new learning truth; it explains diagnostics, mastery, active plans, and tutoring engagement in language appropriate to each stakeholder.

## Product Vision
Give authorized adults a trustworthy answer to three questions: What has the student learned? Where is intervention needed? What should happen next?

## Business Goals
- Make student progress visible without requiring adults to inspect raw AI conversations.
- Support tutor and teacher intervention at scale.
- Increase parent trust through explainable evidence and progress trends.
- Create the B2B/B2C reporting layer required for future school and family subscriptions.

## Personas
- Teacher managing many students and limited intervention time.
- Parent seeking understandable progress information.
- Tutor preparing for the next session.
- Administrator responsible for access and compliance.

## Core User Stories
- As a teacher, I can see students assigned to me and identify those needing attention.
- As a parent, I can view only my authorized student's progress.
- As a tutor, I can identify weak skills and the next recommended activity.
- As an administrator, I can grant auditable role-based access.
- As a stakeholder, I can view historical snapshots rather than only current state.

## Functional Requirements
1. Create idempotent viewer-to-student access grants.
2. Produce a student dashboard from mastery, diagnostics, learning plans, and tutor sessions.
3. Rank strengths and weak skills using mastery and confidence.
4. Generate deterministic, explainable alerts.
5. Return a viewer overview for all authorized students.
6. Persist daily progress snapshots and expose trend history.
7. Prevent unauthorized cross-student access.

## Non-functional Requirements
- Dashboard reads should be deterministic and free of LLM dependency.
- Responses should be suitable for caching and generated within one second on V1 data volumes.
- Every metric must be traceable to persisted Level 1–4 records.
- No raw student work or tutor transcript appears in the summary response.

## Acceptance Criteria
- An unauthorized viewer receives HTTP 403.
- A teacher with a grant can retrieve a summary and roster overview.
- Weak skills, confidence, completion, and diagnostic accuracy are calculated consistently.
- A daily snapshot can be created repeatedly without duplicate rows.
- Existing Levels 1–4 tests continue to pass.

## Edge Cases
- No mastery evidence yet.
- Student has diagnostics but no active plan.
- Active plan has no activities.
- Viewer has multiple roles.
- Confidence is too low for reliable intervention.
- Snapshot is regenerated on the same day.

## Risks and Mitigations
- Misleading percentages: return confidence and evidence counts alongside mastery.
- Privacy leakage: enforce explicit access grants and omit raw content.
- Alert fatigue: use a small deterministic alert taxonomy with severity.
- Stale trends: store snapshot generation date and algorithm version.

## Success Metrics
- Dashboard access success rate.
- Percentage of at-risk students reviewed by a teacher.
- Parent dashboard return rate.
- Alert-to-intervention conversion.
- Snapshot coverage among active students.

## V1 Scope
Backend dashboard APIs, access grants, deterministic metrics, alerts, snapshots, and trends.

## Out of Scope
React visualizations, school SIS integration, email notifications, classroom grouping, district-level analytics, and predictive score claims.
