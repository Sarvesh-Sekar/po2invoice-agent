"""Idempotent seed data loading.

Seeds canonical FIELD_DEFINITIONS from YAML so the extraction subgraph always
has a stable field catalogue to work against.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.repositories.field_definition_repository import FieldDefinitionRepository
from app.repositories.schemas.orm.field_definitions import FieldDefinition

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_seed(file_name: str) -> dict:
    path = _DATA_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"Seed data file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Seed data file '{file_name}' must be a YAML mapping")
    return data


async def seed_field_definitions(
    session_factory: async_sessionmaker[AsyncSession],
    file_name: str = "field_definitions.yaml",
) -> list[FieldDefinition]:
    """Create the canonical FIELD_DEFINITIONS unless they already exist."""
    repository = FieldDefinitionRepository(session_factory)
    existing = await repository.list_all()
    existing_names = {definition.field_name for definition in existing}
    if len(existing_names) >= 18:
        return existing

    created: list[FieldDefinition] = []
    data = _load_seed(file_name)
    for group in ("header_fields", "line_item_fields"):
        for definition in data.get(group, []):
            field_name = definition["field_name"]
            if field_name in existing_names:
                created.append(await repository.get_by_name(field_name))  # type: ignore[arg-type]
                continue
            created.append(
                await repository.create(
                    field_name=field_name,
                    field_description=definition.get("field_description"),
                    field_type=definition.get("field_type", "string"),
                )
            )
    return created
