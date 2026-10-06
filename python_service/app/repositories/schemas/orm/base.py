"""Shared ORM mixins and column types."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Uuid, func
from sqlalchemy.types import TypeDecorator


def new_uuid_id() -> str:
    return str(uuid.uuid4())


class GUID(TypeDecorator):
    """Primary/foreign key column backed by a native ``uuid`` type.

    The shared schema is created by the Go service (GORM ``AutoMigrate``), which
    declares every identifier as ``type:uuid``. asyncpg refuses to bind a
    ``str`` to a ``uuid`` parameter, so the value is converted on the way in and
    handed back to Python as the canonical dashed string on the way out.
    """

    impl = Uuid(as_uuid=True, native_uuid=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

    def process_result_value(self, value, dialect):
        return None if value is None else str(value)


class UUIDPrimaryKeyMixin:
    id = Column(
        GUID(),
        primary_key=True,
        default=new_uuid_id,
    )


class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ModifiedTimestampMixin:
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
