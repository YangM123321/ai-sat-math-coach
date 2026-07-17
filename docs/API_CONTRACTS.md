# API Contracts

- `POST /api/v1/diagnostics` — create diagnosis (`201`)
- `GET /api/v1/diagnostics/{id}` — retrieve one (`200`, `404`)
- `GET /api/v1/students/{student_id}/diagnostics` — paginated history
- `POST /api/v1/diagnostics/{id}/feedback` — store human feedback (`201`)
- `POST /api/v1/diagnostics/from-image` — validates upload then fails closed until OCR is configured

## Main request
```json
{"student_id":"stu_001","question":{"question_text":"If 2x + 5 = 17, what is x?","correct_answer":"6","domain":"algebra","skill":"linear_equations"},"student_answer":"7","work_text":"2x = 17 + 5, so 2x = 22 and x = 7"}
```

## Error envelope
```json
{"error":{"code":"DIAGNOSTIC_NOT_FOUND","message":"The requested diagnostic result does not exist.","details":{"diagnostic_id":"diag_missing"}}}
```
