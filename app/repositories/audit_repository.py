from app.models.audit import AuditEvent


class AuditRepository:
    """Append-only by convention: no update/delete methods exist here."""

    def __init__(self, db):
        self.db = db

    def save(self, event: AuditEvent) -> AuditEvent:
        self.db.add(event)
        self.db.commit()
        return event
