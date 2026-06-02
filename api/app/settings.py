"""Configurações da API de busca."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    minio_endpoint: str = _env("MINIO_ENDPOINT", "localhost:9002")
    minio_access_key: str = _env("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = _env("MINIO_SECRET_KEY", "minioadmin")
    minio_use_ssl: bool = _env("MINIO_SECURE", "false").lower() == "true"

    bucket: str = _env("MINIO_BUCKET", "lakehouse")
    duckdb_path: str = _env("API_DUCKDB_PATH", ":memory:")

    # Limites de paginação
    max_per_page: int = int(_env("API_MAX_PER_PAGE", "100"))
    default_per_page: int = int(_env("API_DEFAULT_PER_PAGE", "25"))


settings = Settings()
