from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.app.models import EntidadeDetalhe, PaginatedResult
from api.app.search import buscar, detalhar
from api.app.settings import settings

router = APIRouter(prefix="/api/v1/fornecedores", tags=["fornecedores"])


@router.get("/buscar", response_model=PaginatedResult)
def buscar_fornecedores(
    q: str | None = Query(None, description="Texto buscado em razão social (ILIKE)"),
    doc: str | None = Query(None, description="CNPJ; pontuação opcional"),
    email: str | None = Query(None),
    telefone: str | None = Query(None),
    cidade: str | None = Query(None),
    uf: str | None = Query(None, min_length=2, max_length=2),
    page: int = Query(1, ge=1),
    per_page: int = Query(settings.default_per_page, ge=1, le=settings.max_per_page),
) -> PaginatedResult:
    return buscar(
        view="golden_fornecedores",
        q=q, doc=doc, email=email, telefone=telefone,
        cidade=cidade, uf=uf, page=page, per_page=per_page,
    )


@router.get("/{id_golden}", response_model=EntidadeDetalhe)
def detalhar_fornecedor(id_golden: str) -> EntidadeDetalhe:
    result = detalhar("golden_fornecedores", id_golden)
    if result is None:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    return result
