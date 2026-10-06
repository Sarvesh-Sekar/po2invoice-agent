"""Episodic memory repository backed by SQLAlchemy / PostgreSQL.

EPISODIC_MEMORY stores customer-specific extraction patterns/instructions —
never extracted values.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.episodic_memory import EpisodicMemory

DEFAULT_CONFIDENCE = Decimal("0.5")


class EpisodicMemoryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get(self, customer_id: str, field_id: str) -> EpisodicMemory | None:
        async with self._sf() as session:
            result = await session.execute(
                select(EpisodicMemory)
                .where(EpisodicMemory.customer_id == customer_id, EpisodicMemory.field_id == field_id)
                .order_by(EpisodicMemory.modified_at.desc())
            )
            return result.scalar_one_or_none()

    async def create(
        self,
        *,
        customer_id: str,
        field_id: str,
        location_hint: str | None,
        document_pattern: str | None,
        instruction: str | None,
        confidence: Decimal = DEFAULT_CONFIDENCE,
    ) -> EpisodicMemory:
        async with self._sf() as session:
            memory = EpisodicMemory(
                customer_id=customer_id,
                field_id=field_id,
                location_hint=location_hint,
                document_pattern=document_pattern,
                instruction=instruction,
                confidence=confidence,
                usage_count=0,
                success_count=0,
                failure_count=0,
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
            return memory

    async def record_success(
        self, memory_id: str, *, confidence_delta: Decimal = Decimal("0.05")
    ) -> EpisodicMemory | None:
        """Mark a validated episodic-guided extraction as successful."""

        async def _apply(session: AsyncSession) -> EpisodicMemory | None:
            existing = (
                await session.execute(select(EpisodicMemory).where(EpisodicMemory.id == memory_id))
            ).scalar_one_or_none()
            if existing is None:
                return None
            new_confidence = min(Decimal("1.0"), (existing.confidence or DEFAULT_CONFIDENCE) + confidence_delta)
            existing.confidence = new_confidence
            existing.usage_count = (existing.usage_count or 0) + 1
            existing.success_count = (existing.success_count or 0) + 1
            existing.last_used_at = datetime.now(UTC)
            session.add(existing)
            return existing

        async with self._sf() as session:
            memory = await _apply(session)
            await session.commit()
            if memory is not None:
                await session.refresh(memory)
            return memory

    async def record_failure(
        self, memory_id: str, *, confidence_delta: Decimal = Decimal("0.10")
    ) -> EpisodicMemory | None:
        """Record a failed episodic-guided extraction without destroying the pattern."""

        async def _apply(session: AsyncSession) -> EpisodicMemory | None:
            existing = (
                await session.execute(select(EpisodicMemory).where(EpisodicMemory.id == memory_id))
            ).scalar_one_or_none()
            if existing is None:
                return None
            new_confidence = max(Decimal("0.0"), (existing.confidence or DEFAULT_CONFIDENCE) - confidence_delta)
            existing.confidence = new_confidence
            existing.usage_count = (existing.usage_count or 0) + 1
            existing.failure_count = (existing.failure_count or 0) + 1
            existing.last_used_at = datetime.now(UTC)
            session.add(existing)
            return existing

        async with self._sf() as session:
            memory = await _apply(session)
            await session.commit()
            if memory is not None:
                await session.refresh(memory)
            return memory

    async def update_pattern(
        self,
        memory_id: str,
        *,
        location_hint: str | None = None,
        document_pattern: str | None = None,
        instruction: str | None = None,
        confidence: Decimal | None = None,
    ) -> EpisodicMemory | None:
        """Update the stored extraction pattern (only from validated discoveries)."""
        async with self._sf() as session:
            values: dict = {}
            if location_hint is not None:
                values["location_hint"] = location_hint
            if document_pattern is not None:
                values["document_pattern"] = document_pattern
            if instruction is not None:
                values["instruction"] = instruction
            if confidence is not None:
                values["confidence"] = confidence
            if values:
                await session.execute(update(EpisodicMemory).where(EpisodicMemory.id == memory_id).values(**values))
                await session.commit()
            result = await session.execute(select(EpisodicMemory).where(EpisodicMemory.id == memory_id))
            return result.scalar_one_or_none()
