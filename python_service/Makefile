.PHONY: install dev run lint format test sync

install:
	uv sync --extra dev --extra evaluation

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

lint:
	uv run ruff check app tests

format:
	uv run ruff format app tests

test:
	uv run pytest

sync:
	uv sync --extra dev --extra evaluation