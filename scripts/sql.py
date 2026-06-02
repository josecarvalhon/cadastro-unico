"""Abre um shell DuckDB já conectado ao MinIO com views pré-registradas.

Uso:
    python scripts/sql.py              # REPL interativo
    python scripts/sql.py -c "SELECT count(*) FROM golden_clientes;"
    python scripts/sql.py -f query.sql # roda um arquivo

Views disponíveis no REPL:
    bronze_all                 -- união de todos os Parquets Bronze
    stg_empresa_a_clientes     -- staging Prata (por fonte)
    stg_empresa_a_fornecedores
    stg_empresa_b_clientes
    stg_empresa_c_fornecedores
    stg_empresa_d_clientes
    stg_empresa_d_fornecedores
    stg_empresa_e_clientes
    int_clientes_padronizados  -- Prata unificada
    int_fornecedores_padronizados
    int_clientes_cluster       -- Ouro com cluster_key
    int_fornecedores_cluster
    golden_clientes            -- Ouro final
    golden_fornecedores
    metricas_qualidade
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9002")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
BUCKET = os.environ.get("MINIO_BUCKET", "lakehouse")

PRATA_MODELS = [
    "stg_empresa_a_clientes",
    "stg_empresa_a_fornecedores",
    "stg_empresa_b_clientes",
    "stg_empresa_c_fornecedores",
    "stg_empresa_d_clientes",
    "stg_empresa_d_fornecedores",
    "stg_empresa_e_clientes",
    "int_clientes_padronizados",
    "int_fornecedores_padronizados",
]
OURO_MODELS = [
    "int_clientes_cluster",
    "int_fornecedores_cluster",
    "golden_clientes",
    "golden_fornecedores",
    "metricas_qualidade",
]


def open_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(
        """
        CREATE OR REPLACE SECRET minio_secret (
          TYPE S3, KEY_ID ?, SECRET ?, ENDPOINT ?, URL_STYLE 'path', USE_SSL false
        )
        """,
        [MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ENDPOINT],
    )

    # Bronze como view única (union_by_name lida com schemas diferentes)
    con.execute(
        f"""
        CREATE OR REPLACE VIEW bronze_all AS
        SELECT * FROM read_parquet('s3://{BUCKET}/bronze/**/*.parquet', union_by_name=true)
        """
    )
    for name in PRATA_MODELS:
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM read_parquet('s3://{BUCKET}/prata/{name}.parquet')"
        )
    for name in OURO_MODELS:
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM read_parquet('s3://{BUCKET}/ouro/{name}.parquet')"
        )
    return con


def run_query(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    try:
        result = con.execute(sql)
        df = result.fetchdf()
        if df.empty:
            print("(0 linhas)")
        else:
            print(df.to_string(index=False))
            print(f"({len(df)} linhas)")
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)


def repl(con: duckdb.DuckDBPyConnection) -> None:
    print("Cadastro Único — Shell SQL (DuckDB → MinIO)")
    print(f"Endpoint: {MINIO_ENDPOINT}  •  Bucket: {BUCKET}")
    print("Views: bronze_all, stg_*, int_*, golden_*, metricas_qualidade")
    print('Digite SQL terminado em ";". \\q para sair, \\d para listar views.')
    buffer: list[str] = []
    while True:
        try:
            prompt = "sql> " if not buffer else "  -> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return
        stripped = line.strip()
        if not buffer and stripped in ("\\q", "exit", "quit"):
            return
        if not buffer and stripped == "\\d":
            for v in ["bronze_all"] + PRATA_MODELS + OURO_MODELS:
                print(f"  - {v}")
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            sql = "\n".join(buffer)
            buffer.clear()
            run_query(con, sql)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-c", "--command", help="Roda uma query única e sai")
    parser.add_argument("-f", "--file", help="Roda o conteúdo de um arquivo .sql e sai")
    args = parser.parse_args()

    con = open_connection()
    if args.command:
        run_query(con, args.command)
    elif args.file:
        run_query(con, Path(args.file).read_text(encoding="utf-8"))
    else:
        repl(con)


if __name__ == "__main__":
    main()
