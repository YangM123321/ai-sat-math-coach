# Level 3 API Examples

## Generate a seven-day plan

```json
POST /api/v1/learning-plans
{
  "student_id": "stu_001",
  "start_date": "2026-07-20",
  "exam_date": "2026-10-03",
  "target_score": 700,
  "daily_minutes": 30,
  "duration_days": 7,
  "max_focus_skills": 4
}
```

## Update activity progress

```json
PATCH /api/v1/learning-activities/act_123
{
  "status": "completed",
  "completed_questions": 6,
  "correct_questions": 5
}
```
