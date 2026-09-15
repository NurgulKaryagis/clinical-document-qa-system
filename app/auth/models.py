import enum
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    QUERY = "query"
    EDITOR = "editor"
    ADMIN = "admin"


def default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=90)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str] = mapped_column(String, unique=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.QUERY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    api_keys: Mapped[list["APIKey"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=default_expiry)
    revoked: Mapped[bool] = mapped_column(default=False)

    user: Mapped["User"] = relationship(back_populates="api_keys")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    action: Mapped[str]
    endpoint: Mapped[str]
    status_code: Mapped[int]
    latency_ms: Mapped[int | None]
    cache_hit: Mapped[bool | None]
    confidence_score: Mapped[float | None]

    user: Mapped["User"] = relationship(back_populates="audit_logs")
