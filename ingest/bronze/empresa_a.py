"""Bronze: Empresa A (PostgreSQL).

Extrai full-load das tabelas clientes e fornecedores, converte cada linha em
dict (já tipado), e grava dois Parquets distintos no MinIO.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

import psycopg2
from psycopg2.extras import RealDictCursor

from ingest.bronze._common import logger, new_batch_id, normalize_columns, write_parquet_to_minio
from ingest.config import EMPRESA_A

SOURCE = "empresa_a"


def _connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=EMPRESA_A.host,
        port=EMPRESA_A.port,
        user=EMPRESA_A.user,
        password=EMPRESA_A.password,
        dbname=EMPRESA_A.database,
    )


def _serialize(rows: Iterable[dict]) -> list[dict]:
    """Converte tipos não-Parquet-nativos (date, datetime) em string ISO."""
    out: list[dict] = []
    for r in rows:
        clean: dict = {}
        for k, v in r.items():
            if isinstance(v, (datetime, date)):
                clean[k] = v.isoformat()
            else:
                clean[k] = v
        out.append(clean)
    return out


def _extract(table: str) -> list[dict]:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM {table} ORDER BY id")
        rows = cur.fetchall()
    return _serialize(rows)


def run() -> dict[str, str]:
    batch_id = new_batch_id()
    logger.info("Iniciando ingestão %s (batch=%s)", SOURCE, batch_id)

    paths: dict[str, str] = {}
    for tabela, tipo in (("clientes", "clientes"), ("fornecedores", "fornecedores")):
        rows = normalize_columns(_extract(tabela))
        paths[tipo] = write_parquet_to_minio(
            rows, source=SOURCE, cadastro_tipo=tipo, batch_id=batch_id
        )
    return paths


if __name__ == "__main__":
    run()
