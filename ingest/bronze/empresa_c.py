"""Bronze: Empresa C (MongoDB).

Documentos têm schema flexível e campos aninhados (endereço como subdoc,
arrays de certificações). Para preservar fidelidade na Bronze, serializamos
subdocs/arrays como string JSON — a normalização (achatar/explodir) acontece
na camada Prata.
"""
from __future__ import annotations

import json

from pymongo import MongoClient

from ingest.bronze._common import logger, new_batch_id, normalize_columns, write_parquet_to_minio
from ingest.config import EMPRESA_C

SOURCE = "empresa_c"


def _serialize(doc: dict) -> dict:
    """Achata o nível superior: campos escalares ficam como estão; subdocs e
    arrays viram strings JSON. Isso garante schema homogêneo no Parquet."""
    out: dict = {}
    for k, v in doc.items():
        if isinstance(v, (dict, list)):
            out[k] = json.dumps(v, ensure_ascii=False, default=str)
        else:
            out[k] = v
    return out


def _extract() -> list[dict]:
    client = MongoClient(
        host=EMPRESA_C.host,
        port=EMPRESA_C.port,
        username=EMPRESA_C.user,
        password=EMPRESA_C.password,
        authSource=EMPRESA_C.auth_source,
    )
    try:
        coll = client[EMPRESA_C.database]["fornecedores"]
        return [_serialize(doc) for doc in coll.find({})]
    finally:
        client.close()


def run() -> dict[str, str]:
    batch_id = new_batch_id()
    logger.info("Iniciando ingestão %s (batch=%s)", SOURCE, batch_id)
    rows = normalize_columns(_extract())
    return {
        "fornecedores": write_parquet_to_minio(
            rows, source=SOURCE, cadastro_tipo="fornecedores", batch_id=batch_id
        )
    }


if __name__ == "__main__":
    run()
