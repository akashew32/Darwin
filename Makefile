.PHONY: setup test lint format typecheck doctor dashboard docker-up

export PYTHONPATH := src

setup:
	python -m pip install -e ".[dev,postgres]"
	pre-commit install

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

format:
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .

typecheck:
	.venv/bin/mypy

doctor:
	.venv/bin/darwin doctor

dashboard:
	.venv/bin/darwin dashboard

docker-up:
	docker compose up --build
