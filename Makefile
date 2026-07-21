.PHONY: setup test lint format typecheck doctor dashboard docker-up

export PYTHONPATH := src
VENV_BIN := .venv/bin
PYTEST := $(if $(wildcard $(VENV_BIN)/pytest),$(VENV_BIN)/pytest,pytest)
RUFF := $(if $(wildcard $(VENV_BIN)/ruff),$(VENV_BIN)/ruff,ruff)
MYPY := $(if $(wildcard $(VENV_BIN)/mypy),$(VENV_BIN)/mypy,mypy)
DARWIN := $(if $(wildcard $(VENV_BIN)/darwin),$(VENV_BIN)/darwin,darwin)

setup:
	python -m pip install -e ".[dev,postgres]"
	pre-commit install

test:
	$(PYTEST)

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) check --fix .
	$(RUFF) format .

typecheck:
	$(MYPY)

doctor:
	$(DARWIN) doctor

dashboard:
	$(DARWIN) dashboard

docker-up:
	docker compose up --build
