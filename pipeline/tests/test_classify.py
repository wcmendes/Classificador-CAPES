"""Testes unitários para a função classify() — orquestração principal.

Cobre:
- journalArticle com metrica_unica: todas métricas → COMPLETO
- journalArticle com uma métrica ausente → ESTIMATIVA_CONSERVADORA
- journalArticle sem métricas → NAO_CLASSIFICAVEL
- conferencePaper → fallback NAO_CONSIDERADO
- book → NAO_CLASSIFICAVEL
- Tipo desconhecido → NAO_CLASSIFICAVEL
- melhor_posicao (estilo Área 27): melhor resultado selecionado
- primeira_regra: primeiro match
- Trilha contém entradas esperadas
- Ajustes qualitativos sinalizados mas não aplicados
"""

import pytest

from pipeline.engine import TrailEntry, Verdict, classify
from pipeline.vehicles import MetricValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mv(valor, fonte_id="test_src", data_fonte="2026-07-01"):
    """Cria MetricValue de teste."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


# ---------------------------------------------------------------------------
# Fixtures — Regras sintéticas
# ---------------------------------------------------------------------------


@pytest.fixture
def area_metrica_unica() -> dict:
    """Regras estilo Área 02 (metrica_unica com max(a, b))."""
    return {
        "area": 2,
        "nome": "Computação",
        "vigencia": "2025-2028",
        "data_extracao": "2026-07-15",
        "status": "experimental",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"],
            "pontos": {"A1": 1, "A2": 0.875, "A3": 0.75, "A4": 0.625,
                       "A5": 0, "A6": 0, "A7": 0, "A8": 0},
        },
        "veiculos": {
            "journalArticle": {
                "combinacao": "metrica_unica",
                "metrica": "max(wos_percentil, scopus_percentil)",
                "regras": [
                    {"min": 87.5, "resultado": "A1"},
                    {"min": 75.0, "max": 87.5, "resultado": "A2"},
                    {"min": 62.5, "max": 75.0, "resultado": "A3"},
                    {"min": 50.0, "max": 62.5, "resultado": "A4"},
                    {"min": 37.5, "max": 50.0, "resultado": "A5"},
                    {"min": 25.0, "max": 37.5, "resultado": "A6"},
                    {"min": 12.5, "max": 25.0, "resultado": "A7"},
                    {"min": 0, "max": 12.5, "resultado": "A8"},
                ],
                "ajustes": [
                    {"se": "periodico_sbc", "efeito": "+2",
                     "qualitativo": True,
                     "nota": "Elegibilidade SBC sinalizada."},
                ],
                "fallback": "NAO_CLASSIFICAVEL",
            },
            "conferencePaper": {
                "combinacao": "metrica_unica",
                "metrica": "h5_google_scholar",
                "regras": [
                    {"min": 35, "resultado": "A1"},
                    {"min": 25, "max": 35, "resultado": "A2"},
                    {"min": 20, "max": 25, "resultado": "A3"},
                    {"min": 15, "max": 20, "resultado": "A4"},
                ],
                "ajustes": [],
                "teto_qualitativo": "A3",
                "fallback": "NAO_CONSIDERADO",
            },
            "book": {
                "combinacao": "primeira_regra",
                "regras": [
                    {"resultado": "NAO_CLASSIFICAVEL",
                     "nota": "Livros não automatizáveis."},
                ],
                "fallback": "NAO_CLASSIFICAVEL",
            },
        },
    }


@pytest.fixture
def area_melhor_posicao() -> dict:
    """Regras estilo Área 27 (melhor_posicao com múltiplas métricas)."""
    return {
        "area": 27,
        "nome": "Administração",
        "vigencia": "2025-2028",
        "data_extracao": "2026-07-15",
        "status": "experimental",
        "escala": {
            "rotulos": ["MB", "B", "R", "F", "I"],
            "pontos": {"MB": 8, "B": 4, "R": 2, "F": 1, "I": 0},
        },
        "veiculos": {
            "journalArticle": {
                "combinacao": "melhor_posicao",
                "regras": [
                    {"metrica": "abdc_rating", "in": ["A", "A*"],
                     "resultado": "MB"},
                    {"metrica": "sjr_quartil", "in": ["Q1"],
                     "resultado": "MB"},
                    {"metrica": "abdc_rating", "in": ["B"],
                     "resultado": "B"},
                    {"metrica": "sjr_quartil", "in": ["Q2"],
                     "resultado": "B"},
                    {"metrica": "abdc_rating", "in": ["C"],
                     "resultado": "R"},
                    {"metrica": "sjr_quartil", "in": ["Q3"],
                     "resultado": "R"},
                    {"metrica": "sjr_quartil", "in": ["Q4"],
                     "resultado": "F"},
                ],
                "ajustes": [
                    {"se": "indexado_scielo_br", "efeito": "+1",
                     "teto": "B"},
                ],
                "fallback": "NAO_CLASSIFICAVEL",
            },
        },
    }


@pytest.fixture
def area_primeira_regra() -> dict:
    """Regras com modo primeira_regra para testes."""
    return {
        "area": 50,
        "nome": "Área Teste Primeira Regra",
        "vigencia": "2025-2028",
        "data_extracao": "2026-07-15",
        "status": "experimental",
        "escala": {
            "rotulos": ["X1", "X2", "X3", "X4"],
            "pontos": {"X1": 4, "X2": 3, "X3": 2, "X4": 1},
        },
        "veiculos": {
            "journalArticle": {
                "combinacao": "primeira_regra",
                "regras": [
                    {"metrica": "score", "min": 90, "resultado": "X1"},
                    {"metrica": "score", "min": 70, "max": 90,
                     "resultado": "X2"},
                    {"metrica": "score", "min": 50, "max": 70,
                     "resultado": "X3"},
                    {"metrica": "score", "min": 0, "max": 50,
                     "resultado": "X4"},
                ],
                "ajustes": [],
                "fallback": "NAO_CLASSIFICAVEL",
            },
        },
    }


# ---------------------------------------------------------------------------
# Testes: metrica_unica — journalArticle com todas métricas → COMPLETO
# ---------------------------------------------------------------------------


class TestClassifyMetricaUnicaCompleto:
    """classify() com metrica_unica e todas métricas presentes → COMPLETO."""

    def test_all_metrics_present_a1(self, area_metrica_unica):
        """Ambos percentis presentes, max >= 87.5 → A1, COMPLETO."""
        metricas = {
            "wos_percentil": _mv(90.0),
            "scopus_percentil": _mv(85.0),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.estrato == "A1"
        assert v.estado == "COMPLETO"
        assert v.area == 2
        assert v.data_snapshot == "2026-07-15"

    def test_all_metrics_present_a3(self, area_metrica_unica):
        """Ambos percentis presentes, max em [62.5, 75) → A3, COMPLETO."""
        metricas = {
            "wos_percentil": _mv(65.0),
            "scopus_percentil": _mv(70.0),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.estrato == "A3"
        assert v.estado == "COMPLETO"


# ---------------------------------------------------------------------------
# Testes: metrica_unica — journalArticle com uma métrica ausente
#         → ESTIMATIVA_CONSERVADORA
# ---------------------------------------------------------------------------


class TestClassifyMetricaUnicaEstimativa:
    """classify() com operando parcial → ESTIMATIVA_CONSERVADORA."""

    def test_one_metric_absent(self, area_metrica_unica):
        """Apenas scopus_percentil presente → ESTIMATIVA_CONSERVADORA."""
        metricas = {
            "scopus_percentil": _mv(80.0),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.estrato == "A2"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"

    def test_one_metric_absent_low_value(self, area_metrica_unica):
        """Apenas wos_percentil presente com valor baixo."""
        metricas = {
            "wos_percentil": _mv(30.0),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.estrato == "A6"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"


# ---------------------------------------------------------------------------
# Testes: metrica_unica — journalArticle sem métricas → NAO_CLASSIFICAVEL
# ---------------------------------------------------------------------------


class TestClassifyMetricaUnicaNaoClassificavel:
    """classify() sem métricas → NAO_CLASSIFICAVEL."""

    def test_no_metrics_journal(self, area_metrica_unica):
        """Nenhuma métrica para journalArticle → fallback NAO_CLASSIFICAVEL."""
        metricas: dict[str, MetricValue] = {}
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"

    def test_irrelevant_metrics(self, area_metrica_unica):
        """Métricas presentes mas irrelevantes para a expressão."""
        metricas = {
            "abdc_rating": _mv("A"),  # Não participa de max(wos, scopus)
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# Testes: conferencePaper → fallback NAO_CONSIDERADO
# ---------------------------------------------------------------------------


class TestClassifyConferencePaperFallback:
    """classify() conferencePaper sem h5 → NAO_CONSIDERADO."""

    def test_no_h5_metric(self, area_metrica_unica):
        """Sem h5_google_scholar → fallback NAO_CONSIDERADO."""
        metricas: dict[str, MetricValue] = {}
        v = classify("conferencePaper", metricas, area_metrica_unica)
        assert v.estrato == "NAO_CONSIDERADO"
        assert v.estado == "NAO_CONSIDERADO"

    def test_conference_with_h5(self, area_metrica_unica):
        """Com h5=30 → A2, COMPLETO."""
        metricas = {"h5_google_scholar": _mv(30)}
        v = classify("conferencePaper", metricas, area_metrica_unica)
        assert v.estrato == "A2"
        assert v.estado == "COMPLETO"


# ---------------------------------------------------------------------------
# Testes: book → NAO_CLASSIFICAVEL
# ---------------------------------------------------------------------------


class TestClassifyBookNaoClassificavel:
    """classify() para book → sempre NAO_CLASSIFICAVEL."""

    def test_book_returns_nao_classificavel(self, area_metrica_unica):
        """book via primeira_regra com regra incondicional."""
        metricas: dict[str, MetricValue] = {}
        v = classify("book", metricas, area_metrica_unica)
        # A regra sem campo 'metrica' é satisfeita → resultado NAO_CLASSIFICAVEL
        # Mas isso vem da regra (não do fallback), estado depende de missing
        assert v.estrato == "NAO_CLASSIFICAVEL"

    def test_book_with_metrics_still_nao_classificavel(self, area_metrica_unica):
        """Mesmo com métricas presentes, book retorna NAO_CLASSIFICAVEL."""
        metricas = {"scopus_percentil": _mv(95.0)}
        v = classify("book", metricas, area_metrica_unica)
        assert v.estrato == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# Testes: tipo desconhecido → NAO_CLASSIFICAVEL
# ---------------------------------------------------------------------------


class TestClassifyUnknownType:
    """classify() com item_type não definido em veiculos."""

    def test_unknown_type(self, area_metrica_unica):
        """Tipo não existente → NAO_CLASSIFICAVEL direto."""
        metricas = {"scopus_percentil": _mv(90.0)}
        v = classify("thesis", metricas, area_metrica_unica)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"

    def test_unknown_type_trail_has_fallback(self, area_metrica_unica):
        """Trilha indica fallback por tipo não definido."""
        metricas: dict[str, MetricValue] = {}
        v = classify("patent", metricas, area_metrica_unica)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"
        assert len(v.trilha) == 1
        assert v.trilha[0].etapa == "fallback"
        assert "patent" in (v.trilha[0].nota or "")


# ---------------------------------------------------------------------------
# Testes: melhor_posicao (estilo Área 27)
# ---------------------------------------------------------------------------


class TestClassifyMelhorPosicao:
    """classify() com modo melhor_posicao."""

    def test_best_result_selected(self, area_melhor_posicao):
        """Múltiplas regras satisfeitas → melhor estrato selecionado."""
        metricas = {
            "abdc_rating": _mv("B"),      # → B
            "sjr_quartil": _mv("Q1"),     # → MB
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        assert v.estrato == "MB"
        assert v.estado == "COMPLETO"

    def test_single_metric_satisfied(self, area_melhor_posicao):
        """Uma única métrica satisfaz uma regra."""
        metricas = {
            "sjr_quartil": _mv("Q3"),     # → R
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        # abdc_rating ausente → ESTIMATIVA_CONSERVADORA
        assert v.estrato == "R"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"


    def test_adjustment_applied_scielo(self, area_melhor_posicao):
        """Ajuste SciELO: R→B com teto B (não-qualitativo)."""
        metricas = {
            "sjr_quartil": _mv("Q3"),         # → R
            "indexado_scielo_br": _mv(True),   # ajuste +1
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        assert v.estrato == "B"

    def test_adjustment_teto_b(self, area_melhor_posicao):
        """Ajuste SciELO com base B: teto B impede ir para MB."""
        metricas = {
            "abdc_rating": _mv("B"),           # → B
            "indexado_scielo_br": _mv(True),   # ajuste +1 com teto B
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        assert v.estrato == "B"  # Teto impede subir para MB

    def test_no_rules_satisfied(self, area_melhor_posicao):
        """Nenhuma regra satisfeita → fallback NAO_CLASSIFICAVEL."""
        metricas = {
            "abdc_rating": _mv("D"),  # Não corresponde a nenhuma regra
            "sjr_quartil": _mv("Q5"),  # Idem
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# Testes: primeira_regra — primeiro match retornado
# ---------------------------------------------------------------------------


class TestClassifyPrimeiraRegra:
    """classify() com modo primeira_regra."""

    def test_first_match_high_score(self, area_primeira_regra):
        """Score 95 → primeira regra (min: 90) satisfeita → X1."""
        metricas = {"score": _mv(95)}
        v = classify("journalArticle", metricas, area_primeira_regra)
        assert v.estrato == "X1"
        assert v.estado == "COMPLETO"

    def test_second_match(self, area_primeira_regra):
        """Score 75 → segunda regra (min:70, max:90) → X2."""
        metricas = {"score": _mv(75)}
        v = classify("journalArticle", metricas, area_primeira_regra)
        assert v.estrato == "X2"
        assert v.estado == "COMPLETO"

    def test_last_range(self, area_primeira_regra):
        """Score 10 → última regra (min:0, max:50) → X4."""
        metricas = {"score": _mv(10)}
        v = classify("journalArticle", metricas, area_primeira_regra)
        assert v.estrato == "X4"
        assert v.estado == "COMPLETO"

    def test_no_metric_fallback(self, area_primeira_regra):
        """Sem a métrica score → nenhuma regra satisfeita → fallback."""
        metricas: dict[str, MetricValue] = {}
        v = classify("journalArticle", metricas, area_primeira_regra)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# Testes: Trilha de decisão — conteúdo esperado
# ---------------------------------------------------------------------------


class TestClassifyTrail:
    """Trilha de decisão contém entradas esperadas."""

    def test_trail_has_expressao_avaliada(self, area_metrica_unica):
        """metrica_unica gera entrada 'expressao_avaliada' na trilha."""
        metricas = {"scopus_percentil": _mv(80.0)}
        v = classify("journalArticle", metricas, area_metrica_unica)
        etapas = [e.etapa for e in v.trilha]
        assert "expressao_avaliada" in etapas

    def test_trail_has_regra_ativada(self, area_metrica_unica):
        """Quando uma regra é satisfeita, trilha contém 'regra_ativada'."""
        metricas = {
            "wos_percentil": _mv(90.0),
            "scopus_percentil": _mv(85.0),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        etapas = [e.etapa for e in v.trilha]
        assert "regra_ativada" in etapas

    def test_trail_has_ajuste_sinalizado(self, area_metrica_unica):
        """Ajuste qualitativo com condição atendida → ajuste_sinalizado."""
        metricas = {
            "wos_percentil": _mv(80.0),
            "scopus_percentil": _mv(70.0),
            "periodico_sbc": _mv(True),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        etapas = [e.etapa for e in v.trilha]
        assert "ajuste_sinalizado" in etapas

    def test_trail_has_fallback_entry(self, area_metrica_unica):
        """Sem métricas → trilha contém entrada 'fallback'."""
        metricas: dict[str, MetricValue] = {}
        v = classify("journalArticle", metricas, area_metrica_unica)
        etapas = [e.etapa for e in v.trilha]
        assert "fallback" in etapas

    def test_trail_melhor_posicao_shows_all_rules(self, area_melhor_posicao):
        """melhor_posicao gera entrada para CADA regra avaliada."""
        metricas = {
            "abdc_rating": _mv("B"),
            "sjr_quartil": _mv("Q2"),
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        # Deve ter entries para todas as 7 regras
        rule_entries = [
            e for e in v.trilha
            if e.etapa in ("regra_ativada", "regra_avaliada")
        ]
        assert len(rule_entries) == 7

    def test_trail_ajuste_aplicado(self, area_melhor_posicao):
        """Ajuste não-qualitativo aplicado → 'ajuste_aplicado' na trilha."""
        metricas = {
            "sjr_quartil": _mv("Q3"),
            "indexado_scielo_br": _mv(True),
        }
        v = classify("journalArticle", metricas, area_melhor_posicao)
        etapas = [e.etapa for e in v.trilha]
        assert "ajuste_aplicado" in etapas


# ---------------------------------------------------------------------------
# Testes: Ajustes qualitativos — sinalizados mas não aplicados
# ---------------------------------------------------------------------------


class TestClassifyAjustesQualitativos:
    """Ajustes qualitativos: elegíveis sinalizados, estrato NÃO muda."""

    def test_qualitativo_nao_altera_estrato(self, area_metrica_unica):
        """Ajuste SBC qualitativo: estrato inalterado."""
        metricas = {
            "wos_percentil": _mv(80.0),
            "scopus_percentil": _mv(78.0),
            "periodico_sbc": _mv(True),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        # max(80, 78) = 80 → A2 (75 <= 80 < 87.5)
        assert v.estrato == "A2"
        # O ajuste qualitativo +2 NÃO é aplicado
        assert v.estado == "COMPLETO"

    def test_qualitativo_sinalizado_na_trilha(self, area_metrica_unica):
        """Trilha registra que o ajuste foi sinalizado."""
        metricas = {
            "wos_percentil": _mv(60.0),
            "scopus_percentil": _mv(55.0),
            "periodico_sbc": _mv(True),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        # max(60, 55) = 60 → A4 (50 <= 60 < 62.5)
        assert v.estrato == "A4"
        sinalizados = [e for e in v.trilha if e.etapa == "ajuste_sinalizado"]
        assert len(sinalizados) == 1
        assert sinalizados[0].metrica == "periodico_sbc"

    def test_qualitativo_nao_sinalizado_se_condicao_ausente(
        self, area_metrica_unica
    ):
        """Sem periodico_sbc → ajuste nem é mencionado na trilha."""
        metricas = {
            "wos_percentil": _mv(80.0),
            "scopus_percentil": _mv(78.0),
        }
        v = classify("journalArticle", metricas, area_metrica_unica)
        sinalizados = [e for e in v.trilha if e.etapa == "ajuste_sinalizado"]
        assert len(sinalizados) == 0


# ---------------------------------------------------------------------------
# Testes: Verdict metadata
# ---------------------------------------------------------------------------


class TestClassifyVerdictMetadata:
    """Verify Verdict contains correct metadata."""

    def test_area_code(self, area_metrica_unica):
        metricas = {"scopus_percentil": _mv(50.0)}
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.area == 2

    def test_data_snapshot(self, area_metrica_unica):
        metricas = {"scopus_percentil": _mv(50.0)}
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert v.data_snapshot == "2026-07-15"

    def test_verdict_is_dataclass(self, area_metrica_unica):
        metricas = {"scopus_percentil": _mv(50.0)}
        v = classify("journalArticle", metricas, area_metrica_unica)
        assert isinstance(v, Verdict)

    def test_trilha_entries_are_trail_entry(self, area_metrica_unica):
        metricas = {"scopus_percentil": _mv(50.0)}
        v = classify("journalArticle", metricas, area_metrica_unica)
        for entry in v.trilha:
            assert isinstance(entry, TrailEntry)


# ---------------------------------------------------------------------------
# Testes: usando sample_area_rules da conftest.py
# ---------------------------------------------------------------------------


class TestClassifyWithSampleFixture:
    """Testes usando a fixture sample_area_rules do conftest.py."""

    def test_sample_journal_a1(self, sample_area_rules):
        """test_percentil >= 75 → A1, COMPLETO."""
        metricas = {"test_percentil": _mv(80.0)}
        v = classify("journalArticle", metricas, sample_area_rules)
        assert v.estrato == "A1"
        assert v.estado == "COMPLETO"

    def test_sample_journal_a4(self, sample_area_rules):
        """test_percentil em [0, 25) → A4, COMPLETO."""
        metricas = {"test_percentil": _mv(10.0)}
        v = classify("journalArticle", metricas, sample_area_rules)
        assert v.estrato == "A4"
        assert v.estado == "COMPLETO"

    def test_sample_unknown_type(self, sample_area_rules):
        """Tipo não definido em sample → NAO_CLASSIFICAVEL."""
        metricas = {"test_percentil": _mv(80.0)}
        v = classify("conferencePaper", metricas, sample_area_rules)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"
