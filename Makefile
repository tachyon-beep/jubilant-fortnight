SHELL := /usr/bin/env bash

# Configurable variables
PY ?= python3.12
VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DB ?= great_work.db

.PHONY: help venv install upgrade test lint seed run env clean-venv clean-db

help:
	@echo "Common tasks:"
	@echo "  make venv           Create virtualenv (.venv)"
	@echo "  make install        Install project + dev deps"
	@echo "  make upgrade        Upgrade project deps"
	@echo "  make test           Run pytest"
	@echo "  make lint           Run ruff if available"
	@echo "  make validate-narrative  Run narrative YAML validator"
	@echo "  make preview-narrative   Print sample narrative previews"
	@echo "  make seed DB=...    Seed the SQLite DB (default: great_work.db)"
	@echo "  make run            Run Discord bot (loads .env if present)"
	@echo "  make env            Create .env from .env.example if missing"
	@echo "  make clean-venv     Remove virtualenv"
	@echo "  make clean-db       Remove DB file ($(DB))"

venv:
	@# Create venv only if missing
	@if [ ! -d "$(VENV)" ]; then \
		$(PY) -m venv $(VENV); \
		echo "Created $(VENV) with $(PY)"; \
	fi
	@echo "Activate with: source $(VENV)/bin/activate"

install: venv
	$(PIP) install -U pip
	$(PIP) install -e .[dev]

upgrade: venv
	$(PIP) install -U -e .[dev]

test:
	$(PYTHON) -m pytest -q

validate-narrative:
	$(PYTHON) -m great_work.tools.validate_narrative --all

preview-narrative:
	$(PYTHON) -m great_work.tools.preview_narrative

lint:
	@if [ -x "$(VENV)/bin/ruff" ]; then \
		$(VENV)/bin/ruff . ; \
	else \
		echo "ruff not installed; skipping lint"; \
	fi

seed: venv
	$(PYTHON) -m great_work.tools.seed_db $(DB)

run: venv
	@bash -c 'set -a; [ -f .env ] && source .env; set +a; "$(PYTHON)" -m great_work.discord_bot'

env:
	@if [ -f .env ]; then \
		echo ".env already exists"; \
	else \
		cp .env.example .env && echo "Created .env from .env.example"; \
	fi

clean-venv:
	rm -rf $(VENV)

clean-db:
	rm -f $(DB)
