"""FastAPI app do Cadastro Único — endpoints de busca sobre a camada Ouro."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app.db import get_connection
from api.app.routers import clientes, entidade, fornecedores

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_connection()  # aquece a conexão e valida que os Parquets estão acessíveis
    yield


app = FastAPI(
    title="Cadastro Único — API de Busca",
    version="1.0.0",
    description=(
        "Endpoints para consulta da visão unificada de clientes e fornecedores "
        "(camada Ouro). Lê Parquets do MinIO via DuckDB embarcado."
    ),
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    cur = get_connection().cursor()
    n_cli = cur.execute("SELECT COUNT(*) FROM golden_clientes").fetchone()[0]
    n_for = cur.execute("SELECT COUNT(*) FROM golden_fornecedores").fetchone()[0]
    return {"status": "ok", "clientes": n_cli, "fornecedores": n_for}


@app.get("/api/v1/metricas", tags=["meta"])
def metricas() -> list[dict]:
    cur = get_connection().cursor()
    cols = [d[0] for d in cur.execute("SELECT * FROM metricas_qualidade LIMIT 0").description]
    rows = cur.execute("SELECT * FROM metricas_qualidade ORDER BY tipo_cadastro, fonte").fetchall()
    return [dict(zip(cols, r)) for r in rows]


app.include_router(clientes.router)
app.include_router(fornecedores.router)
app.include_router(entidade.router)
