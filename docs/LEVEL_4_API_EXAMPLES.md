# Level 4 API Examples

## Create session
```json
POST /api/v1/tutor/sessions
{
  "student_id": "stu_001",
  "skill_code": "ALG_LINEAR",
  "problem_text": "If 2x + 5 = 17, what is x?",
  "correct_answer": "6",
  "student_answer": "7",
  "student_work": "2x = 17 + 5, so x = 7"
}
```

## Continue
```json
POST /api/v1/tutor/sessions/{session_id}/messages
{"content": "I am not sure what I did wrong."}
```

## Complete
```json
POST /api/v1/tutor/sessions/{session_id}/complete
{"reflection": "I must subtract 5 from both sides before dividing."}
```
