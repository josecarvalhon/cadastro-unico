"""Empresa A — Rede de Varejo (PostgreSQL).

Gera INSERTs SQL para as tabelas clientes e fornecedores. O arquivo de saída
é carregado automaticamente quando o container postgres-empresa-a sobe pela
primeira vez (montado em /docker-entrypoint-initdb.d/).
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from _common import format_cnpj, format_cpf, load_or_build_universe, sampling_plan

OUTPUT = Path(__file__).resolve().parents[2] / "infra" / "postgres" / "seed.sql"


def _esc(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _data_cadastro_aleatoria() -> date:
    return date.today() - timedelta(days=random.randint(0, 1095))


def _insert(table: str, row: dict) -> str:
    cols = ", ".join(row.keys())
    vals = ", ".join(_esc(str(v)) if not isinstance(v, (int, float)) and v is not None else (str(v) if v is not None else "NULL") for v in row.values())
    return f"INSERT INTO {table} ({cols}) VALUES ({vals});"


def _row_from_pf(p: dict) -> dict:
    end = p["endereco"]
    return {
        "tipo_pessoa": "PF",
        "nome_razao_social": p["nome"],
        "cpf_cnpj": format_cpf(p["cpf"]),
        "endereco_rua": end["rua"],
        "endereco_numero": end["numero"],
        "endereco_bairro": end["bairro"],
        "endereco_cidade": end["cidade"],
        "endereco_uf": end["uf"],
        "endereco_cep": end["cep"],
        "telefone_principal": p["telefone"],
        "email": p["email"],
        "data_cadastro": _data_cadastro_aleatoria().isoformat(),
        "status": random.choices(["ativo", "inativo"], weights=[9, 1])[0],
    }


def _row_from_pj(j: dict) -> dict:
    end = j["endereco"]
    return {
        "tipo_pessoa": "PJ",
        "nome_razao_social": j["razao_social"],
        "cpf_cnpj": format_cnpj(j["cnpj"]),
        "endereco_rua": end["rua"],
        "endereco_numero": end["numero"],
        "endereco_bairro": end["bairro"],
        "endereco_cidade": end["cidade"],
        "endereco_uf": end["uf"],
        "endereco_cep": end["cep"],
        "telefone_principal": j["telefone"],
        "email": j["email"],
        "data_cadastro": _data_cadastro_aleatoria().isoformat(),
        "status": random.choices(["ativo", "inativo"], weights=[9, 1])[0],
    }


def main() -> None:
    universe = load_or_build_universe()
    plan = sampling_plan(universe)["empresa_a"]

    sql_lines: list[str] = [
        "-- Seed Empresa A — gerado por scripts/generate/empresa_a.py",
        "SET client_encoding = 'UTF8';",
        "BEGIN;",
    ]

    for pf in plan["clientes_pf"]:
        sql_lines.append(_insert("clientes", _row_from_pf(pf)))
    for pj in plan["clientes_pj"]:
        sql_lines.append(_insert("clientes", _row_from_pj(pj)))
    for pj in plan["fornecedores_pj"]:
        sql_lines.append(_insert("fornecedores", _row_from_pj(pj)))

    sql_lines.append("COMMIT;")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(sql_lines), encoding="utf-8")
    print(f"Empresa A: {len(plan['clientes_pf']) + len(plan['clientes_pj'])} clientes + {len(plan['fornecedores_pj'])} fornecedores -> {OUTPUT}")


if __name__ == "__main__":
    main()
