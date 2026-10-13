PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff
export PYTHONPATH := .

.PHONY: dev web train test eval lint up down

dev:
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8741

web:
	cd frontend && npm run dev -- --hostname 0.0.0.0 --port 8742

train:
	$(PYTHON) -m backend.ml.generate_dataset
	$(PYTHON) -m backend.ml.train_risk_model

test:
	$(PYTEST) --cov=backend --cov-report=term-missing

eval:
	$(PYTHON) -m backend.evaluation.run_comparison
	$(PYTHON) -m backend.evaluation.report

lint:
	$(RUFF) check backend tests

up:
	docker compose up --build

down:
	docker compose down
