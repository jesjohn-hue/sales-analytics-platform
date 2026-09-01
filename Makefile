.PHONY: install postgres-install generate dashboard db-up db-down db-init load db-check sql-check test test-integration lint format

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
PSQL := .local/postgresql-16.15/bin/psql

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -e ".[dev]"

postgres-install:
	sh scripts/install_postgres.sh

generate:
	PYTHONPATH=src $(PYTHON) -m sales_analytics.pipeline.generate

dashboard:
	PYTHONPATH=src .venv/bin/streamlit run dashboard/app.py

db-up:
	sh scripts/local_postgres.sh up

db-down:
	sh scripts/local_postgres.sh down

db-init:
	PYTHONPATH=src $(PYTHON) -m sales_analytics.pipeline.load --init-only

load:
	PYTHONPATH=src $(PYTHON) -m sales_analytics.pipeline.load

db-check:
	@DSN="$$(PYTHONPATH=src $(PYTHON) -c 'from sales_analytics.config import Settings; print(Settings.from_env().psycopg_dsn)')"; \
	$(PSQL) "$$DSN" -v ON_ERROR_STOP=1 -f sql/tests/001_integrity_checks.sql

sql-check:
	@DSN="$$(PYTHONPATH=src $(PYTHON) -c 'from sales_analytics.config import Settings; print(Settings.from_env().psycopg_dsn)')"; \
	for file in sql/queries/*.sql; do \
		echo "Executing $$file"; \
		$(PSQL) "$$DSN" -v ON_ERROR_STOP=1 -f "$$file" >/dev/null || exit 1; \
	done

test:
	$(PYTEST)

test-integration:
	RUN_POSTGRES_TESTS=1 $(PYTEST) tests/integration

lint:
	$(RUFF) check .

format:
	$(RUFF) format .
