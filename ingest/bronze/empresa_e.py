"""Bronze: Empresa E (API REST).

Consome a mock-API paginada, respeitando rate limit (100 req/min). Implementa
backoff simples para 429.
"""
from __future__ import annotations

import json
import time

import requests

from ingest.bronze._common import logger, new_batch_id, normalize_columns, write_parquet_to_minio
from ingest.config import EMPRESA_E

SOURCE = "empresa_e"


def _serialize(record: dict) -> dict:
    """Achata: address (dict) e tags (list) viram JSON-string para Parquet."""
    out: dict = {}
    for k, v in record.items():
        if isinstance(v, (dict, list)):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    return out


def _fetch_page(page: int) -> dict:
    url = f"{EMPRESA_E.base_url}/api/v1/customers"
    params = {"page": page, "per_page": EMPRESA_E.per_page}
    for attempt in range(5):
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 429:
            wait = 2 ** attempt
            logger.warning("Rate limit; aguardando %ds...", wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Excesso de 429 consecutivos.")


def _extract() -> list[dict]:
    page = 1
    rows: list[dict] = []
    while True:
        payload = _fetch_page(page)
        rows.extend(_serialize(r) for r in payload["data"])
        if not payload["has_next"]:
            break
        page += 1
    return rows


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
