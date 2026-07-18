"""Argon2id password hashing (Phase 1.5 PR 3).

Passwords are always hashed with Argon2id before persistence -- the
plaintext value is never stored and never logged. Argon2id is passed
explicitly to PasswordHasher (argon2-cffi has defaulted to Argon2id
since 18.2.0, but the type is asserted in code here rather than
inherited silently from a library default).
"""
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHash, VerifyMismatchError

_DUMMY_PASSWORD = "dummy-password-never-used-for-a-real-account"
# Computed once at import time (not per-request, not per-PasswordService
# instance) so the login timing-mitigation below (verify_dummy) costs one
# real Argon2id verification per call, without paying an extra hashing
# cost on every request just to prepare the placeholder.
_DUMMY_HASH = PasswordHasher(type=Type.ID).hash(_DUMMY_PASSWORD)


class PasswordService:
    def __init__(self):
        self._hasher = PasswordHasher(type=Type.ID)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHash):
            return False

    def verify_dummy(self) -> None:
        """Run a real Argon2id verification against a fixed, precomputed
        dummy hash so a login attempt against a nonexistent email takes
        comparable time to one against a real email with a wrong
        password -- closing the timing side-channel that would
        otherwise let an attacker distinguish "no such account" from
        "wrong password" by response latency. The dummy password always
        matches the dummy hash, so this never raises; the result is
        discarded either way."""
        try:
            self._hasher.verify(_DUMMY_HASH, _DUMMY_PASSWORD)
        except (VerifyMismatchError, InvalidHash):
            pass
