from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{12,}$")


def validate_password(password: str) -> str:
    if not PASSWORD_PATTERN.fullmatch(password):
        raise ValueError(
            "Password must be at least 12 characters and include lowercase, "
            "uppercase, a number, and a special character"
        )
    return password


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    password_verification: str
    mtg_player_id: str
    display_player_id: str

    @model_validator(mode="after")
    def validate_passwords(self):
        validate_password(self.password)
        if self.password != self.password_verification:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    new_password_verification: str

    @model_validator(mode="after")
    def validate_new_passwords(self):
        validate_password(self.new_password)
        if self.new_password != self.new_password_verification:
            raise ValueError("New passwords do not match")
        return self


class AccountDelete(BaseModel):
    password: str


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    display_player_id: Optional[str]


class DisplayPlayerIdChange(BaseModel):
    display_player_id: str = Field(min_length=1, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str
