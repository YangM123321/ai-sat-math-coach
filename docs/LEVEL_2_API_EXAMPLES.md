# Level 2 API Examples

## Create a skill

```json
POST /api/v1/skills
{
  "code": "linear_equations",
  "name": "Linear equations",
  "domain": "algebra"
}
```

## Add evidence

```json
POST /api/v1/mastery/evidence
{
  "student_id": "stu_001",
  "skill_code": "linear_equations",
  "evidence_type": "diagnostic_attempt",
  "source_id": "diag_abc123",
  "is_correct": false,
  "diagnostic_confidence": 0.94,
  "difficulty": "medium",
  "error_category": "procedural_error"
}
```

## Retrieve profile

```text
GET /api/v1/students/stu_001/knowledge-profile
```

The response contains the current score and confidence separately. A low score with low confidence means the system has weak evidence, not that the student has been conclusively classified.
