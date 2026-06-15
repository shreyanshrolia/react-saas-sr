from typing import Optional

from pydantic import BaseModel, Field

from . import Role


class SignupReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str = Field(..., min_length=6, max_length=80)
    role: Role
    address: Optional[str] = Field(None, max_length=300)
    security_question: str = Field(..., min_length=4, max_length=120)
    security_answer: str = Field(..., min_length=2, max_length=80)


class LoginReq(BaseModel):
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str


class ForgotPasswordReq(BaseModel):
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")


class ResetPasswordReq(BaseModel):
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    security_answer: str = Field(..., min_length=1, max_length=80)
    new_password: str = Field(..., min_length=6, max_length=80)


class AdminLoginReq(BaseModel):
    password: str


class AdminResetReq(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=80)


class UserPublic(BaseModel):
    id: str
    name: str
    phone: str
    role: Role
    address: Optional[str] = None
    trial_ends_at: Optional[str] = None
    subscription_status: str = "trial"
    subscription_ends_at: Optional[str] = None
    created_at: str


class AuthResp(BaseModel):
    token: str
    user: UserPublic
