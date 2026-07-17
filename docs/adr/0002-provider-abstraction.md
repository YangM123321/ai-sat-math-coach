# ADR 0002: Use a Diagnostic Provider Interface

## Status
Accepted

## Context
The portfolio should demonstrate AI architecture without binding the domain layer to one vendor.

## Decision
All model calls implement a `DiagnosticProvider` interface. The repository includes a deterministic development provider; production providers can be added behind the same contract.

## Consequences
Vendor migration and testing are easier. Provider-specific advanced capabilities require adapters.
