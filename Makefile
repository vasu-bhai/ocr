.PHONY: install dev test lint migrate

install:
	python -m pip install -r requirements.txt

dev:
	python -m uvicorn app.main:app --reload --port 8000

test:
	python -m pytest tests/ -v

lint:
	python -m ruff check .

migrate:
	python -m alembic upgrade head
