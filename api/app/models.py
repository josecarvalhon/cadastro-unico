"""Schemas Pydantic de resposta da API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Endereco(BaseModel):
    cidade: str | None = None
    uf: str | None = None
    fonte: str | None = None


class EntidadeResumo(BaseModel):
    """Versão resumida usada em listagens (buscas)."""

    id_golden: str
    nome_razao_social: str | None
    cpf_cnpj: str | None
    cpf_cnpj_kind: str | None
    tipo_pessoa: str | None
    emails: list[str] = Field(default_factory=list)
    telefones: list[str] = Field(default_factory=list)
    enderecos: list[Endereco] = Field(default_factory=list)
    fontes: list[str] = Field(default_factory=list)
    total_fontes: int
    score_completude: float


class AtributosPorFonte(BaseModel):
    fonte: str
    atributos: dict[str, Any] | str | None = None


class EntidadeDetalhe(EntidadeResumo):
    """Versão completa para /entidade/{id}."""

    metodos_match: list[str] = Field(default_factory=list)
    ids_origem: dict[str, str] = Field(default_factory=dict)
    atributos_por_fonte: list[AtributosPorFonte] = Field(default_factory=list)
    primeira_aparicao: datetime | None = None
    ultima_atualizacao: datetime | None = None
    versao: int = 1


class PaginatedResult(BaseModel):
    total: int
    page: int
    per_page: int
    has_next: bool
    data: list[EntidadeResumo]
