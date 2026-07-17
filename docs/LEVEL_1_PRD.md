# Level 1 Product Requirements Document — AI Diagnostic Engine

## 1. Executive Summary

The AI Diagnostic Engine converts a student’s SAT Math attempt into an actionable diagnosis. It determines whether the response is correct, identifies the tested skill, locates the earliest meaningful reasoning error, classifies the root cause, explains the issue in student-friendly language, recommends one next action, and exposes confidence and human-review signals.

The engine is the first operational capability in AI SAT Math Coach. Its structured output becomes the input for the Student Knowledge Model, personalized practice, tutoring, and educator reporting.

## 2. Product Vision

Give every SAT Math learner access to immediate, evidence-grounded feedback that explains not only that an answer is wrong, but why the reasoning failed and what to practice next.

## 3. Business Goals

- Differentiate the product from answer-checking tools and generic chatbots.
- Reduce the manual diagnostic workload for tutors and teachers.
- Create structured learner data that enables later personalization.
- Demonstrate an interview-quality AI application with measurable reliability controls.
- Establish a reusable diagnostic API that can support direct-to-consumer and B2B education workflows.

## 4. Problem Statement

Students often receive binary grading and generic explanations. Two students can select the same wrong answer for different reasons, so identical feedback is inefficient and may reinforce misconceptions. Tutors can diagnose errors manually, but that process is slow, expensive, and difficult to scale.

## 5. Personas

### Primary: Independent SAT Student

Needs immediate, understandable feedback and a clear next step. May not be able to afford frequent one-on-one tutoring.

### Secondary: SAT Tutor or Teacher

Needs structured evidence, recurring-error visibility, and a way to confirm or correct AI diagnoses.

### Secondary: Parent

Needs simplified progress information and confidence that study time is targeting real weaknesses.

### Internal Consumer: Personalization Services

Needs stable, machine-readable diagnostic fields rather than prose-only output.

## 6. Core User Stories

- As a student, I can submit a question, my answer, and my work so I can understand the cause of my mistake.
- As a student, I receive one focused action rather than an overwhelming remediation plan.
- As a teacher, I can inspect the evidence supporting a diagnosis.
- As a teacher, I can confirm or correct a diagnosis for future evaluation.
- As a system, I can store diagnostic history by student and skill.
- As a system, I can flag uncertain cases for human review instead of presenting speculation as fact.

## 7. User Journey

1. The student submits a typed SAT Math question, expected answer, student answer, and optional work.
2. The API validates the request.
3. Deterministic grading checks answer equivalence.
4. The diagnostic provider analyzes the reasoning.
5. Structured output is validated.
6. Confidence and human-review rules are applied.
7. The attempt and diagnosis are saved.
8. The student sees the diagnosis and recommended action.
9. A teacher can later review and submit feedback.

## 8. Functional Requirements

### FR-1 Submission

The system shall accept typed question text, correct answer, student answer, student ID, optional work, optional answer choices, optional official explanation, and optional metadata.

### FR-2 Deterministic Grading

The system shall compare common numeric equivalents such as `0.5` and `1/2` without requiring an LLM.

### FR-3 Structured Diagnosis

The system shall return domain, skill, error category, error subcategory, evidence, root cause, explanation, recommendation, confidence, and review status.

### FR-4 Evidence Grounding

Every nontrivial diagnosis shall include at least one evidence statement tied to the submitted material.

### FR-5 Confidence and Review

The system shall calculate a transparent confidence score and require human review when confidence is low, evidence is insufficient, or multiple diagnoses are similarly plausible.

### FR-6 Persistence

The system shall persist attempts, diagnoses, prompt/model versions, confidence breakdowns, and raw structured provider outputs.

### FR-7 Retrieval

The system shall retrieve one diagnosis and list diagnostic history for one student.

### FR-8 Feedback

The system shall allow authorized reviewers to confirm or correct a diagnosis.

### FR-9 Image Contract

The system shall define an image-upload contract but fail closed until a production math OCR provider is configured.

## 9. Non-Functional Requirements

- P95 API latency target: under 5 seconds with a production provider.
- Structured-output validation success: 100% after retries/fallbacks.
- No cross-student data access once authentication is enabled.
- All public APIs documented in OpenAPI.
- All secrets supplied through environment variables or a secret manager.
- Logs must include request IDs and must not contain raw student work by default.
- Database migrations must be reproducible through Alembic.
- Core service and API test coverage target: at least 85%.

## 10. Acceptance Criteria

- A valid incorrect attempt produces HTTP 201 and a persisted structured diagnosis.
- A correct equivalent numeric answer produces `error_category=none`.
- Missing student work lowers confidence and triggers review when appropriate.
- Invalid request fields produce HTTP 422.
- Unknown diagnostic IDs produce a typed HTTP 404 response.
- Feedback can be stored against an existing diagnosis.
- Tests run without an external AI API key.
- Docker and CI configuration are included.

## 11. Edge Cases

- Correct final answer with flawed work.
- Incorrect final answer with correct method and arithmetic slip.
- Multiple valid answer formats.
- No student work.
- Ambiguous or contradictory work.
- Duplicate answer choices.
- Extremely long work text.
- Unreadable image or unsupported media type.
- Provider timeout or invalid structured output.
- A provider disagrees with deterministic grading.

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Hallucinated reasoning | Evidence grounding, strict schema, human review |
| Overconfidence | Transparent confidence policy and calibration dataset |
| OCR corruption | Preserve original input, confidence threshold, student correction flow |
| Cost growth | Deterministic grading first, provider abstraction, caching later |
| Privacy exposure | Data minimization, authorization, redacted logs |
| Taxonomy inconsistency | Controlled enums, labeled evaluation set, reviewer feedback |

## 13. Success Metrics

### Product

- Diagnostic viewed rate
- Recommended-action completion rate
- Reduction in repeated error categories
- Teacher helpfulness and agreement ratings

### Model and System

- Primary-category accuracy
- Human-review recall for ambiguous cases
- Overconfidence rate
- Structured-output validity
- P50/P95 latency
- Cost per diagnosis

## 14. V1 Scope

Implemented V1 supports typed questions and typed work, deterministic grading, structured diagnostics, persistence, retrieval, history, feedback, confidence scoring, tests, Docker, migrations, and CI.

## 15. Out of Scope

- Production handwriting OCR
- Production LLM credentials or vendor lock-in
- Student Knowledge Graph updates
- Personalized learning plans
- Interactive tutoring
- Parent or teacher UI
- Claims of proven SAT score improvement

## 16. Future Enhancements

- Production multimodal OCR
- Vendor-backed structured-output LLM provider
- Semantic equivalence for symbolic algebra
- Caching of canonical problem analyses
- Reviewer queue and audit dashboard
- Confidence calibration using isotonic regression or Platt scaling
- Knowledge-model event publishing
