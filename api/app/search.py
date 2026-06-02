"""Lógica compartilhada entre /clientes/buscar e /fornecedores/buscar."""
from __future__ import annotations

import re
from typing import Any

from api.app.db import cursor
from api.app.models import Endereco, EntidadeDetalhe, EntidadeResumo, PaginatedResult


_DOC_RE = re.compile(r"[^0-9]")


def _clean_doc(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _DOC_RE.sub("", value)
    return cleaned or None


def _row_to_resumo(row: tuple) -> EntidadeResumo:
    (
        id_golden, nome, cpf_cnpj, kind, tipo_pessoa,
        emails, telefones, enderecos, fontes, total_fontes, score,
    ) = row
    return EntidadeResumo(
        id_golden=id_golden,
        nome_razao_social=nome,
        cpf_cnpj=cpf_cnpj,
        cpf_cnpj_kind=kind,
        tipo_pessoa=tipo_pessoa,
        emails=list(emails or []),
        telefones=list(telefones or []),
        enderecos=[Endereco(**dict(e)) for e in (enderecos or [])],
        fontes=list(fontes or []),
        total_fontes=total_fontes,
        score_completude=float(score),
    )


_BASE_SELECT = """
    id_golden,
    nome_razao_social,
    cpf_cnpj,
    cpf_cnpj_kind,
    tipo_pessoa,
    emails,
    telefones,
    enderecos,
    fontes,
    total_fontes,
    score_completude
"""


def buscar(
    *,
    view: str,
    q: str | None = None,
    doc: str | None = None,
    email: str | None = None,
    telefone: str | None = None,
    cidade: str | None = None,
    uf: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> PaginatedResult:
    """Busca paginada na view Ouro indicada.

    Filtros opcionais combinam com AND. Strings de texto usam ILIKE %valor%;
    documento é normalizado para só dígitos e casa por igualdade exata.
    """
    where: list[str] = []
    params: list[Any] = []

    if q:
        where.append("nome_razao_social ILIKE ?")
        params.append(f"%{q}%")
    if doc and (cleaned := _clean_doc(doc)):
        where.append("cpf_cnpj = ?")
        params.append(cleaned)
    if email:
        where.append("len(list_filter(emails, x -> x ILIKE ?)) > 0")
        params.append(f"%{email.lower()}%")
    if telefone and (digits := _clean_doc(telefone)):
        where.append("len(list_filter(telefones, x -> x ILIKE ?)) > 0")
        params.append(f"%{digits}%")
    if cidade:
        where.append("len(list_filter(enderecos, x -> x.cidade ILIKE ?)) > 0")
        params.append(f"%{cidade}%")
    if uf:
        where.append("len(list_filter(enderecos, x -> x.uf = ?)) > 0")
        params.append(uf.upper())

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * per_page

    cur = cursor()
    total = cur.execute(f"SELECT COUNT(*) FROM {view}{where_sql}", params).fetchone()[0]
    rows = cur.execute(
        f"""
        SELECT {_BASE_SELECT}
        FROM {view}{where_sql}
        ORDER BY score_completude DESC, nome_razao_social
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    ).fetchall()

    return PaginatedResult(
        total=total,
        page=page,
        per_page=per_page,
        has_next=(offset + per_page) < total,
        data=[_row_to_resumo(r) for r in rows],
    )


def detalhar(view: str, id_golden: str) -> EntidadeDetalhe | None:
    """Detalhes completos por id_golden."""
    cur = cursor()
    row = cur.execute(
        f"""
        SELECT
          id_golden,
          nome_razao_social,
          cpf_cnpj,
          cpf_cnpj_kind,
          tipo_pessoa,
          emails,
          telefones,
          enderecos,
          fontes,
          total_fontes,
          score_completude,
          metodos_match,
          ids_origem,
          atributos_por_fonte,
          primeira_aparicao,
          ultima_atualizacao,
          versao
        FROM {view}
        WHERE id_golden = ?
        """,
        [id_golden],
    ).fetchone()
    if row is None:
        return None

    resumo = _row_to_resumo(row[:11])
    (
        _id_golden, _nome, _doc, _kind, _tp, _emails, _telefones, _enderecos,
        _fontes, _total, _score,
        metodos_match, ids_origem, atributos_por_fonte,
        primeira, ultima, versao,
    ) = row

    return EntidadeDetalhe(
        **resumo.model_dump(),
        metodos_match=list(metodos_match or []),
        ids_origem=dict(ids_origem or {}),
        atributos_por_fonte=[
            {"fonte": a["fonte"], "atributos": a["atributos"]}
            for a in (atributos_por_fonte or [])
        ],
        primeira_aparicao=primeira,
        ultima_atualizacao=ultima,
        versao=versao,
    )
