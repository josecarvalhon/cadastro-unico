"""Configurações centralizadas dos conectores de ingestão.

Valores padrão batem com o docker-compose. Tudo é overridable via variável
de ambiente — o mesmo código vai rodar no container do Airflow no futuro.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str = _env("MINIO_ENDPOINT", "localhost:9002")
    access_key: str = _env("MINIO_ACCESS_KEY", "minioadmin")
    secret_key: str = _env("MINIO_SECRET_KEY", "minioadmin")
    bucket: str = _env("MINIO_BUCKET", "lakehouse")
    secure: bool = _env("MINIO_SECURE", "false").lower() == "true"


@dataclass(frozen=True)
class EmpresaAConfig:
    host: str = _env("PG_A_HOST", "localhost")
    port: int = int(_env("PG_A_PORT", "5433"))
    user: str = _env("PG_A_USER", "empresa_a")
    password: str = _env("PG_A_PASSWORD", "empresa_a")
    database: str = _env("PG_A_DATABASE", "varejo")


@dataclass(frozen=True)
class EmpresaBConfig:
    host: str = _env("MYSQL_B_HOST", "localhost")
    port: int = int(_env("MYSQL_B_PORT", "3306"))
    user: str = _env("MYSQL_B_USER", "empresa_b")
    password: str = _env("MYSQL_B_PASSWORD", "empresa_b")
    database: str = _env("MYSQL_B_DATABASE", "servicos_digitais")


@dataclass(frozen=True)
class EmpresaCConfig:
    host: str = _env("MONGO_C_HOST", "localhost")
    port: int = int(_env("MONGO_C_PORT", "27017"))
    user: str = _env("MONGO_C_USER", "empresa_c")
    password: str = _env("MONGO_C_PASSWORD", "empresa_c")
    database: str = _env("MONGO_C_DATABASE", "industria")
    auth_source: str = _env("MONGO_C_AUTH_SOURCE", "admin")


@dataclass(frozen=True)
class EmpresaDConfig:
    seed_dir: Path = Path(_env("EMPRESA_D_DIR", str(Path(__file__).resolve().parents[1] / "data" / "seed" / "empresa_d")))


@dataclass(frozen=True)
class EmpresaEConfig:
    base_url: str = _env("EMPRESA_E_URL", "http://localhost:8081")
    per_page: int = int(_env("EMPRESA_E_PER_PAGE", "25"))


MINIO = MinioConfig()
EMPRESA_A = EmpresaAConfig()
EMPRESA_B = EmpresaBConfig()
EMPRESA_C = EmpresaCConfig()
EMPRESA_D = EmpresaDConfig()
EMPRESA_E = EmpresaEConfig()
