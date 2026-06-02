"""DAG: cadastro_unico_etl — pipeline analítico do Cadastro Único.

Fluxo:

    ingest_a ─┐
    ingest_b ─┤
    ingest_c ─┼─► dbt_run ─► dbt_test
    ingest_d ─┤
    ingest_e ─┘

As 5 ingestões correm como tasks independentes (SequentialExecutor as roda
em série, mas o DAG já modela o paralelismo correto para upgrade futuro
para LocalExecutor). dbt_run só dispara depois que todas as Bronze ficam OK.
dbt_test verifica a qualidade ao final.

Assume que as 5 fontes (Postgres, MySQL, Mongo, CSV, mock-API) já têm dados.
Para um cenário de refresh completo (regerar dados sintéticos), seria uma
DAG separada — mantida fora do escopo desta orquestração analítica.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_ROOT = "/opt/project"

default_args = {
    "owner": "engenharia-de-dados",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="cadastro_unico_etl",
    description="Bronze (5 fontes) → Prata → Ouro do Cadastro Único.",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["cadastro-unico", "lakehouse", "medalhao"],
) as dag:

    # ------------------------------------------------------------------
    # Bronze — 1 task por fonte. PYTHONPATH e env já vêm do compose.
    # ------------------------------------------------------------------
    bronze_tasks = []
    for fonte in ("empresa_a", "empresa_b", "empresa_c", "empresa_d", "empresa_e"):
        bronze_tasks.append(
            BashOperator(
                task_id=f"ingest_bronze_{fonte}",
                bash_command=f"cd {PROJECT_ROOT} && python -m ingest.bronze.{fonte}",
            )
        )

    # ------------------------------------------------------------------
    # Prata + Ouro — dbt rodando todos os modelos.
    # ------------------------------------------------------------------
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {PROJECT_ROOT}/dbt && DBT_PROFILES_DIR=. dbt run"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {PROJECT_ROOT}/dbt && DBT_PROFILES_DIR=. dbt test"
        ),
        # Testes falham com warnings em deprecations da versão 1.11; mantemos
        # o exit code do dbt para sinalizar falha de qualidade no Airflow.
    )

    bronze_tasks >> dbt_run >> dbt_test
