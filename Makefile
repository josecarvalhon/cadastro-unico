.PHONY: help install generate up down logs clean reset status ingest-bronze dbt-run dbt-test dbt-docs api-run airflow-password airflow-trigger sql

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "Targets disponíveis:"
	@echo "  install   - cria venv e instala requirements"
	@echo "  generate  - gera dados sintéticos das 5 fontes"
	@echo "  ingest-bronze - roda os 5 conectores Bronze (extrai → Parquet → MinIO)"
	@echo "  dbt-run   - roda todos os modelos dbt (Prata + Ouro)"
	@echo "  dbt-test  - roda dbt test"
	@echo "  dbt-docs  - gera e serve dbt docs"
	@echo "  api-run   - sobe a FastAPI em http://localhost:8000 (docs em /docs)"
	@echo "  airflow-password - imprime a senha do admin gerada pelo Airflow standalone"
	@echo "  airflow-trigger  - dispara a DAG cadastro_unico_etl manualmente"
	@echo "  sql       - abre shell DuckDB com views pré-registradas para queries ad-hoc"
	@echo "  up        - sobe infraestrutura (docker compose up -d)"
	@echo "  down      - derruba infraestrutura"
	@echo "  logs      - mostra logs em tempo real"
	@echo "  status    - lista containers"
	@echo "  reset     - down + remove volumes + sobe limpo"
	@echo "  clean     - remove venv e arquivos gerados"

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

generate: install
	$(PY) scripts/generate_all.py

ingest-bronze: install
	PYTHONPATH=. $(PY) -m ingest.bronze.run_all

dbt-run: install
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/bin/dbt run

dbt-test: install
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/bin/dbt test

dbt-docs: install
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/bin/dbt docs generate
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/bin/dbt docs serve --port 8082

api-run: install
	PYTHONPATH=. $(VENV)/bin/uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload

airflow-password:
	@docker exec cu-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated 2>/dev/null \
		|| docker exec cu-airflow cat /opt/airflow/standalone_admin_password.txt 2>/dev/null \
		|| docker exec cu-airflow airflow users reset-password -u admin -p admin && echo "Senha redefinida como: admin"

airflow-trigger:
	docker exec cu-airflow airflow dags trigger cadastro_unico_etl

sql: install
	$(PY) scripts/sql.py

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

status:
	docker compose -f infra/docker-compose.yml ps

reset:
	docker compose -f infra/docker-compose.yml down -v
	docker compose -f infra/docker-compose.yml up -d

clean:
	rm -rf $(VENV)
	rm -rf data/seed
	rm -f infra/postgres/seed.sql infra/mysql/seed.sql
