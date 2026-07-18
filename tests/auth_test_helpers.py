"""Shared test helper for Phase 1.5 PR 4 authorization tests.

Every domain route now requires a valid JWT (app.api.dependencies.
get_current_user), so every existing API test needs a real,
authenticated user instead of an arbitrary student_id string.

Registration always creates a `student` (app/schemas/auth.py's
RegisterRequest has no role field at all -- see app/services/auth_service.py).
There is no API-level role-assignment endpoint (intentionally out of
scope for this PR -- see docs/security/THREAT_MODEL.md's deferred-work
notes), so promoting a test user to teacher/admin is done by writing
directly to the database, mirroring the exact pattern already
established in tests/test_auth_api.py's `db` fixture for flipping
`is_active`.
"""
from app.db.session import SessionLocal
from app.models.user import User

DEFAULT_PASSWORD = "correct-horse-battery-staple"


def register_and_login(client, email, password=DEFAULT_PASSWORD, role="student"):
    """Registers (always as student), optionally promotes role directly
    in the database, logs in, and returns (user_id, access_token)."""
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert registered.status_code == 201, registered.text
    user_id = registered.json()["id"]
    if role != "student":
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            user.role = role
            db.commit()
        finally:
            db.close()
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200, logged_in.text
    return user_id, logged_in.json()["access_token"]


def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}
