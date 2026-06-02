"""Conexão DuckDB compartilhada pela API.

Cria uma conexão única no startup, com extensão httpfs e secret S3 para o
MinIO, e registra views sobre os Parquets da camada Ouro. Cada request usa
`con.cursor()` para isolamento — DuckDB é seguro para cursores concorrentes
sobre a mesma conexão.
"""
from __future__ import annotations

import logging
from threading import Lock

import duckdb

from api.app.settings import settings

logger = logging.getLogger("api.db")

_con: duckdb.DuckDBPyConnection | None = None
_lock = Lock()


def _build_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(settings.duckdb_path)
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(
        """
        CREATE OR REPLACE SECRET minio_secret (
          TYPE S3,
          KEY_ID ?,
          SECRET ?,
          ENDPOINT ?,
          URL_STYLE 'path',
          USE_SSL ?
        )
        """,
        [
            settings.minio_access_key,
            settings.minio_secret_key,
            settings.minio_endpoint,
            settings.minio_use_ssl,
        ],
    )

    base = f"s3://{settings.bucket}/ouro"
    con.execute(f"CREATE OR REPLACE VIEW golden_clientes AS SELECT * FROM read_parquet('{base}/golden_clientes.parquet')")
    con.execute(f"CREATE OR REPLACE VIEW golden_fornecedores AS SELECT * FROM read_parquet('{base}/golden_fornecedores.parquet')")
    con.execute(f"CREATE OR REPLACE VIEW metricas_qualidade AS SELECT * FROM read_parquet('{base}/metricas_qualidade.parquet')")

    n_cli = con.execute("SELECT COUNT(*) FROM golden_clientes").fetchone()[0]
    n_for = con.execute("SELECT COUNT(*) FROM golden_fornecedores").fetchone()[0]
    logger.info("DuckDB pronto: %d clientes, %d fornecedores carregados.", n_cli, n_for)
    return con


def get_connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        with _lock:
            if _con is None:
                _con = _build_connection()
    return _con


def cursor() -> duckdb.DuckDBPyConnection:
    """Retorna um cursor isolado para a request atual."""
    return get_connection().cursor()
