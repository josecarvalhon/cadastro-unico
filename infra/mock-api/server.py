"""Mock REST API que simula a Empresa E (startup de tecnologia).

Lê o arquivo JSON gerado em data/seed/empresa_e/clientes.json e expõe
endpoints paginados em /api/v1/customers com rate limiting simples.
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request

DATA_FILE = Path("/data/seed/empresa_e/clientes.json")
RATE_LIMIT_PER_MIN = 100

app = FastAPI(title="Empresa E — Mock API", version="1.0.0")

_request_timestamps: deque[float] = deque()


def _enforce_rate_limit() -> None:
    now = time.time()
    while _request_timestamps and now - _request_timestamps[0] > 60:
        _request_timestamps.popleft()
    if len(_request_timestamps) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit excedido (100 req/min).")
    _request_timestamps.append(now)


def _load_clientes() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "total_clientes": len(_load_clientes())}


@app.get("/api/v1/customers")
def list_customers(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
) -> dict:
    _enforce_rate_limit()
    clientes = _load_clientes()
    total = len(clientes)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_next": end < total,
        "data": clientes[start:end],
    }


@app.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id: str) -> dict:
    _enforce_rate_limit()
    for c in _load_clientes():
        if c.get("id") == customer_id:
            return c
    raise HTTPException(status_code=404, detail="Cliente não encontrado.")
