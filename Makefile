.PHONY: setup test lint format typecheck doctor dashboard docker-up

setup:
	python -m pip install -e ".[dev,postgres]"
	pre-commit install

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy

doctor:
	darwin doctor

dashboard:
	darwin dashboard

docker-up:
	docker compose up --build
