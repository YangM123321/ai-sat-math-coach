# Level 1 Engineering Specification

## Objective
Transform one SAT Math attempt into persistent, structured learning data: correctness, domain, skill, earliest causal error, evidence, explanation, recommended action, confidence, and human-review status.

## Workflow
Validation → deterministic grading → attempt persistence → provider analysis → Pydantic validation → confidence policy → review decision → result persistence → API response.

## V1 scope
Typed questions, typed answers, optional typed work, structured provider interface, rule-based local provider, SQLite/PostgreSQL-ready persistence, history, feedback, tests, and a fail-closed OCR contract.

## Taxonomy
`none`, `conceptual_misunderstanding`, `equation_setup_error`, `strategy_selection_error`, `procedural_error`, `arithmetic_error`, `interpretation_error`, `formula_recall_error`, `visual_interpretation_error`, `incomplete_reasoning`, `insufficient_evidence`.

## Confidence rules
Base 0.50; +0.15 high provider confidence; +0.10 usable work; +0.10 official explanation; +0.05 pre-labeled domain/skill; +0.05 cited evidence; -0.20 missing work; -0.15 multiple alternatives; -0.15 insufficient evidence; -0.10 low provider confidence. Scores are clamped to 0–1. Review is required below 0.60 or when evidence is insufficient/ambiguous.

## Definition of done
A valid attempt returns a validated diagnosis, persists it, retrieves it, lists student history, stores feedback, lowers confidence for missing work, flags ambiguity, and passes automated tests without an external API key.
