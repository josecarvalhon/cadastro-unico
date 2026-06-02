"""Empresa D — Operações Legadas (Excel/CSV).

Gera arquivos CSV "bagunçados" simulando planilhas manuais antigas:
  - colunas com nomes inconsistentes (Nome / NOME / Cliente)
  - endereço em uma única coluna concatenada
  - CPF e CNPJ misturados na mesma coluna "Documento"
  - erros de digitação propositais (espaços extras, acentuação inconsistente,
    telefones em formatos variados)
  - duplicatas óbvias e duplicatas sutis (mesmo titular com pequenas variações)
  - linhas com campos faltando
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

from _common import deaccent, format_cnpj, format_cpf, load_or_build_universe, sampling_plan

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "seed" / "empresa_d"


def _phone_dirty(phone_e164: str) -> str:
    """Devolve o telefone em formatos variados, como humano digitaria."""
    ddd = phone_e164[2:4]
    numero = phone_e164[4:]
    return random.choice(
        [
            f"({ddd}) {numero[:5]}-{numero[5:]}",
            f"{ddd} {numero}",
            f"{ddd}{numero}",
            f"+55 ({ddd}) {numero[:5]}-{numero[5:]}",
            f"{numero[:5]}-{numero[5:]}",  # sem DDD
        ]
    )


def _maybe_typo(text: str) -> str:
    """Pequenas inconsistências: maiúsculas, sem acento, espaço extra."""
    r = random.random()
    if r < 0.2:
        return text.upper()
    if r < 0.35:
        return deaccent(text)
    if r < 0.5:
        return f"  {text} "
    return text


def _row_pf(pf: dict) -> dict:
    end = pf["endereco"]
    endereco_concat = f"{end['rua']}, {end['numero']} - {end['bairro']}, {end['cidade']} - {end['uf']}"
    return {
        "Nome": _maybe_typo(pf["nome"]),
        "Documento": format_cpf(pf["cpf"]) if random.random() > 0.2 else pf["cpf"],  # com ou sem máscara
        "Fone": _phone_dirty(pf["telefone"]),
        "Email": pf["email"] if random.random() > 0.15 else "",  # alguns vazios
        "Endereco": endereco_concat,
        "Obs": random.choice(["", "", "", "Cliente VIP", "Atualizar contato", "Conferir endereço"]),
    }


def _row_pj(pj: dict) -> dict:
    end = pj["endereco"]
    endereco_concat = f"{end['rua']}, {end['numero']} - {end['bairro']}, {end['cidade']} - {end['uf']}"
    return {
        "Nome": _maybe_typo(pj["razao_social"]),
        "Documento": format_cnpj(pj["cnpj"]) if random.random() > 0.3 else pj["cnpj"],
        "Fone": _phone_dirty(pj["telefone"]),
        "Email": pj["email"] if random.random() > 0.25 else "",
        "Endereco": endereco_concat,
        "Obs": random.choice(["", "", "Fornecedor", "FORN", "fornecedor preferencial"]),
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["Nome", "Documento", "Fone", "Email", "Endereco", "Obs"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    universe = load_or_build_universe()
    plan = sampling_plan(universe)["empresa_d"]

    clientes_rows = [_row_pf(pf) for pf in plan["clientes_pf"]]
    # Injeta umas 4 duplicatas óbvias (mesma linha repetida).
    if clientes_rows:
        clientes_rows += random.sample(clientes_rows, k=min(4, len(clientes_rows)))

    fornecedores_rows = [_row_pj(pj) for pj in plan["fornecedores_pj"]]
    if fornecedores_rows:
        fornecedores_rows += random.sample(fornecedores_rows, k=min(3, len(fornecedores_rows)))

    random.shuffle(clientes_rows)
    random.shuffle(fornecedores_rows)

    _write_csv(OUTPUT_DIR / "clientes.csv", clientes_rows)
    _write_csv(OUTPUT_DIR / "fornecedores.csv", fornecedores_rows)
    print(f"Empresa D: {len(clientes_rows)} clientes + {len(fornecedores_rows)} fornecedores -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
