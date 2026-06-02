"""Empresa E — Startup de Tecnologia (API REST).

Gera o arquivo JSON consumido pela mock-API (infra/mock-api/server.py). O
formato segue o que uma API SaaS bem desenhada exporia: tudo aninhado,
documentos identificados por UUID externo, datas em ISO 8601.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import format_cnpj, format_cpf, load_or_build_universe, sampling_plan

OUTPUT = Path(__file__).resolve().parents[2] / "data" / "seed" / "empresa_e" / "clientes.json"

TAGS = ["beta-tester", "enterprise", "self-serve", "trial", "churn-risk", "advocate", "newsletter"]


def _ts(days_ago_max: int = 720) -> str:
    delta = timedelta(days=random.randint(0, days_ago_max), seconds=random.randint(0, 86400))
    return (datetime.now(timezone.utc) - delta).isoformat()


def _pf_record(pf: dict) -> dict:
    created = _ts(720)
    return {
        "id": str(uuid.UUID(int=random.getrandbits(128))),
        "type": "individual",
        "name": pf["nome"],
        "document": format_cpf(pf["cpf"]),
        "email": pf["email"],
        "phone": f"+{pf['telefone']}",
        "address": {
            "street": pf["endereco"]["rua"],
            "number": pf["endereco"]["numero"],
            "neighborhood": pf["endereco"]["bairro"],
            "city": pf["endereco"]["cidade"],
            "state": pf["endereco"]["uf"],
            "postal_code": pf["endereco"]["cep"],
            "country": "BR",
        },
        "tags": random.sample(TAGS, k=random.randint(0, 3)),
        "created_at": created,
        "updated_at": _ts(min(720, max(1, (datetime.now(timezone.utc) - datetime.fromisoformat(created)).days))),
    }


def _pj_record(pj: dict) -> dict:
    created = _ts(720)
    return {
        "id": str(uuid.UUID(int=random.getrandbits(128))),
        "type": "business",
        "name": pj["razao_social"],
        "document": format_cnpj(pj["cnpj"]),
        "email": pj["email"],
        "phone": f"+{pj['telefone']}",
        "address": {
            "street": pj["endereco"]["rua"],
            "number": pj["endereco"]["numero"],
            "neighborhood": pj["endereco"]["bairro"],
            "city": pj["endereco"]["cidade"],
            "state": pj["endereco"]["uf"],
            "postal_code": pj["endereco"]["cep"],
            "country": "BR",
        },
        "tags": random.sample(TAGS, k=random.randint(0, 2)),
        "created_at": created,
        "updated_at": _ts(min(720, max(1, (datetime.now(timezone.utc) - datetime.fromisoformat(created)).days))),
    }


def main() -> None:
    universe = load_or_build_universe()
    plan = sampling_plan(universe)["empresa_e"]

    records: list[dict] = []
    records.extend(_pf_record(pf) for pf in plan["clientes_pf"])
    records.extend(_pj_record(pj) for pj in plan["clientes_pj"])
    random.shuffle(records)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"Empresa E: {len(records)} clientes -> {OUTPUT}")


if __name__ == "__main__":
    main()
