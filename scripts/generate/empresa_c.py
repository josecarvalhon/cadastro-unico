"""Empresa C — Indústria (MongoDB).

Gera um arquivo NDJSON (uma linha por documento) com schema flexível: nem
todos os fornecedores têm os mesmos campos, alguns têm subdocumentos
aninhados (endereço, dados bancários) e arrays (certificações, categorias).

A carga no MongoDB é feita posteriormente via mongoimport ou um script de
seed dedicado.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from _common import format_cnpj, load_or_build_universe, sampling_plan

OUTPUT = Path(__file__).resolve().parents[2] / "data" / "seed" / "empresa_c" / "fornecedores.ndjson"


def _build_doc(j: dict) -> dict:
    end = j["endereco"]
    doc: dict = {
        "_id": f"forn_{j['uid']}",
        "razao_social": j["razao_social"],
        "cnpj": format_cnpj(j["cnpj"]),
        "contato_nome": j["contato_nome"],
        "contato_telefone": j["contato_telefone"],
        "contato_email": j["contato_email"],
        "categorias": j["categorias"],
        "avaliacao_media": round(random.uniform(2.5, 5.0), 2),
        "data_cadastro": (date.today() - timedelta(days=random.randint(0, 1500))).isoformat(),
    }

    # Schema flexível: certas chaves só aparecem em parte dos documentos.
    if random.random() > 0.2:
        doc["certificacoes"] = j["certificacoes"]
    if random.random() > 0.15:
        doc["endereco"] = {
            "logradouro": end["rua"],
            "numero": end["numero"],
            "bairro": end["bairro"],
            "cidade": end["cidade"],
            "uf": end["uf"],
            "cep": end["cep"],
        }
    if random.random() > 0.4:
        doc["dados_bancarios"] = {
            "banco": random.choice(["001 - BB", "104 - CEF", "237 - Bradesco", "341 - Itaú", "260 - Nubank"]),
            "agencia": f"{random.randint(1, 9999):04d}",
            "conta": f"{random.randint(10000, 99999)}-{random.randint(0, 9)}",
            "tipo": random.choice(["corrente", "poupança"]),
        }
    if random.random() > 0.7:
        doc["observacoes"] = "Fornecedor preferencial." if random.random() > 0.5 else "Em homologação."
    return doc


def main() -> None:
    universe = load_or_build_universe()
    plan = sampling_plan(universe)["empresa_c"]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as fh:
        for j in plan["fornecedores_pj"]:
            fh.write(json.dumps(_build_doc(j), ensure_ascii=False) + "\n")
    print(f"Empresa C: {len(plan['fornecedores_pj'])} fornecedores -> {OUTPUT}")


if __name__ == "__main__":
    main()
