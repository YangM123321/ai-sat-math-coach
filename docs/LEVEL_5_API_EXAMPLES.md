# Level 5 API Examples

## Grant teacher access
```http
POST /api/v1/dashboard/access-grants
```
```json
{"viewer_id":"teacher_1","student_id":"stu_1","role":"teacher","created_by":"admin_1"}
```

## Read student dashboard
```http
GET /api/v1/dashboard/students/stu_1?viewer_id=teacher_1&role=teacher
```

## Read teacher overview
```http
GET /api/v1/dashboard/viewers/teacher_1/overview?role=teacher
```

## Create daily snapshot
```http
POST /api/v1/dashboard/students/stu_1/snapshots?viewer_id=teacher_1&role=teacher
```

## Read trend history
```http
GET /api/v1/dashboard/students/stu_1/trends?viewer_id=teacher_1&role=teacher&limit=30
```
