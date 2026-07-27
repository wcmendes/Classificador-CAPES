"""Testes para pipeline/sources.py — resolução de métricas via sources.yml.

Testa:
- Métricas da area02-computacao.json são resolvíveis via sources.yml
- Métricas da area27-administracao.json são resolvíveis via sources.yml
- Área sintética com métrica desconhecida → reporta órfã
- sources.yml com provides faltando para métrica conhecida → reporta
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.sources import (
    extract_metrics_from_area,
    find_orphan_metrics,
    get_all_provided_metrics,
    load_sources,
    validate_all_areas,
)

# Raiz do monorepo
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sources_path() -> Path:
    return REPO_ROOT / "sources.yml"


@pytest.fixture
def areas_dir() -> Path:
    return REPO_ROOT / "areas"


@pytest.fixture
def area02_rules(areas_dir: Path) -> dict:
    with open(areas_dir / "area02-computacao.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def area27_rules(areas_dir: Path) -> dict:
    with open(areas_dir / "area27-administracao.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sources(sources_path: Path) -> dict[str, list[str]]:
    return load_sources(sources_path)


# ---------------------------------------------------------------------------
# Testes de integração com arquivos reais
# ---------------------------------------------------------------------------


class TestArea02MetricsResolvable:
    """Todas as métricas em area02-computacao.json devem ser resolvíveis."""

    def test_all_metrics_have_source(
        self, area02_rules: dict, sources: dict[str, list[str]]
    ):
        orphans = find_orphan_metrics(area02_rules, sources)
        assert orphans == [], (
            f"Métricas órfãs na Área 02 (sem fonte em sources.yml): {orphans}"
        )

    def test_extracts_expected_metrics(self, area02_rules: dict):
        """Verifica que a extração encontra as métricas esperadas da Área 02."""
        metrics = extract_metrics_from_area(area02_rules)
        # journalArticle usa max(wos_percentil, scopus_percentil)
        assert "wos_percentil" in metrics
        assert "scopus_percentil" in metrics
        # conferencePaper usa h5_google_scholar
        assert "h5_google_scholar" in metrics
        # Ajustes qualitativos
        assert "periodico_sbc" in metrics
        assert "ce_sbc_top10" in metrics
        assert "ce_sbc_top20" in metrics
        assert "ce_sbc_relevante" in metrics
        assert "evento_sbc_nacional" in metrics


class TestArea27MetricsResolvable:
    """Todas as métricas em area27-administracao.json devem ser resolvíveis."""

    def test_all_metrics_have_source(
        self, area27_rules: dict, sources: dict[str, list[str]]
    ):
        orphans = find_orphan_metrics(area27_rules, sources)
        assert orphans == [], (
            f"Métricas órfãs na Área 27 (sem fonte em sources.yml): {orphans}"
        )

    def test_extracts_expected_metrics(self, area27_rules: dict):
        """Verifica que a extração encontra as métricas esperadas da Área 27."""
        metrics = extract_metrics_from_area(area27_rules)
        assert "abdc_rating" in metrics
        assert "abs_rating" in metrics
        assert "jcr_quartil" in metrics
        assert "sjr_quartil" in metrics
        assert "spell_faixa" in metrics
        assert "indexado_scielo_br" in metrics


# ---------------------------------------------------------------------------
# Testes com dados sintéticos — métricas órfãs
# ---------------------------------------------------------------------------


class TestOrphanMetricDetection:
    """Detecta métricas sem fonte correspondente."""

    def test_synthetic_area_with_unknown_metric(
        self, sources: dict[str, list[str]]
    ):
        """Área sintética com métrica inexistente → reporta como órfã."""
        area_rules = {
            "area": 99,
            "nome": "Área Sintética",
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "metrica_inventada_xyz",
                    "regras": [
                        {"min": 50, "resultado": "A1"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        orphans = find_orphan_metrics(area_rules, sources)
        assert "metrica_inventada_xyz" in orphans

    def test_synthetic_area_with_multiple_unknown_metrics(
        self, sources: dict[str, list[str]]
    ):
        """Área com várias métricas inventadas → todas reportadas."""
        area_rules = {
            "area": 99,
            "nome": "Área Sintética",
            "veiculos": {
                "journalArticle": {
                    "combinacao": "melhor_posicao",
                    "regras": [
                        {"metrica": "foo_index", "min": 10, "resultado": "A1"},
                        {
                            "metrica": "bar_rating",
                            "in": ["X"],
                            "requer": ["baz_flag"],
                            "resultado": "A2",
                        },
                    ],
                    "ajustes": [
                        {"se": "qux_condition", "efeito": "+1"},
                    ],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        orphans = find_orphan_metrics(area_rules, sources)
        assert "foo_index" in orphans
        assert "bar_rating" in orphans
        assert "baz_flag" in orphans
        assert "qux_condition" in orphans

    def test_sources_with_missing_provides_for_known_metric(self):
        """sources.yml sem provides para métrica usada na área → reporta órfã."""
        # Simula sources.yml que NÃO fornece sjr_quartil
        incomplete_sources = {
            "scopus": ["scopus_percentil", "scopus_quartil", "scopus_citescore"],
            # sjr ausente — nenhuma fonte fornece sjr_quartil
        }
        area_rules = {
            "area": 99,
            "nome": "Área Teste",
            "veiculos": {
                "journalArticle": {
                    "combinacao": "melhor_posicao",
                    "regras": [
                        {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "A1"},
                        {"metrica": "scopus_percentil", "min": 90, "resultado": "A1"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        orphans = find_orphan_metrics(area_rules, incomplete_sources)
        assert "sjr_quartil" in orphans
        # scopus_percentil é fornecido, não deve estar nos órfãos
        assert "scopus_percentil" not in orphans


# ---------------------------------------------------------------------------
# Testes de load_sources
# ---------------------------------------------------------------------------


class TestLoadSources:
    """Testes para carregamento de sources.yml."""

    def test_loads_real_sources_yml(self, sources_path: Path):
        """Carrega sources.yml real sem erros."""
        sources = load_sources(sources_path)
        assert isinstance(sources, dict)
        assert len(sources) > 0
        # Verifica que fontes conhecidas estão presentes
        assert "sjr" in sources
        assert "scopus" in sources
        assert "abdc" in sources

    def test_provides_are_lists(self, sources_path: Path):
        """Cada fonte tem provides como lista de strings."""
        sources = load_sources(sources_path)
        for source_id, provides in sources.items():
            assert isinstance(provides, list), f"provides de '{source_id}' não é lista"
            for metric in provides:
                assert isinstance(metric, str), (
                    f"Métrica '{metric}' em '{source_id}' não é string"
                )

    def test_file_not_found(self, tmp_path: Path):
        """Arquivo inexistente → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_sources(tmp_path / "nao_existe.yml")

    def test_invalid_yaml_no_fontes(self, tmp_path: Path):
        """YAML sem campo 'fontes' → ValueError."""
        bad_file = tmp_path / "bad.yml"
        bad_file.write_text("chave_errada: 123\n")
        with pytest.raises(ValueError, match="campo 'fontes' ausente"):
            load_sources(bad_file)

    def test_entry_without_id(self, tmp_path: Path):
        """Entrada sem campo 'id' → ValueError."""
        bad_file = tmp_path / "bad.yml"
        bad_file.write_text("fontes:\n  - nome: Teste\n    provides: [x]\n")
        with pytest.raises(ValueError, match="sem campo 'id'"):
            load_sources(bad_file)

    def test_entry_without_provides(self, tmp_path: Path):
        """Entrada sem campo 'provides' → ValueError."""
        bad_file = tmp_path / "bad.yml"
        bad_file.write_text("fontes:\n  - id: teste\n    nome: Teste\n")
        with pytest.raises(ValueError, match="sem campo 'provides'"):
            load_sources(bad_file)


# ---------------------------------------------------------------------------
# Testes de validate_all_areas
# ---------------------------------------------------------------------------


class TestValidateAllAreas:
    """Testa validação integrada de todas as áreas."""

    def test_real_areas_all_resolvable(self, areas_dir: Path, sources_path: Path):
        """Todas as áreas reais devem ter métricas resolvíveis."""
        result = validate_all_areas(areas_dir, sources_path)
        assert result == {}, (
            f"Áreas com métricas órfãs: {result}"
        )
