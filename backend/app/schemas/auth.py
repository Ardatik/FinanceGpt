from pydantic import BaseModel, EmailStr, Field


class AuthCodeRequest(BaseModel):
    email: EmailStr


class AuthVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    onboarding_completed: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
