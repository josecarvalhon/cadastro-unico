"""Roda os geradores das 5 fontes em sequência.

Uso:
    python scripts/generate_all.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "generate"
sys.path.insert(0, str(ROOT))

MODULES = ["empresa_a", "empresa_b", "empresa_c", "empresa_d", "empresa_e"]


def main() -> None:
    for name in MODULES:
        mod = importlib.import_module(name)
        mod.main()
    print("\nTodos os geradores rodaram com sucesso.")


if __name__ == "__main__":
    main()
