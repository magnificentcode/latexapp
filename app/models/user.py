# app/models/user.py

import uuid

from pydantic import BaseModel, EmailStr, field_validator


class UserCredentials(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower().strip()


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
