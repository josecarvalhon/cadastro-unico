"""Bronze: Empresa B (MySQL)."""
from __future__ import annotations

from datetime import date, datetime

import mysql.connector

from ingest.bronze._common import logger, new_batch_id, normalize_columns, write_parquet_to_minio
from ingest.config import EMPRESA_B

SOURCE = "empresa_b"


def _serialize(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        out.append({k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in r.items()})
    return out


def _extract() -> list[dict]:
    conn = mysql.connector.connect(
        host=EMPRESA_B.host,
        port=EMPRESA_B.port,
        user=EMPRESA_B.user,
        password=EMPRESA_B.password,
        database=EMPRESA_B.database,
    )
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM clients ORDER BY client_id")
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return _serialize(rows)


def run() -> dict[str, str]:
    batch_id = new_batch_id()
    logger.info("Iniciando ingestão %s (batch=%s)", SOURCE, batch_id)
    rows = normalize_columns(_extract())
    return {
        "clientes": write_parquet_to_minio(
            rows, source=SOURCE, cadastro_tipo="clientes", batch_id=batch_id
        )
    }


if __name__ == "__main__":
    run()
