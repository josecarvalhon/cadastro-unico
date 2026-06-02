"""Utilitários compartilhados pelos conectores Bronze.

Responsabilidades:
  - cliente MinIO configurado
  - escrita de Parquet com metadados de ingestão (_source, _ingested_at, _batch_id)
  - organização particionada por empresa/tipo/ano/mês
  - logging consistente
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable

import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from ingest.config import MINIO

logger = logging.getLogger("bronze")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def get_minio() -> Minio:
    """Devolve um cliente MinIO conectado ao endpoint configurado."""
    return Minio(
        MINIO.endpoint,
        access_key=MINIO.access_key,
        secret_key=MINIO.secret_key,
        secure=MINIO.secure,
    )


def new_batch_id() -> str:
    """Identificador único do lote de ingestão (UUID4)."""
    return str(uuid.uuid4())


def add_metadata_columns(
    rows: list[dict],
    *,
    source: str,
    batch_id: str,
    ingested_at: datetime | None = None,
) -> list[dict]:
    """Anexa metadados de ingestão a cada registro. Não muta os originais."""
    ts = (ingested_at or datetime.now(timezone.utc)).isoformat()
    enriched: list[dict] = []
    for r in rows:
        enriched.append({**r, "_source": source, "_ingested_at": ts, "_batch_id": batch_id})
    return enriched


def write_parquet_to_minio(
    rows: list[dict],
    *,
    source: str,
    cadastro_tipo: str,
    batch_id: str,
    ingested_at: datetime | None = None,
) -> str:
    """Serializa as linhas como Parquet em memória e envia ao MinIO.

    Layout: bronze/{source}/{cadastro_tipo}/year=YYYY/month=MM/{batch_id}.parquet
    """
    ts = ingested_at or datetime.now(timezone.utc)
    enriched = add_metadata_columns(rows, source=source, batch_id=batch_id, ingested_at=ts)

    if not enriched:
        logger.warning("Nada para escrever em %s/%s", source, cadastro_tipo)
        return ""

    table = pa.Table.from_pylist(enriched)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    size = buf.getbuffer().nbytes

    object_path = (
        f"bronze/{source}/{cadastro_tipo}/"
        f"year={ts.year}/month={ts.month:02d}/"
        f"{batch_id}.parquet"
    )

    client = get_minio()
    try:
        client.put_object(
            MINIO.bucket,
            object_path,
            buf,
            length=size,
            content_type="application/octet-stream",
        )
    except S3Error as e:
        logger.error("Falha ao escrever %s: %s", object_path, e)
        raise

    logger.info("%s/%s: %d registros (%d bytes) -> %s", source, cadastro_tipo, len(enriched), size, object_path)
    return object_path


def list_bronze_objects(prefix: str = "bronze/") -> list[str]:
    """Lista objetos no bucket sob o prefixo dado (para verificação)."""
    client = get_minio()
    return [obj.object_name for obj in client.list_objects(MINIO.bucket, prefix=prefix, recursive=True)]


def read_parquet_from_minio(object_path: str) -> pa.Table:
    """Lê de volta um Parquet — útil para verificação."""
    client = get_minio()
    resp = client.get_object(MINIO.bucket, object_path)
    try:
        return pq.read_table(io.BytesIO(resp.read()))
    finally:
        resp.close()
        resp.release_conn()


def normalize_columns(rows: Iterable[dict]) -> list[dict]:
    """Garante que todas as linhas tenham as mesmas chaves (None onde ausente).

    PyArrow exige schema homogêneo; dados de Mongo/CSV podem ter chaves
    diferentes entre registros.
    """
    rows = list(rows)
    if not rows:
        return rows
    all_keys: set[str] = set()
    for r in rows:
        all_keys.update(r.keys())
    return [{k: r.get(k) for k in all_keys} for r in rows]
