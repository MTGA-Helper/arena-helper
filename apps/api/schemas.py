from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class TelemetryPayload(BaseModel):
    deck_slug: str
    result: str
    turns: Optional[int] = 8
    opponent_archetype: Optional[str] = "unknown"
    timestamp: Optional[str] = None
