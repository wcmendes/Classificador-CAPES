"""Testes unitários para Área 27 — Administração.

Carrega o arquivo REAL `areas/area27-administracao.json` e testa classify()
com cenários que validam:
- melhor_posicao com múltiplas métricas → melhor estrato
- Ajuste SciELO: R→B, F→R, B sem ajuste (teto), MB sem ajuste
- SPELL + SciELO cumulativo → B
- conferencePaper/book/bookSection → NAO_CLASSIFICAVEL

Requirements: 3.1-3.7
"""

import json
from pathlib import Path

import pytest

from pipeline.engine import classify
from pipeline.vehicles import MetricValue

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AREA27_PATH = REPO_ROOT / "areas" / "area27-administracao.json"


@pytest.fixture
def area27_rules() -> dict:
    """Carrega regras reais de area27-administracao.json."""
    with open(AREA27_PATH, encoding="utf-8") as f:
        return json.load(f)


def _mv(valor, fonte_id: str = "test", data_fonte: str = "2026-01-01") -> MetricValue:
    """Helper para criar MetricValue rapidamente."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestArea27JournalArticle:
    """Testes de journalArticle com regras reais da Área 27."""

    def test_abdc_a_star_gives_mb(self, area27_rules: dict) -> None:
        """1. journalArticle, abdc_rating='A*' → MB.

        Estado é ESTIMATIVA_CONSERVADORA porque há métricas ausentes (sjr, jcr, etc.)
        que poderiam participar de melhor_posicao mas não estão disponíveis.
        """
        metricas = {"abdc_rating": _mv("A*")}
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "MB"
        assert verdict.estado == "ESTIMATIVA_CONSERVADORA"

    def test_sjr_q1_gives_mb(self, area27_rules: dict) -> None:
        """2. journalArticle, sjr_quartil='Q1' → MB.

        Estado é ESTIMATIVA_CONSERVADORA (métricas parciais em melhor_posicao).
        """
        metricas = {"sjr_quartil": _mv("Q1")}
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "MB"
        assert verdict.estado == "ESTIMATIVA_CONSERVADORA"

    def test_abdc_b_gives_b(self, area27_rules: dict) -> None:
        """3. journalArticle, abdc_rating='B' → B.

        Estado é ESTIMATIVA_CONSERVADORA (métricas parciais em melhor_posicao).
        """
        metricas = {"abdc_rating": _mv("B")}
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "B"
        assert verdict.estado == "ESTIMATIVA_CONSERVADORA"

    def test_sjr_q2_gives_b(self, area27_rules: dict) -> None:
        """4. journalArticle, sjr_quartil='Q2' → B.

        Estado é ESTIMATIVA_CONSERVADORA (métricas parciais em melhor_posicao).
        """
        metricas = {"sjr_quartil": _mv("Q2")}
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "B"
        assert verdict.estado == "ESTIMATIVA_CONSERVADORA"

    def test_sjr_q3_with_scielo_gives_b(self, area27_rules: dict) -> None:
        """5. journalArticle, sjr_quartil='Q3' + indexado_scielo_br → B.

        Estrato base R, ajuste SciELO +1 → B (teto B respeitado).
        """
        metricas = {
            "sjr_quartil": _mv("Q3"),
            "indexado_scielo_br": _mv(True),
        }
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "B"

    def test_sjr_q4_with_scielo_gives_r(self, area27_rules: dict) -> None:
        """6. journalArticle, sjr_quartil='Q4' + indexado_scielo_br → R.

        Estrato base F, ajuste SciELO +1 → R.
        """
        metricas = {
            "sjr_quartil": _mv("Q4"),
            "indexado_scielo_br": _mv(True),
        }
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "R"

    def test_abdc_b_with_scielo_stays_b(self, area27_rules: dict) -> None:
        """7. journalArticle, abdc_rating='B' + indexado_scielo_br → B.

        Estrato base B, teto=B impede subir para MB.
        """
        metricas = {
            "abdc_rating": _mv("B"),
            "indexado_scielo_br": _mv(True),
        }
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "B"

    def test_spell_decil_superior_with_scielo_gives_b(self, area27_rules: dict) -> None:
        """8. journalArticle, spell_faixa='decil_superior' + indexado_scielo_br → B.

        Requer cumulativo: SPELL décil superior + SciELO → regra satisfeita → B.
        """
        metricas = {
            "spell_faixa": _mv("decil_superior"),
            "indexado_scielo_br": _mv(True),
        }
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "B"

    def test_spell_decil_superior_without_scielo_not_b(self, area27_rules: dict) -> None:
        """9. journalArticle, spell_faixa='decil_superior' SEM indexado_scielo_br → NÃO B.

        Sem SciELO, a regra SPELL com requer falha → NAO_CLASSIFICAVEL.
        """
        metricas = {"spell_faixa": _mv("decil_superior")}
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato != "B"
        # Sem outras métricas, nenhuma regra é satisfeita → fallback
        assert verdict.estrato == "NAO_CLASSIFICAVEL"

    def test_no_metrics_gives_nao_classificavel(self, area27_rules: dict) -> None:
        """10. journalArticle sem métricas → NAO_CLASSIFICAVEL."""
        metricas: dict[str, MetricValue] = {}
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "NAO_CLASSIFICAVEL"
        assert verdict.estado == "NAO_CLASSIFICAVEL"

    def test_multiple_metrics_best_wins(self, area27_rules: dict) -> None:
        """11. journalArticle, abdc='C' + sjr='Q1' → MB (melhor_posicao picks best).

        abdc_rating='C' → R, sjr_quartil='Q1' → MB. Melhor posição = MB.
        """
        metricas = {
            "abdc_rating": _mv("C"),
            "sjr_quartil": _mv("Q1"),
        }
        verdict = classify("journalArticle", metricas, area27_rules)
        assert verdict.estrato == "MB"


class TestArea27NonJournalTypes:
    """Testes de tipos não definidos em veículos (conferencePaper, book)."""

    def test_conference_paper_nao_classificavel(self, area27_rules: dict) -> None:
        """12. conferencePaper → NAO_CLASSIFICAVEL."""
        metricas = {"sjr_quartil": _mv("Q1")}
        verdict = classify("conferencePaper", metricas, area27_rules)
        assert verdict.estrato == "NAO_CLASSIFICAVEL"
        assert verdict.estado == "NAO_CLASSIFICAVEL"

    def test_book_nao_classificavel(self, area27_rules: dict) -> None:
        """13. book → NAO_CLASSIFICAVEL."""
        metricas = {"abdc_rating": _mv("A*")}
        verdict = classify("book", metricas, area27_rules)
        assert verdict.estrato == "NAO_CLASSIFICAVEL"
        assert verdict.estado == "NAO_CLASSIFICAVEL"


class TestArea27Status:
    """Teste de status experimental do arquivo de regras."""

    def test_status_is_experimental(self, area27_rules: dict) -> None:
        """14. Verifica que o status no arquivo é 'experimental'."""
        assert area27_rules["status"] == "experimental"
