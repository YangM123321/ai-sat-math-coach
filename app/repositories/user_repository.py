from datetime import datetime, timezone

from sqlalchemy import select

from app.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, db):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save_refresh_token(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def revoke_refresh_token(self, token: RefreshToken, *, replaced_by_id: str | None = None) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        if replaced_by_id is not None:
            token.replaced_by_id = replaced_by_id
        self.db.commit()

    def revoke_all_refresh_tokens_for_user(self, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        tokens = list(
            self.db.scalars(
                select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            ).all()
        )
        for token in tokens:
            token.revoked_at = now
        self.db.commit()
        return len(tokens)
