"""DAG: cadastro_unico_etl — pipeline analítico do Cadastro Único.

Fluxo:

    ingest_a ─┐
    ingest_b ─┤
    ingest_c ─┼─► dbt_deps ─► dbt_run ─► dbt_test ─► dbt_source_freshness ─► edr_report
    ingest_d ─┤
    ingest_e ─┘

As 5 ingestões correm como tasks independentes (SequentialExecutor as roda
em série, mas o DAG já modela o paralelismo correto para upgrade futuro
para LocalExecutor). dbt_run só dispara depois que todas as Bronze ficam OK.
dbt_test verifica a qualidade; dbt_source_freshness e edr_report alimentam
o dashboard Elementary (HTML estático em docs/elementary_report.html).

Assume que as 5 fontes (Postgres, MySQL, Mongo, CSV, mock-API) já têm dados.
Para um cenário de refresh completo (regerar dados sintéticos), seria uma
DAG separada — mantida fora do escopo desta orquestração analítica.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule

PROJECT_ROOT = "/opt/project"
DBT_DIR = f"{PROJECT_ROOT}/dbt"
DBT_CMD_PREFIX = f"cd {DBT_DIR} && DBT_PROFILES_DIR=."

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
    # dbt deps — idempotente; garante package Elementary em clone fresco
    # ou após rebuild da imagem.
    # ------------------------------------------------------------------
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT_CMD_PREFIX} dbt deps",
    )

    # ------------------------------------------------------------------
    # Prata + Ouro — dbt rodando todos os modelos.
    # ------------------------------------------------------------------
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"{DBT_CMD_PREFIX} dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT_CMD_PREFIX} dbt test",
        # Testes falham com warnings em deprecations da versão 1.11; mantemos
        # o exit code do dbt para sinalizar falha de qualidade no Airflow.
    )

    # ------------------------------------------------------------------
    # Monitoramento Elementary — freshness das fontes + geração do HTML.
    # all_done garante publicação do report mesmo quando há testes vermelhos
    # (é justamente quando ele importa).
    # ------------------------------------------------------------------
    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"{DBT_CMD_PREFIX} dbt source freshness",
        trigger_rule=TriggerRule.ALL_DONE,
    )

    edr_report = BashOperator(
        task_id="edr_report",
        bash_command=(
            f"mkdir -p {PROJECT_ROOT}/docs && "
            # DBT_DUCKDB_PATH absoluto: edr chama dbt com --project-dir
            # apontando para o package Elementary interno, então path relativo
            # da profile resolveria a partir daquela pasta vazia.
            f"DBT_DUCKDB_PATH={DBT_DIR}/cadastro_unico.duckdb "
            f"edr report "
            f"--file-path {PROJECT_ROOT}/docs/elementary_report.html "
            f"--profiles-dir {DBT_DIR} "
            f"--profile-target dev"
        ),
        trigger_rule=TriggerRule.ALL_DONE,
    )

    bronze_tasks >> dbt_deps >> dbt_run >> dbt_test >> dbt_source_freshness >> edr_report
