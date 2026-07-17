# Level 4 Product Requirements Document — Socratic AI Tutor

## Executive Summary
Level 4 turns diagnostic and mastery data into an interactive tutoring experience. The tutor does not default to giving answers. It uses short, evidence-grounded questions and progressively stronger hints to help students repair their own reasoning.

## Product Vision
Give every SAT Math learner access to immediate, personalized instructional dialogue that is connected to diagnosed errors, current mastery, and assigned learning activities.

## Business Goals
- Increase completion of personalized learning activities.
- Reduce repeated errors by requiring active reasoning.
- Differentiate the product from answer-generating chatbots.
- Produce auditable tutoring interaction data for Level 6 evaluation.

## Primary Personas
- Independent SAT learner who becomes stuck during practice.
- Tutor or teacher who wants students to receive guided help between sessions.
- Parent who wants safe, purposeful AI support rather than unrestricted answer generation.

## User Stories
- As a student, I can open a tutor session for a specific skill and problem.
- As a student, I receive one focused prompt at a time.
- As a student, I can request hints without immediately seeing the final answer.
- As a teacher, I can inspect the exact tutoring conversation and instructional strategy.
- As the product team, we can measure helpfulness and hint usage.

## Functional Requirements
1. Create a session associated with a student and SAT skill.
2. Optionally associate the session with a Level 3 learning activity.
3. Persist the problem, submitted answer, and student work.
4. Store every message in immutable sequence order.
5. Label tutor messages by strategy: Socratic question, hint, explanation, or reflection.
6. Enforce active/completed session states.
7. Track hints used and maximum hints.
8. Allow explicit completion with a student reflection.
9. Collect helpfulness feedback and optional rating.
10. Preserve provider and policy versions.

## Nonfunctional Requirements
- P95 API latency below five seconds with a production provider.
- No silent loss of conversation history.
- Strict request size limits.
- Provider output must be policy-validated before persistence.
- Student records must be authorization-scoped in production.

## Acceptance Criteria
- A valid skill can start a tutor session.
- An unknown skill returns a typed 404 error.
- The opening response asks a reasoning question rather than merely providing the answer.
- A stuck response produces a hint and increments hint usage.
- Completed sessions reject additional messages.
- Feedback is stored against a valid session.

## Edge Cases
- Missing student work.
- Student explicitly demands the answer.
- Student submits off-topic text.
- Correct answer is unknown.
- Session is resumed after completion.
- Linked learning activity is deleted or superseded.

## Risks and Mitigations
- **Answer leakage:** progressive disclosure and hint limits.
- **Hallucinated reasoning:** use only problem and conversation evidence.
- **Overdependence:** require student response between tutor steps.
- **Unsafe or irrelevant content:** production moderation boundary before provider invocation.
- **Privacy:** avoid logging raw tutoring content in request logs.

## Success Metrics
- Session completion rate.
- Percentage of sessions ending with a student reflection.
- Hint-to-explanation ratio.
- Helpfulness rating.
- Subsequent accuracy on the same skill.
- Policy violation rate.

## V1 Scope
Text-based, skill-linked, asynchronous Socratic tutoring with deterministic local provider, persisted messages, state management, and feedback.

## Out of Scope
Voice tutoring, handwritten whiteboard interaction, live teacher takeover, unrestricted general chat, and claims of measured learning improvement.

## Future Enhancements
Production LLM provider, retrieval of vetted SAT explanations, moderation, multilingual support, teacher intervention, streaming, and adaptive hint depth.
