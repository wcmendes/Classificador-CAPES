"""Testes de integração do motor de regras com a Área 02 — Computação.

Carrega o arquivo REAL areas/area02-computacao.json e executa classify()
com cenários representativos dos critérios da área.

Requirements: 4.1-4.9
"""

import json
from pathlib import Path

import pytest

from pipeline.engine import classify, Verdict, TrailEntry
from pipeline.vehicles import MetricValue

# ---------------------------------------------------------------------------
# Fixture: regras reais da Área 02
# ---------------------------------------------------------------------------

AREA02_PATH = Path(__file__).resolve().parent.parent.parent / "areas" / "area02-computacao.json"


@pytest.fixture
def area02_rules() -> dict:
    """Carrega regras reais de areas/area02-computacao.json."""
    with open(AREA02_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mv(valor, fonte_id: str = "test", data_fonte: str = "2026-01-01") -> MetricValue:
    """Helper para criar MetricValue de forma concisa."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


# ---------------------------------------------------------------------------
# 1. journalArticle com dois percentis → A1, COMPLETO
# ---------------------------------------------------------------------------


class TestJournalArticle:
    """Cenários de journalArticle (combinacao=metrica_unica, max(wos,scopus))."""

    def test_both_percentiles_high_yields_a1_completo(self, area02_rules: dict) -> None:
        """scopus_percentil=90, wos_percentil=85 → A1, COMPLETO."""
        metricas = {
            "scopus_percentil": _mv(90),
            "wos_percentil": _mv(85),
        }
        v = classify("journalArticle", metricas, area02_rules)

        assert v.estrato == "A1"
        assert v.estado == "COMPLETO"
        assert v.area == 2

    def test_single_scopus_70_yields_a3_estimativa(self, area02_rules: dict) -> None:
        """scopus_percentil=70 only → A3, ESTIMATIVA_CONSERVADORA."""
        metricas = {
            "scopus_percentil": _mv(70),
        }
        v = classify("journalArticle", metricas, area02_rules)

        # max(wos_percentil, scopus_percentil) com wos ausente → usa 70
        # 62.5 <= 70 < 75 → A3
        assert v.estrato == "A3"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"

    def test_scopus_50_yields_a4(self, area02_rules: dict) -> None:
        """scopus_percentil=50.0 → A4."""
        metricas = {
            "scopus_percentil": _mv(50.0),
            "wos_percentil": _mv(50.0),
        }
        v = classify("journalArticle", metricas, area02_rules)

        # 50.0 <= 50 < 62.5 → A4
        assert v.estrato == "A4"
        assert v.estado == "COMPLETO"

    def test_no_metrics_yields_nao_classificavel(self, area02_rules: dict) -> None:
        """journalArticle sem métricas → NAO_CLASSIFICAVEL."""
        metricas: dict[str, MetricValue] = {}
        v = classify("journalArticle", metricas, area02_rules)

        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# 5-8. conferencePaper com h5_google_scholar
# ---------------------------------------------------------------------------


class TestConferencePaper:
    """Cenários de conferencePaper (combinacao=metrica_unica, h5_google_scholar)."""

    def test_h5_40_yields_a1(self, area02_rules: dict) -> None:
        """h5_google_scholar=40 → A1 (min 35)."""
        metricas = {
            "h5_google_scholar": _mv(40),
        }
        v = classify("conferencePaper", metricas, area02_rules)

        assert v.estrato == "A1"

    def test_h5_20_yields_a3(self, area02_rules: dict) -> None:
        """h5_google_scholar=20 → A3 (min 20, max 25)."""
        metricas = {
            "h5_google_scholar": _mv(20),
        }
        v = classify("conferencePaper", metricas, area02_rules)

        assert v.estrato == "A3"

    def test_h5_5_yields_a8(self, area02_rules: dict) -> None:
        """h5_google_scholar=5 → A8 (min 1, max 6)."""
        metricas = {
            "h5_google_scholar": _mv(5),
        }
        v = classify("conferencePaper", metricas, area02_rules)

        assert v.estrato == "A8"

    def test_no_h5_yields_nao_considerado(self, area02_rules: dict) -> None:
        """conferencePaper sem h5 → NAO_CONSIDERADO (fallback)."""
        metricas: dict[str, MetricValue] = {}
        v = classify("conferencePaper", metricas, area02_rules)

        assert v.estrato == "NAO_CONSIDERADO"
        assert v.estado == "NAO_CONSIDERADO"


# ---------------------------------------------------------------------------
# 9-10. book e bookSection → NAO_CLASSIFICAVEL
# ---------------------------------------------------------------------------


class TestBookTypes:
    """Livros e capítulos são NAO_CLASSIFICAVEL (avaliação qualitativa).

    Nota: o estado é COMPLETO porque a regra é determinística —
    a área DEFINE que livros/capítulos não são classificáveis automaticamente.
    Não é falta de dados, é decisão declarada.
    """

    def test_book_yields_nao_classificavel(self, area02_rules: dict) -> None:
        """book → estrato NAO_CLASSIFICAVEL."""
        metricas: dict[str, MetricValue] = {}
        v = classify("book", metricas, area02_rules)

        assert v.estrato == "NAO_CLASSIFICAVEL"
        # Estado COMPLETO: a regra é determinística (não há métrica ausente)
        assert v.estado == "COMPLETO"

    def test_book_section_yields_nao_classificavel(self, area02_rules: dict) -> None:
        """bookSection → estrato NAO_CLASSIFICAVEL."""
        metricas: dict[str, MetricValue] = {}
        v = classify("bookSection", metricas, area02_rules)

        assert v.estrato == "NAO_CLASSIFICAVEL"
        # Estado COMPLETO: a regra é determinística (não há métrica ausente)
        assert v.estado == "COMPLETO"


# ---------------------------------------------------------------------------
# 11-12. Ajustes qualitativos SBC
# ---------------------------------------------------------------------------


class TestAjustesQualitativosSBC:
    """Ajustes qualitativos da SBC: sinalizados mas não aplicados."""

    def test_periodico_sbc_sinalizado_estrato_inalterado(self, area02_rules: dict) -> None:
        """journalArticle com periodico_sbc=True → ajuste SINALIZADO, estrato inalterado."""
        metricas = {
            "scopus_percentil": _mv(70),
            "wos_percentil": _mv(70),
            "periodico_sbc": _mv(True),
        }
        v = classify("journalArticle", metricas, area02_rules)

        # 62.5 <= 70 < 75 → A3 base
        # Ajuste qualitativo: sinalizado mas NÃO aplicado
        assert v.estrato == "A3"  # Inalterado

        # Verificar que houve sinalização na trilha
        sinalizacoes = [t for t in v.trilha if t.etapa == "ajuste_sinalizado"]
        assert len(sinalizacoes) >= 1
        assert sinalizacoes[0].metrica == "periodico_sbc"

    def test_ce_sbc_top10_sinalizado_teto_a3(self, area02_rules: dict) -> None:
        """conferencePaper com ce_sbc_top10=True, h5=25 → ajuste sinalizado, teto A3."""
        metricas = {
            "h5_google_scholar": _mv(25),
            "ce_sbc_top10": _mv(True),
        }
        v = classify("conferencePaper", metricas, area02_rules)

        # h5=25 → min 25, max 35 → A2 base
        assert v.estrato == "A2"  # Inalterado (qualitativo não aplica)

        # Verificar que houve sinalização na trilha
        sinalizacoes = [t for t in v.trilha if t.etapa == "ajuste_sinalizado"]
        assert len(sinalizacoes) >= 1

        # O teto qualitativo do bloco conferencePaper é A3
        # Então o alvo sinalizado deve respeitar o teto A3
        sinal_top10 = [s for s in sinalizacoes if s.metrica == "ce_sbc_top10"]
        assert len(sinal_top10) >= 1
        # O ajuste +2 sobre A2 iria para "fora da escala" (melhor que A1 não existe)
        # mas o teto_qualitativo A3 limita: de A2, +2 iria para index 0 (A1),
        # mas com teto A3 o resultado sinalizado deve ser no máximo A3.
        # Porém base já é A2 que é melhor que A3, então na prática o teto limita
        # para A3 se o alvo calculado for melhor que A3.
        # A2 index=1, +2 → index=-1 clamped to 0 → A1, mas teto A3 (index=2) → A3
        assert sinal_top10[0].resultado == "A3"


# ---------------------------------------------------------------------------
# Status experimental
# ---------------------------------------------------------------------------


class TestStatusExperimental:
    """O status da área deve ser refletido no veredito."""

    def test_area02_is_experimental(self, area02_rules: dict) -> None:
        """O JSON de area02 tem status=experimental."""
        assert area02_rules["status"] == "experimental"

    def test_verdict_carries_area_and_snapshot_date(self, area02_rules: dict) -> None:
        """O veredito inclui código da área e data do snapshot."""
        metricas = {"scopus_percentil": _mv(90), "wos_percentil": _mv(90)}
        v = classify("journalArticle", metricas, area02_rules)

        assert v.area == 2
        assert v.data_snapshot == "2026-07-26"  # data_extracao do JSON
