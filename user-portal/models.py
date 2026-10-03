import uuid

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.types import CHAR, TypeDecorator

from database import Base


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        return str(value) if value is not None else None


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    mtg_player_id = Column(String, unique=True, nullable=True)
    display_player_id = Column(String, nullable=True)
    is_email_verified = Column(Boolean, nullable=False, default=False)
    verification_token_hash = Column(String, nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)
