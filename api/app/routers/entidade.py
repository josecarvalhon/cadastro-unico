from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.app.models import EntidadeDetalhe
from api.app.search import detalhar

router = APIRouter(prefix="/api/v1/entidade", tags=["entidade"])


@router.get("/{id_golden}", response_model=EntidadeDetalhe)
def detalhar_entidade(id_golden: str) -> EntidadeDetalhe:
    """Resolve um id_golden em qualquer um dos dois cadastros (cliente ou fornecedor).

    Útil quando o consumidor só tem o ID e não sabe a categoria.
    """
    for view in ("golden_clientes", "golden_fornecedores"):
        result = detalhar(view, id_golden)
        if result is not None:
            return result
    raise HTTPException(status_code=404, detail="Entidade não encontrada em nenhum cadastro.")
