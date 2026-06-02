"""Empresa B — Serviços Digitais (MySQL).

Gera INSERTs SQL para a tabela `clients`. CRM digital — só PF, sem endereço
nem CPF, com foco em canais sociais.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

from _common import load_or_build_universe, sampling_plan

OUTPUT = Path(__file__).resolve().parents[2] / "infra" / "mysql" / "seed.sql"

CHANNELS = ["email", "whatsapp", "instagram", "twitter"]


def _esc(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _row(pf: dict) -> str:
    signup = date.today() - timedelta(days=random.randint(0, 720))
    last_active = datetime.combine(signup, datetime.min.time()) + timedelta(
        days=random.randint(0, (date.today() - signup).days or 1),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    cols = [
        "full_name",
        "email",
        "phone",
        "instagram_handle",
        "twitter_handle",
        "facebook_url",
        "preferred_channel",
        "signup_date",
        "last_active",
    ]
    vals = [
        _esc(pf["nome"]),
        _esc(pf["email"]),
        _esc(pf["telefone"]),
        _esc(pf["instagram"]) if random.random() > 0.1 else "NULL",
        _esc(pf["twitter"]) if random.random() > 0.4 else "NULL",
        _esc(f"https://facebook.com/{pf['instagram'].lstrip('@')}") if random.random() > 0.6 else "NULL",
        _esc(random.choice(CHANNELS)),
        _esc(signup.isoformat()),
        _esc(last_active.strftime("%Y-%m-%d %H:%M:%S")),
    ]
    return f"INSERT INTO clients ({', '.join(cols)}) VALUES ({', '.join(vals)});"


def main() -> None:
    universe = load_or_build_universe()
    plan = sampling_plan(universe)["empresa_b"]

    sql_lines = [
        "-- Seed Empresa B — gerado por scripts/generate/empresa_b.py",
        "SET NAMES utf8mb4;",
        "START TRANSACTION;",
    ]
    for pf in plan["clientes_pf"]:
        sql_lines.append(_row(pf))
    sql_lines.append("COMMIT;")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(sql_lines), encoding="utf-8")
    print(f"Empresa B: {len(plan['clientes_pf'])} clientes -> {OUTPUT}")


if __name__ == "__main__":
    main()
