"""Safe YAML prompt loading with caching."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

from app.exceptions.base import BaseAppError


class PromptNotFoundError(BaseAppError):
    def __init__(self, file_name: str, key: str) -> None:
        super().__init__(
            "PROMPT_NOT_FOUND",
            f"Prompt '{key}' not found in '{file_name}'",
            status_code=500,
        )


def _prompt_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts"


@cache
def _load_yaml(file_name: str) -> dict:
    path = _prompt_dir() / file_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Prompt file '{file_name}' must be a YAML mapping")
    return data


def load_prompt(file_name: str, key: str) -> str:
    """Load a rendered prompt string by file and key.

    Prompts are stored as YAML (organization format) while the prompt body
    itself uses XML-style semantic tags (<role>, <objective>, ...).
    """
    data = _load_yaml(file_name)
    prompt = data.get(key)
    if not isinstance(prompt, str) or not prompt.strip():
        raise PromptNotFoundError(file_name, key)
    return prompt.strip()


def load_prompt_messages(file_name: str, key: str) -> dict:
    """Load a structured prompt (multi-part) by file and key, if present."""
    data = _load_yaml(file_name)
    value = data.get(key)
    if not isinstance(value, dict):
        raise PromptNotFoundError(file_name, key)
    return value


def load_memory(file_name: str = "memory.yaml") -> dict:
    """Load the full procedural/semantic memory file as a parsed mapping."""
    data = _load_yaml(file_name)
    if not isinstance(data, dict):
        raise ValueError(f"Memory file '{file_name}' must be a YAML mapping")
    return data
