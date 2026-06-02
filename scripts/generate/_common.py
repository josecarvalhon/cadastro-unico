"""Pool central de entidades sintéticas compartilhadas entre as fontes.

Estratégia: gera um universo de pessoas (PF) e empresas (PJ) com identificadores
válidos. Esse universo é a "verdade" — depois cada fonte sorteia um subconjunto
desse universo, criando intersecções (duplicatas) entre subsidiárias. Sem
intersecções, a deduplicação na camada Ouro não teria o que fazer.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from faker import Faker

SEED = 42
fake = Faker("pt_BR")
Faker.seed(SEED)
random.seed(SEED)

# Tamanho do universo total. Cada fonte sorteia ~100 desse pool com sobreposição.
UNIVERSE_PF_SIZE = 220
UNIVERSE_PJ_SIZE = 180


# ---------------------------------------------------------------------------
# Validação CPF / CNPJ — dígitos verificadores corretos.
# ---------------------------------------------------------------------------
def _cpf_digits() -> str:
    base = [random.randint(0, 9) for _ in range(9)]

    def dv(nums: list[int], weights: range) -> int:
        s = sum(n * w for n, w in zip(nums, weights))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    d1 = dv(base, range(10, 1, -1))
    d2 = dv(base + [d1], range(11, 1, -1))
    return "".join(map(str, base + [d1, d2]))


def _cnpj_digits() -> str:
    base = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]

    def dv(nums: list[int]) -> int:
        weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        s = sum(n * w for n, w in zip(nums, weights[-len(nums) :]))
        r = s % 11
        return 0 if r < 2 else 11 - r

    d1 = dv(base)
    d2 = dv(base + [d1])
    return "".join(map(str, base + [d1, d2]))


def format_cpf(d: str) -> str:
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def format_cnpj(d: str) -> str:
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def strip_punct(doc: str) -> str:
    return re.sub(r"\D", "", doc)


def deaccent(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Entidades do universo
# ---------------------------------------------------------------------------
@dataclass
class Endereco:
    rua: str
    numero: str
    bairro: str
    cidade: str
    uf: str
    cep: str

    @property
    def completo(self) -> str:
        return f"{self.rua}, {self.numero} - {self.bairro}, {self.cidade}/{self.uf} - CEP {self.cep}"


@dataclass
class PessoaFisica:
    uid: str  # identificador interno (não vai para nenhuma fonte)
    nome: str
    cpf: str  # somente dígitos
    email: str
    telefone: str  # E.164 sem formatação: 5561999990000
    endereco: Endereco
    instagram: str
    twitter: str


@dataclass
class PessoaJuridica:
    uid: str
    razao_social: str
    nome_fantasia: str
    cnpj: str  # somente dígitos
    email: str
    telefone: str
    endereco: Endereco
    contato_nome: str
    contato_telefone: str
    contato_email: str
    certificacoes: list[str] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)


def _endereco() -> Endereco:
    return Endereco(
        rua=fake.street_name(),
        numero=str(random.randint(1, 9999)),
        bairro=fake.bairro(),
        cidade=fake.city(),
        uf=fake.estado_sigla(),
        cep=re.sub(r"\D", "", fake.postcode()),
    )


def _telefone() -> str:
    ddd = random.choice([11, 21, 31, 41, 51, 61, 71, 81, 85, 92])
    numero = random.randint(900000000, 999999999)
    return f"55{ddd}{numero}"


def _handle(nome: str) -> str:
    base = re.sub(r"\W+", "", deaccent(nome).lower())[:15]
    return f"{base}{random.randint(1, 99)}"


CERTIFICACOES = ["ISO9001", "ISO14001", "ISO27001", "ISO45001", "PBQP-H", "ABNT-NBR-15575"]
CATEGORIAS = ["matéria-prima", "embalagens", "logística", "TI", "manutenção", "serviços jurídicos", "química"]


def build_pessoa_fisica(uid: str) -> PessoaFisica:
    nome = fake.name()
    handle = re.sub(r"\W+", ".", deaccent(nome).lower()).strip(".")
    return PessoaFisica(
        uid=uid,
        nome=nome,
        cpf=_cpf_digits(),
        email=f"{handle}@{fake.free_email_domain()}",
        telefone=_telefone(),
        endereco=_endereco(),
        instagram=f"@{_handle(nome)}",
        twitter=f"@{_handle(nome)}",
    )


def build_pessoa_juridica(uid: str) -> PessoaJuridica:
    razao = fake.company()
    contato = fake.name()
    dominio = re.sub(r"\W+", "", deaccent(razao).lower())[:20]
    contato_handle = re.sub(r"\W+", ".", deaccent(contato).lower()).strip(".")
    return PessoaJuridica(
        uid=uid,
        razao_social=razao,
        nome_fantasia=razao.split()[0],
        cnpj=_cnpj_digits(),
        email=f"contato@{dominio}.com.br",
        telefone=_telefone(),
        endereco=_endereco(),
        contato_nome=contato,
        contato_telefone=_telefone(),
        contato_email=f"{contato_handle}@{dominio}.com.br",
        certificacoes=random.sample(CERTIFICACOES, k=random.randint(0, 3)),
        categorias=random.sample(CATEGORIAS, k=random.randint(1, 3)),
    )


# ---------------------------------------------------------------------------
# Persistência do universo (gerado uma vez, reaproveitado por todas as fontes)
# ---------------------------------------------------------------------------
UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "_universe.json"


def build_universe() -> dict:
    """Gera o universo determinístico. Idempotente graças à seed fixa."""
    pf = [asdict(build_pessoa_fisica(f"pf-{i:04d}")) for i in range(UNIVERSE_PF_SIZE)]
    pj = [asdict(build_pessoa_juridica(f"pj-{i:04d}")) for i in range(UNIVERSE_PJ_SIZE)]
    return {"pf": pf, "pj": pj}


def load_or_build_universe() -> dict:
    if UNIVERSE_PATH.exists():
        with UNIVERSE_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    universe = build_universe()
    UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with UNIVERSE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(universe, fh, ensure_ascii=False, indent=2)
    return universe


# ---------------------------------------------------------------------------
# Amostragem com sobreposição controlada entre fontes
# ---------------------------------------------------------------------------
# Define manualmente quais entidades aparecem em quais fontes. Isso garante
# duplicatas reais e cobertura previsível para a deduplicação na camada Ouro.
#
# Distribuição-alvo (100 registros por fonte):
#   Empresa A (varejo)       : PF 60  + PJ 40  (clientes PF/PJ e fornecedores)
#   Empresa B (digital)      : PF 100
#   Empresa C (indústria)    : PJ 100 (só fornecedores)
#   Empresa D (legado)       : PF 50  + PJ 50 (misto, com baixa qualidade)
#   Empresa E (startup API)  : PF 70  + PJ 30
#
# Sobreposições propositais:
#   - ~25 PFs aparecem em A + B + E (clientes do grupo)
#   - ~15 PJs aparecem em A + C (fornecedores compartilhados)
#   - ~10 entidades aparecem em D + outra (duplicata "suja" vs "limpa")
def sampling_plan(universe: dict) -> dict[str, dict[str, list[dict]]]:
    pf = universe["pf"]
    pj = universe["pj"]

    pf_shared_abe = pf[:25]
    pf_a_only = pf[25:60]
    pf_b_only = pf[60:135]
    pf_e_only = pf[135:180]
    pf_d_dirty = pf[180:220]  # 40 PFs em D, com 10 sobrepondo

    pj_shared_ac = pj[:15]
    pj_a_only = pj[15:40]
    pj_c_only = pj[:100]   # C reaproveita os 15 compartilhados com A + 85 exclusivos = 100
    pj_d_dirty = pj[100:150]
    pj_e_only = pj[150:180]

    return {
        "empresa_a": {
            "clientes_pf": pf_shared_abe[:15] + pf_a_only[:25],          # 40 PF
            "clientes_pj": pj_a_only[:20],                                # 20 PJ clientes
            "fornecedores_pj": pj_shared_ac + pj_a_only[20:25],           # 20 PJ fornecedores
        },
        "empresa_b": {
            "clientes_pf": pf_shared_abe + pf_b_only,                     # ~100 PF
        },
        "empresa_c": {
            "fornecedores_pj": pj_c_only,                                 # 100 PJ
        },
        "empresa_d": {
            "clientes_pf": pf_d_dirty[:30] + pf_shared_abe[:20],          # 50 PF (mistura)
            "fornecedores_pj": pj_d_dirty + pj_shared_ac[:5],             # ~55 PJ (mistura)
        },
        "empresa_e": {
            "clientes_pf": pf_shared_abe[:20] + pf_e_only + pf_b_only[:5],# ~70 PF
            "clientes_pj": pj_e_only,                                     # 30 PJ
        },
    }
