"""Fixtures compartilhadas para os testes do pipeline."""

from pathlib import Path

import pytest

from pipeline.parsers.base import ParsedRecord

# Raiz do monorepo (dois níveis acima de pipeline/tests/)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def repo_root() -> Path:
    """Caminho absoluto para a raiz do monorepo."""
    return REPO_ROOT


@pytest.fixture
def sources_yml_path() -> Path:
    """Caminho para sources.yml na raiz do monorepo."""
    return REPO_ROOT / "sources.yml"


@pytest.fixture
def areas_dir() -> Path:
    """Caminho para o diretório areas/."""
    return REPO_ROOT / "areas"


@pytest.fixture
def schema_dir() -> Path:
    """Diretório contendo os schemas JSON (raiz do repositório / schema)."""
    return REPO_ROOT / "schema"


@pytest.fixture
def sample_parsed_record() -> ParsedRecord:
    """Registro sintético básico para testes."""
    return ParsedRecord(
        issn="1234-5678",
        issn_alt="8765-4321",
        doi="10.1145/1234567",
        titulo="Journal of Synthetic Testing",
        metricas={
            "sjr_quartil": "Q1",
            "sjr_valor": 3.45,
        },
    )


@pytest.fixture
def sample_parsed_record_minimal() -> ParsedRecord:
    """Registro sintético com dados mínimos (apenas ISSN e uma métrica)."""
    return ParsedRecord(
        issn="2345-6789",
        issn_alt=None,
        doi=None,
        titulo=None,
        metricas={"sjr_quartil": "Q2"},
    )


@pytest.fixture
def sample_parsed_record_no_issn() -> ParsedRecord:
    """Registro sintético sem ISSN (necessita enriquecimento)."""
    return ParsedRecord(
        issn=None,
        issn_alt=None,
        doi="10.1000/xyz123",
        titulo="Journal of Synthetic Testing",
        metricas={"abdc_rating": "B"},
    )


@pytest.fixture
def sample_area_rules() -> dict:
    """Regras de área sintéticas mínimas para testes do motor."""
    return {
        "area": 99,
        "nome": "Área de Teste",
        "vigencia": "2025-2028",
        "status": "experimental",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4"],
            "pontos": {"A1": 4, "A2": 3, "A3": 2, "A4": 1},
        },
        "veiculos": {
            "journalArticle": {
                "combinacao": "metrica_unica",
                "metrica": "test_percentil",
                "regras": [
                    {"min": 75, "resultado": "A1"},
                    {"min": 50, "max": 75, "resultado": "A2"},
                    {"min": 25, "max": 50, "resultado": "A3"},
                    {"min": 0, "max": 25, "resultado": "A4"},
                ],
                "ajustes": [],
                "fallback": "NAO_CLASSIFICAVEL",
            }
        },
    }
