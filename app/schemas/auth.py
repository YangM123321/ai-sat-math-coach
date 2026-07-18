from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    # extra="forbid" so a caller-supplied `role` (or any other
    # unrecognized field) is rejected with a 422, not silently dropped.
    # There is no role field on this model at all -- registration always
    # creates the least-privileged role; see app/services/auth_service.py.
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutAllResponse(BaseModel):
    revoked_count: int
