"""Bronze: Empresa D (CSV legado).

Lê os dois CSVs gerados pelo gerador da Empresa D. A Bronze preserva o
conteúdo exatamente como veio — espaços extras, maiúsculas, formatos
inconsistentes. Toda a limpeza fica para a Prata.
"""
from __future__ import annotations

import pandas as pd

from ingest.bronze._common import logger, new_batch_id, normalize_columns, write_parquet_to_minio
from ingest.config import EMPRESA_D

SOURCE = "empresa_d"


def _extract(arquivo: str) -> list[dict]:
    df = pd.read_csv(EMPRESA_D.seed_dir / arquivo, dtype=str, keep_default_na=False)
    return df.to_dict(orient="records")


def run() -> dict[str, str]:
    batch_id = new_batch_id()
    logger.info("Iniciando ingestão %s (batch=%s)", SOURCE, batch_id)
    paths: dict[str, str] = {}
    for arquivo, tipo in (("clientes.csv", "clientes"), ("fornecedores.csv", "fornecedores")):
        rows = normalize_columns(_extract(arquivo))
        paths[tipo] = write_parquet_to_minio(
            rows, source=SOURCE, cadastro_tipo=tipo, batch_id=batch_id
        )
    return paths


if __name__ == "__main__":
    run()
