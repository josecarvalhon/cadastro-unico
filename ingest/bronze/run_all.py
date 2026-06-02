"""Roda os 5 conectores Bronze em sequência.

Uso:
    python -m ingest.bronze.run_all
"""
from __future__ import annotations

from ingest.bronze import empresa_a, empresa_b, empresa_c, empresa_d, empresa_e
from ingest.bronze._common import list_bronze_objects, logger


def main() -> None:
    resultados: dict[str, dict[str, str]] = {}
    for mod in (empresa_a, empresa_b, empresa_c, empresa_d, empresa_e):
        resultados[mod.SOURCE] = mod.run()

    logger.info("Ingestão Bronze concluída.")
    objetos = list_bronze_objects()
    logger.info("Total de objetos no bucket: %d", len(objetos))
    for o in objetos:
        logger.info("  - %s", o)


if __name__ == "__main__":
    main()
