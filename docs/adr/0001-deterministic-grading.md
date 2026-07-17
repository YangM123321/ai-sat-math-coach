# ADR 0001: Deterministic Grading Is the Correctness Authority

## Status
Accepted

## Context
LLMs can inconsistently compare mathematically equivalent answer formats and are unnecessary for simple equivalence checks.

## Decision
A deterministic grading service decides final-answer correctness. The diagnostic provider analyzes reasoning but cannot override that result.

## Consequences
The system is cheaper, easier to test, and more reproducible. Symbolic equivalence beyond V1 will require a stronger math engine.
