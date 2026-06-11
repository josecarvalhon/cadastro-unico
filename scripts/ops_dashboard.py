"""Painel operacional do Cadastro Único.

Coleta o estado de 13 cenários de falha (infra, orquestração, pipeline) e
renderiza um HTML estático em `docs/operacional.html`. Sem servidor, sem
dependência nova — usa só libs que já estão em requirements.txt.

Cada check tem try/except próprio: uma checagem que falha vira card cinza
('unknown') sem derrubar o painel inteiro. Timeouts curtos (3s) garantem
que o painel gera em <15s mesmo com várias coisas mortas.

Uso:
    python scripts/ops_dashboard.py
    python scripts/ops_dashboard.py --output /tmp/x.html --auto-refresh --print
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import duckdb
import requests
from minio import Minio
from minio.error import S3Error

# Sobe um nível para que `ingest.config` resolva.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest.config import EMPRESA_A, EMPRESA_B, EMPRESA_C, EMPRESA_E, MINIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DUCKDB_PATH = PROJECT_ROOT / "dbt" / "cadastro_unico.duckdb"
EDR_REPORT_PATH = PROJECT_ROOT / "docs" / "elementary_report.html"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "operacional.html"

TIMEOUT_S = 3
AIRFLOW_CONTAINER = "cu-airflow"
AIRFLOW_HEALTH_URL = "http://localhost:8080/api/v1/health"
FASTAPI_HEALTH_URL = "http://localhost:8000/health"
MINIO_HEALTH_URL = f"http://{MINIO.endpoint}/minio/health/live"
MOCK_API_URL = f"{EMPRESA_E.base_url}/health"
DAG_ID = "cadastro_unico_etl"


@dataclass
class Check:
    name: str
    category: str
    status: str  # ok | warn | error | unknown
    detail: str
    suggested_action: str
    checked_at: datetime


def _safe(name: str, category: str, fn: Callable[[], tuple[str, str, str]]) -> Check:
    """Roda uma checagem capturando qualquer exceção como 'unknown'."""
    try:
        status, detail, action = fn()
    except Exception as e:
        status, detail, action = "unknown", f"erro na coleta: {e}", ""
    return Check(
        name=name,
        category=category,
        status=status,
        detail=detail,
        suggested_action=action,
        checked_at=datetime.now(timezone.utc),
    )


# ---------- Categoria: Infra ----------

DC_RESTART = "docker compose -f infra/docker-compose.yml restart"


def check_minio() -> tuple[str, str, str]:
    t0 = time.monotonic()
    try:
        r = requests.get(MINIO_HEALTH_URL, timeout=TIMEOUT_S)
    except requests.ConnectionError:
        return "error", f"sem resposta na porta {MINIO.endpoint.split(':')[-1]}", f"{DC_RESTART} minio"
    ms = int((time.monotonic() - t0) * 1000)
    if r.status_code == 200:
        return "ok", f"healthcheck respondeu em {ms}ms", ""
    return "error", f"healthcheck devolveu HTTP {r.status_code}", f"{DC_RESTART} minio"


def check_postgres_a() -> tuple[str, str, str]:
    import psycopg2
    t0 = time.monotonic()
    try:
        conn = psycopg2.connect(
            host=EMPRESA_A.host, port=EMPRESA_A.port, user=EMPRESA_A.user,
            password=EMPRESA_A.password, dbname=EMPRESA_A.database,
            connect_timeout=TIMEOUT_S,
        )
    except psycopg2.OperationalError as e:
        return "error", f"conexão recusada na porta {EMPRESA_A.port}", f"{DC_RESTART} postgres-empresa-a"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
    ms = int((time.monotonic() - t0) * 1000)
    return "ok", f"SELECT 1 em {ms}ms", ""


def check_mysql_b() -> tuple[str, str, str]:
    import mysql.connector  # type: ignore
    from mysql.connector.errors import InterfaceError, DatabaseError  # type: ignore
    t0 = time.monotonic()
    try:
        conn = mysql.connector.connect(
            host=EMPRESA_B.host, port=EMPRESA_B.port, user=EMPRESA_B.user,
            password=EMPRESA_B.password, database=EMPRESA_B.database,
            connection_timeout=TIMEOUT_S,
        )
    except (InterfaceError, DatabaseError):
        return "error", f"conexão recusada na porta {EMPRESA_B.port}", f"{DC_RESTART} mysql-empresa-b"
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
    finally:
        conn.close()
    ms = int((time.monotonic() - t0) * 1000)
    return "ok", f"SELECT 1 em {ms}ms", ""


def check_mongo_c() -> tuple[str, str, str]:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    t0 = time.monotonic()
    client = MongoClient(
        host=EMPRESA_C.host, port=EMPRESA_C.port,
        username=EMPRESA_C.user, password=EMPRESA_C.password,
        authSource=EMPRESA_C.auth_source,
        serverSelectionTimeoutMS=TIMEOUT_S * 1000,
    )
    try:
        try:
            client.admin.command("ping")
        except (ConnectionFailure, ServerSelectionTimeoutError):
            return "error", f"sem resposta na porta {EMPRESA_C.port}", f"{DC_RESTART} mongo-empresa-c"
    finally:
        client.close()
    ms = int((time.monotonic() - t0) * 1000)
    return "ok", f"ping em {ms}ms", ""


def check_mock_api_e() -> tuple[str, str, str]:
    t0 = time.monotonic()
    try:
        r = requests.get(MOCK_API_URL, timeout=TIMEOUT_S)
    except requests.ConnectionError:
        return "error", f"sem resposta em {MOCK_API_URL}", f"{DC_RESTART} mock-api-empresa-e"
    ms = int((time.monotonic() - t0) * 1000)
    if r.status_code == 200:
        return "ok", f"/health em {ms}ms", ""
    return "error", f"/health devolveu HTTP {r.status_code}", f"{DC_RESTART} mock-api-empresa-e"


# ---------- Categoria: Orquestração ----------

def check_airflow_scheduler() -> tuple[str, str, str]:
    try:
        r = requests.get(AIRFLOW_HEALTH_URL, timeout=TIMEOUT_S)
    except requests.ConnectionError:
        return "error", "sem resposta na porta 8080", f"{DC_RESTART} airflow"
    if r.status_code != 200:
        return "error", f"/api/v1/health devolveu HTTP {r.status_code}", f"{DC_RESTART} airflow"
    body = r.json()
    sched = body.get("scheduler", {}).get("status")
    db = body.get("metadatabase", {}).get("status")
    if sched == "healthy" and db == "healthy":
        return "ok", f"scheduler={sched}, metadatabase={db}", ""
    return "error", f"scheduler={sched}, metadatabase={db}", f"{DC_RESTART} airflow"


def _airflow_cli(args: list[str], timeout: int = 10) -> str:
    """Roda `airflow <args>` dentro do container e devolve stdout."""
    out = subprocess.run(
        ["docker", "exec", AIRFLOW_CONTAINER, "airflow", *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"airflow {' '.join(args)} falhou: {out.stderr.strip()[:200]}")
    return out.stdout


def check_dag_enabled() -> tuple[str, str, str]:
    raw = _airflow_cli(["dags", "list", "--output", "json"])
    dags = json.loads(raw)
    target = next((d for d in dags if d.get("dag_id") == DAG_ID), None)
    if not target:
        return "error", f"DAG {DAG_ID} não encontrada", (
            "verifique se airflow/dags/cadastro_unico_etl.py está no volume do container"
        )
    paused = str(target.get("paused", "")).lower() in ("true", "1")
    if paused:
        return "warn", "DAG está pausada (não roda no schedule)", (
            f"docker exec {AIRFLOW_CONTAINER} airflow dags unpause {DAG_ID}"
        )
    return "ok", "DAG ativa, schedule @daily", ""


def check_last_dag_run() -> tuple[str, str, str]:
    raw = _airflow_cli(["dags", "list-runs", "-d", DAG_ID, "--output", "json"])
    runs = json.loads(raw)
    if not runs:
        return "warn", "nenhuma execução registrada ainda", "make airflow-trigger"
    runs.sort(key=lambda r: r.get("start_date") or "", reverse=True)
    last = runs[0]
    state = last.get("state", "?")
    start = last.get("start_date", "?")
    try:
        delta_h = (datetime.now(timezone.utc) - datetime.fromisoformat(start)).total_seconds() / 3600
        age = f"há {delta_h:.1f}h"
    except Exception:
        age = f"start_date={start}"
    if state == "success":
        if delta_h > 36:
            return "warn", f"última run success, mas {age} (esperado @daily)", "make airflow-trigger"
        return "ok", f"última run: success {age}", ""
    if state in ("running", "queued"):
        return "ok", f"última run: {state} {age}", ""
    return "error", f"última run: {state} {age}", "make airflow-trigger"


def check_failed_tasks_last_run() -> tuple[str, str, str]:
    raw = _airflow_cli(["dags", "list-runs", "-d", DAG_ID, "--output", "json"])
    runs = json.loads(raw)
    if not runs:
        return "ok", "sem runs históricas — nada a auditar", ""
    runs.sort(key=lambda r: r.get("start_date") or "", reverse=True)
    last = runs[0]
    if last.get("state") in ("running", "queued"):
        return "ok", "última run ainda em andamento", ""
    run_id = last["run_id"]
    raw_t = _airflow_cli(["tasks", "states-for-dag-run", DAG_ID, run_id, "--output", "json"])
    tasks = json.loads(raw_t)
    failed = [t["task_id"] for t in tasks if t.get("state") == "failed"]
    if not failed:
        return "ok", f"{len(tasks)} tasks, 0 falhas", ""
    return "error", f"tasks falhadas: {', '.join(failed)}", (
        f"docker exec {AIRFLOW_CONTAINER} airflow tasks clear {DAG_ID} -r {run_id} -y"
    )


# ---------- Categoria: Pipeline ----------

def check_bronze_freshness() -> tuple[str, str, str]:
    if not DUCKDB_PATH.exists():
        return "warn", "cadastro_unico.duckdb ainda não existe", "make dbt-run"
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # Pior status do batch mais recente por source.
        rows = con.sql("""
            WITH ranked AS (
              SELECT unique_id, status, generated_at,
                     ROW_NUMBER() OVER (PARTITION BY unique_id ORDER BY generated_at DESC) rn
              FROM main_elementary.dbt_source_freshness_results
            )
            SELECT status, COUNT(*) FROM ranked WHERE rn = 1 GROUP BY status
        """).fetchall()
    finally:
        con.close()
    if not rows:
        return "warn", "sem checagens de freshness registradas", (
            "cd dbt && DBT_PROFILES_DIR=. dbt source freshness"
        )
    by_status = dict(rows)
    pass_n = by_status.get("pass", 0)
    warn_n = by_status.get("warn", 0)
    err_n = by_status.get("error", 0) + by_status.get("runtime_error", 0)
    summary = f"{pass_n} pass, {warn_n} warn, {err_n} error"
    if err_n:
        return "error", summary, "verifique ingestões Bronze em atraso: make ingest-bronze"
    if warn_n:
        return "warn", summary, "make ingest-bronze"
    return "ok", summary, ""


def check_edr_report_age() -> tuple[str, str, str]:
    if not EDR_REPORT_PATH.exists():
        return "warn", "docs/elementary_report.html ainda não foi gerado", "make monitor"
    mtime = datetime.fromtimestamp(EDR_REPORT_PATH.stat().st_mtime, tz=timezone.utc)
    age_h = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
    if age_h > 36:
        return "warn", f"última geração há {age_h:.1f}h (alvo: diário)", "make monitor"
    return "ok", f"gerado há {age_h:.1f}h", ""


def check_bronze_quarantine() -> tuple[str, str, str]:
    # Pré-flight: se MinIO já não responde, evita stack trace do minio-py.
    try:
        requests.get(MINIO_HEALTH_URL, timeout=TIMEOUT_S)
    except requests.ConnectionError:
        return "warn", "indisponível (MinIO fora do ar)", ""
    client = Minio(
        MINIO.endpoint, access_key=MINIO.access_key,
        secret_key=MINIO.secret_key, secure=MINIO.secure,
    )
    try:
        objs = list(client.list_objects(MINIO.bucket, prefix="bronze/_quarantine/", recursive=True))
    except S3Error as e:
        return "warn", f"bucket inacessível: {e.code}", ""
    if not objs:
        return "ok", "sem batches em quarentena", ""
    return "warn", f"{len(objs)} batches em quarentena", (
        f"mc ls minio/{MINIO.bucket}/bronze/_quarantine/ "
        "(investigar e remover após reprocessar)"
    )


def check_fastapi_health() -> tuple[str, str, str]:
    t0 = time.monotonic()
    try:
        r = requests.get(FASTAPI_HEALTH_URL, timeout=TIMEOUT_S)
    except requests.ConnectionError:
        return "warn", "API desligada (porta 8000 não responde)", "make api-run"
    ms = int((time.monotonic() - t0) * 1000)
    if r.status_code != 200:
        return "warn", f"/health respondeu HTTP {r.status_code}", "make api-run"
    body = r.json()
    clientes = body.get("clientes")
    fornecedores = body.get("fornecedores")
    return "ok", f"{clientes} clientes, {fornecedores} fornecedores ({ms}ms)", ""


# ---------- Orquestrador de checks ----------

CHECKS = [
    ("MinIO",              "Infra",         check_minio),
    ("PostgreSQL (A)",     "Infra",         check_postgres_a),
    ("MySQL (B)",          "Infra",         check_mysql_b),
    ("MongoDB (C)",        "Infra",         check_mongo_c),
    ("Mock API (E)",       "Infra",         check_mock_api_e),
    ("Airflow scheduler",  "Orquestração",  check_airflow_scheduler),
    ("DAG habilitada",     "Orquestração",  check_dag_enabled),
    ("Última DAG run",     "Orquestração",  check_last_dag_run),
    ("Tasks falhadas",     "Orquestração",  check_failed_tasks_last_run),
    ("Freshness Bronze",   "Pipeline",      check_bronze_freshness),
    ("Elementary report",  "Pipeline",      check_edr_report_age),
    ("Quarentena Bronze",  "Pipeline",      check_bronze_quarantine),
    ("FastAPI /health",    "Pipeline",      check_fastapi_health),
]


def run_all() -> list[Check]:
    return [_safe(name, cat, fn) for name, cat, fn in CHECKS]


# ---------- Renderização ----------

STATUS_COLOR = {
    "ok":      "#10b981",  # verde
    "warn":    "#f59e0b",  # amarelo
    "error":   "#ef4444",  # vermelho
    "unknown": "#6b7280",  # cinza
}

STATUS_LABEL = {
    "ok": "OK", "warn": "WARN", "error": "ERROR", "unknown": "?",
}


def render_html(checks: list[Check], auto_refresh: bool) -> str:
    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    by_status = {s: sum(1 for c in checks if c.status == s) for s in ("ok", "warn", "error", "unknown")}
    by_cat: dict[str, list[Check]] = {}
    for c in checks:
        by_cat.setdefault(c.category, []).append(c)

    refresh_meta = '<meta http-equiv="refresh" content="60">' if auto_refresh else ""

    def card(c: Check) -> str:
        color = STATUS_COLOR[c.status]
        label = STATUS_LABEL[c.status]
        action = (
            f'<div class="action"><span class="action-label">Ação sugerida:</span>'
            f'<code>{_h(c.suggested_action)}</code></div>'
        ) if c.suggested_action else ""
        return f"""
        <div class="card" style="border-left-color: {color};">
          <div class="card-head">
            <span class="dot" style="background:{color};"></span>
            <span class="name">{_h(c.name)}</span>
            <span class="badge" style="background:{color};">{label}</span>
          </div>
          <div class="detail">{_h(c.detail)}</div>
          {action}
        </div>"""

    sections = ""
    for cat in ("Infra", "Orquestração", "Pipeline"):
        items = by_cat.get(cat, [])
        if not items:
            continue
        cards = "".join(card(c) for c in items)
        sections += f'<h2>{_h(cat)} <span class="cat-count">({len(items)})</span></h2><div class="grid">{cards}</div>'

    edr_link = ""
    if EDR_REPORT_PATH.exists():
        edr_link = ' · <a href="elementary_report.html">📊 Relatório Elementary</a>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
{refresh_meta}
<title>Painel Operacional — Cadastro Único</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         margin: 0; padding: 24px 32px; background: #f5f6f8; color: #1a1d24; }}
  header {{ display: flex; justify-content: space-between; align-items: baseline;
            margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid #d9dde3; }}
  h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
  .ts {{ color: #6b7280; font-size: 13px; }}
  .summary {{ margin: 0 0 24px; display: flex; gap: 12px; flex-wrap: wrap; }}
  .pill {{ padding: 4px 12px; border-radius: 14px; font-weight: 600; color: #fff; font-size: 13px; }}
  h2 {{ font-size: 15px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
        color: #4b5563; margin: 24px 0 12px; }}
  .cat-count {{ color: #9ca3af; font-weight: 400; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border: 1px solid #e5e7eb; border-left: 4px solid #6b7280;
           border-radius: 6px; padding: 14px 16px; }}
  .card-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .name {{ font-weight: 600; flex: 1; }}
  .badge {{ color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .detail {{ color: #4b5563; font-size: 13px; }}
  .action {{ margin-top: 10px; padding: 8px 10px; background: #f3f4f6; border-radius: 4px;
             font-size: 12px; }}
  .action-label {{ color: #6b7280; margin-right: 6px; }}
  .action code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                  background: transparent; word-break: break-all; }}
  footer {{ margin-top: 32px; padding-top: 12px; border-top: 1px solid #d9dde3;
            color: #6b7280; font-size: 12px; }}
  footer a {{ color: #2563eb; text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>Painel Operacional · Cadastro Único</h1>
  <span class="ts">gerado em {_h(ts)}</span>
</header>
<div class="summary">
  <span class="pill" style="background:{STATUS_COLOR['ok']}">{by_status['ok']} OK</span>
  <span class="pill" style="background:{STATUS_COLOR['warn']}">{by_status['warn']} WARN</span>
  <span class="pill" style="background:{STATUS_COLOR['error']}">{by_status['error']} ERROR</span>
  <span class="pill" style="background:{STATUS_COLOR['unknown']}">{by_status['unknown']} ?</span>
</div>
{sections}
<footer>Auto-refresh: {"sim, a cada 60s" if auto_refresh else "não — recarregue a página manualmente"}{edr_link}</footer>
</body>
</html>"""


def _h(s: str) -> str:
    """Escape HTML básico."""
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def render_ascii(checks: list[Check]) -> str:
    lines = []
    for cat in ("Infra", "Orquestração", "Pipeline"):
        items = [c for c in checks if c.category == cat]
        if not items:
            continue
        lines.append(f"\n[{cat}]")
        for c in items:
            sym = {"ok": "✓", "warn": "!", "error": "✗", "unknown": "?"}[c.status]
            lines.append(f"  {sym} {c.name:<24} {c.detail}")
            if c.suggested_action:
                lines.append(f"      → {c.suggested_action}")
    by_status = {s: sum(1 for c in checks if c.status == s) for s in ("ok", "warn", "error", "unknown")}
    lines.append(
        f"\nResumo: {by_status['ok']} OK · {by_status['warn']} WARN · "
        f"{by_status['error']} ERROR · {by_status['unknown']} ?"
    )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Painel operacional do Cadastro Único.")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="caminho do HTML")
    p.add_argument("--auto-refresh", action="store_true", help="adiciona meta refresh de 60s")
    p.add_argument("--print", dest="print_ascii", action="store_true", help="também imprime tabela ASCII")
    args = p.parse_args()

    checks = run_all()
    html = render_html(checks, auto_refresh=args.auto_refresh)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"→ Painel gerado em {args.output}")
    if args.print_ascii:
        print(render_ascii(checks))
    # Exit 0 sempre — painel é informativo, não bloqueante.
    return 0


if __name__ == "__main__":
    sys.exit(main())
