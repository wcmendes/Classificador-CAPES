"""Testes unitários para pipeline/engine.py — Motor de Regras.

Cobre:
- evaluate_rule: campo in, min/max, requer, métrica ausente
- evaluate_expression: max/min com 0, 1, 2 operandos
- Modos de combinação: melhor_posicao, metrica_unica, primeira_regra
- apply_adjustments: efeito, resultado, teto, qualitativo
- classify: orquestração completa, fallback, estado, trilha
"""

import pytest

from pipeline.engine import (
    TrailEntry,
    Verdict,
    apply_adjustments,
    classify,
    evaluate_expression,
    evaluate_rule,
    melhor_posicao,
    metrica_unica,
    primeira_regra,
)
from pipeline.vehicles import MetricValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mv(valor, fonte_id="test", data_fonte="2026-01-01"):
    """Cria MetricValue de teste."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


# ---------------------------------------------------------------------------
# evaluate_rule — campo "in"
# ---------------------------------------------------------------------------


class TestEvaluateRuleIn:
    """Testes para campo 'in' (pertencimento case-sensitive, tipo-exata)."""

    def test_in_string_match(self):
        rule = {"metrica": "quartil", "in": ["Q1", "Q2"], "resultado": "MB"}
        metricas = {"quartil": _mv("Q1")}
        assert evaluate_rule(rule, metricas) is True

    def test_in_string_no_match(self):
        rule = {"metrica": "quartil", "in": ["Q1", "Q2"], "resultado": "MB"}
        metricas = {"quartil": _mv("Q3")}
        assert evaluate_rule(rule, metricas) is False

    def test_in_case_sensitive(self):
        """'q1' != 'Q1' — comparação case-sensitive."""
        rule = {"metrica": "quartil", "in": ["Q1"], "resultado": "MB"}
        metricas = {"quartil": _mv("q1")}
        assert evaluate_rule(rule, metricas) is False

    def test_in_type_exact_string_vs_number(self):
        """String "2" não é igual a int 2 — tipo-exata."""
        rule = {"metrica": "rating", "in": [2], "resultado": "MB"}
        metricas = {"rating": _mv("2")}
        assert evaluate_rule(rule, metricas) is False

    def test_in_numeric_match(self):
        rule = {"metrica": "rating", "in": [1, 2, 3], "resultado": "MB"}
        metricas = {"rating": _mv(2)}
        assert evaluate_rule(rule, metricas) is True


# ---------------------------------------------------------------------------
# evaluate_rule — campos min/max
# ---------------------------------------------------------------------------


class TestEvaluateRuleMinMax:
    """Testes para campos min (inclusivo) e max (exclusivo)."""

    def test_min_inclusive(self):
        """min é inclusivo: valor == min → satisfeita."""
        rule = {"metrica": "percentil", "min": 75.0, "resultado": "A1"}
        metricas = {"percentil": _mv(75.0)}
        assert evaluate_rule(rule, metricas) is True

    def test_below_min(self):
        """Valor abaixo de min → não satisfeita."""
        rule = {"metrica": "percentil", "min": 75.0, "resultado": "A1"}
        metricas = {"percentil": _mv(74.9)}
        assert evaluate_rule(rule, metricas) is False

    def test_max_exclusive(self):
        """max é exclusivo: valor == max → não satisfeita."""
        rule = {"metrica": "percentil", "min": 50.0, "max": 75.0, "resultado": "A2"}
        metricas = {"percentil": _mv(75.0)}
        assert evaluate_rule(rule, metricas) is False

    def test_within_range(self):
        """Valor dentro da faixa [min, max) → satisfeita."""
        rule = {"metrica": "percentil", "min": 50.0, "max": 75.0, "resultado": "A2"}
        metricas = {"percentil": _mv(60.0)}
        assert evaluate_rule(rule, metricas) is True

    def test_only_min(self):
        """Apenas min definido (sem max) — sem limite superior."""
        rule = {"metrica": "h5", "min": 35, "resultado": "A1"}
        metricas = {"h5": _mv(100)}
        assert evaluate_rule(rule, metricas) is True

    def test_only_max(self):
        """Apenas max definido (sem min)."""
        rule = {"metrica": "h5", "max": 6, "resultado": "A8"}
        metricas = {"h5": _mv(5)}
        assert evaluate_rule(rule, metricas) is True


# ---------------------------------------------------------------------------
# evaluate_rule — campo requer
# ---------------------------------------------------------------------------


class TestEvaluateRuleRequer:
    """Testes para campo 'requer' (conjunção lógica)."""

    def test_requer_all_present(self):
        """Todas as condições presentes e truthy → satisfeita."""
        rule = {
            "metrica": "spell_faixa",
            "in": ["decil_superior"],
            "requer": ["indexado_scielo_br"],
            "resultado": "B",
        }
        metricas = {
            "spell_faixa": _mv("decil_superior"),
            "indexado_scielo_br": _mv(True),
        }
        assert evaluate_rule(rule, metricas) is True

    def test_requer_missing_condition(self):
        """Condição requerida ausente → não satisfeita."""
        rule = {
            "metrica": "spell_faixa",
            "in": ["decil_superior"],
            "requer": ["indexado_scielo_br"],
            "resultado": "B",
        }
        metricas = {"spell_faixa": _mv("decil_superior")}
        assert evaluate_rule(rule, metricas) is False

    def test_requer_falsy_condition(self):
        """Condição requerida existe mas é falsy → não satisfeita."""
        rule = {
            "metrica": "spell_faixa",
            "in": ["decil_superior"],
            "requer": ["indexado_scielo_br"],
            "resultado": "B",
        }
        metricas = {
            "spell_faixa": _mv("decil_superior"),
            "indexado_scielo_br": _mv(False),
        }
        assert evaluate_rule(rule, metricas) is False

    def test_requer_multiple_conditions(self):
        """Múltiplas condições: todas devem ser verdadeiras."""
        rule = {
            "metrica": "score",
            "min": 10,
            "requer": ["cond_a", "cond_b"],
            "resultado": "X",
        }
        metricas = {
            "score": _mv(15),
            "cond_a": _mv(True),
            "cond_b": _mv(True),
        }
        assert evaluate_rule(rule, metricas) is True

    def test_requer_one_missing_of_multiple(self):
        """Uma de múltiplas condições ausente → não satisfeita."""
        rule = {
            "metrica": "score",
            "min": 10,
            "requer": ["cond_a", "cond_b"],
            "resultado": "X",
        }
        metricas = {"score": _mv(15), "cond_a": _mv(True)}
        assert evaluate_rule(rule, metricas) is False


# ---------------------------------------------------------------------------
# evaluate_rule — métrica ausente
# ---------------------------------------------------------------------------


class TestEvaluateRuleMetricaAusente:
    """Testes para quando métrica não está disponível."""

    def test_metrica_not_in_dict(self):
        """Métrica requerida por regra ausente → não satisfeita."""
        rule = {"metrica": "wos_percentil", "min": 75.0, "resultado": "A1"}
        metricas = {}  # Nenhuma métrica disponível
        assert evaluate_rule(rule, metricas) is False

    def test_rule_without_metrica_field(self):
        """Regra sem campo 'metrica' → sempre satisfeita (sujeita a requer)."""
        rule = {"resultado": "NAO_CLASSIFICAVEL"}
        metricas = {}
        assert evaluate_rule(rule, metricas) is True

    def test_rule_without_metrica_field_with_failing_requer(self):
        """Regra sem metrica mas com requer falhando → não satisfeita."""
        rule = {"resultado": "X", "requer": ["cond"]}
        metricas = {}
        assert evaluate_rule(rule, metricas) is False


# ---------------------------------------------------------------------------
# evaluate_expression
# ---------------------------------------------------------------------------


class TestEvaluateExpression:
    """Testes para avaliação de expressões max(...)/min(...)."""

    def test_max_two_operands_both_present(self):
        """max(a, b) com ambos presentes → retorna o maior."""
        metricas = {"a": _mv(80.0), "b": _mv(90.0)}
        value, missing = evaluate_expression("max(a, b)", metricas)
        assert value == 90.0
        assert missing == []

    def test_max_one_operand_missing(self):
        """max(a, b) com um ausente → retorna o disponível."""
        metricas = {"a": _mv(80.0)}
        value, missing = evaluate_expression("max(a, b)", metricas)
        assert value == 80.0
        assert missing == ["b"]

    def test_max_all_operands_missing(self):
        """max(a, b) com nenhum disponível → None."""
        metricas: dict[str, MetricValue] = {}
        value, missing = evaluate_expression("max(a, b)", metricas)
        assert value is None
        assert set(missing) == {"a", "b"}

    def test_min_two_operands(self):
        """min(a, b) com ambos → retorna o menor."""
        metricas = {"a": _mv(80.0), "b": _mv(60.0)}
        value, missing = evaluate_expression("min(a, b)", metricas)
        assert value == 60.0
        assert missing == []

    def test_min_one_missing(self):
        """min(a, b) com um ausente → retorna o disponível."""
        metricas = {"b": _mv(60.0)}
        value, missing = evaluate_expression("min(a, b)", metricas)
        assert value == 60.0
        assert missing == ["a"]

    def test_simple_metric_present(self):
        """Expressão simples (nome de métrica) presente."""
        metricas = {"h5": _mv(25)}
        value, missing = evaluate_expression("h5", metricas)
        assert value == 25.0
        assert missing == []

    def test_simple_metric_absent(self):
        """Expressão simples (nome de métrica) ausente → None."""
        metricas: dict[str, MetricValue] = {}
        value, missing = evaluate_expression("h5", metricas)
        assert value is None
        assert missing == ["h5"]

    def test_max_three_operands_partial(self):
        """max(a, b, c) com 2 de 3 presentes."""
        metricas = {"a": _mv(10.0), "c": _mv(30.0)}
        value, missing = evaluate_expression("max(a, b, c)", metricas)
        assert value == 30.0
        assert missing == ["b"]


# ---------------------------------------------------------------------------
# melhor_posicao
# ---------------------------------------------------------------------------


SCALE_5 = ["MB", "B", "R", "F", "I"]
SCALE_8 = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]


class TestMelhorPosicao:
    """Testes para modo melhor_posicao."""

    def test_multiple_rules_satisfied_returns_best(self):
        """Várias regras satisfeitas → retorna melhor posição na escala."""
        regras = [
            {"metrica": "abdc_rating", "in": ["B"], "resultado": "B"},
            {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "MB"},
            {"metrica": "jcr_quartil", "in": ["Q2"], "resultado": "B"},
        ]
        metricas = {
            "abdc_rating": _mv("B"),
            "sjr_quartil": _mv("Q1"),
            "jcr_quartil": _mv("Q2"),
        }
        label, trail, missing = melhor_posicao(regras, metricas, SCALE_5)
        assert label == "MB"

    def test_single_rule_satisfied(self):
        """Apenas uma regra satisfeita → retorna esse resultado."""
        regras = [
            {"metrica": "abdc_rating", "in": ["A", "A*"], "resultado": "MB"},
            {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "MB"},
        ]
        metricas = {"sjr_quartil": _mv("Q1")}
        label, trail, missing = melhor_posicao(regras, metricas, SCALE_5)
        assert label == "MB"
        assert "abdc_rating" in missing

    def test_no_rules_satisfied(self):
        """Nenhuma regra satisfeita → None."""
        regras = [
            {"metrica": "abdc_rating", "in": ["A*"], "resultado": "MB"},
        ]
        metricas = {"abdc_rating": _mv("C")}
        label, trail, missing = melhor_posicao(regras, metricas, SCALE_5)
        assert label is None

    def test_all_metrics_missing(self):
        """Todas as métricas ausentes → None, missing não-vazio."""
        regras = [
            {"metrica": "abdc_rating", "in": ["A"], "resultado": "MB"},
            {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "MB"},
        ]
        metricas: dict[str, MetricValue] = {}
        label, trail, missing = melhor_posicao(regras, metricas, SCALE_5)
        assert label is None
        assert "abdc_rating" in missing
        assert "sjr_quartil" in missing

    def test_trail_entries_created(self):
        """Trilha contém entradas para cada regra avaliada."""
        regras = [
            {"metrica": "x", "in": ["A"], "resultado": "MB"},
            {"metrica": "y", "in": ["Q1"], "resultado": "B"},
        ]
        metricas = {"x": _mv("A")}
        label, trail, missing = melhor_posicao(regras, metricas, SCALE_5)
        assert len(trail) == 2
        assert trail[0].etapa == "regra_ativada"
        assert trail[1].etapa == "regra_avaliada"


# ---------------------------------------------------------------------------
# metrica_unica
# ---------------------------------------------------------------------------


class TestMetricaUnica:
    """Testes para modo metrica_unica."""

    def test_value_in_first_range(self):
        """Valor na primeira faixa → melhor resultado."""
        regras = [
            {"min": 87.5, "resultado": "A1"},
            {"min": 75.0, "max": 87.5, "resultado": "A2"},
            {"min": 0, "max": 75.0, "resultado": "A3"},
        ]
        metricas = {"percentil": _mv(90.0)}
        label, trail, missing = metrica_unica(regras, metricas, SCALE_8, "percentil")
        assert label == "A1"

    def test_value_in_middle_range(self):
        """Valor na faixa intermediária."""
        regras = [
            {"min": 87.5, "resultado": "A1"},
            {"min": 75.0, "max": 87.5, "resultado": "A2"},
            {"min": 0, "max": 75.0, "resultado": "A3"},
        ]
        metricas = {"percentil": _mv(80.0)}
        label, trail, missing = metrica_unica(regras, metricas, SCALE_8, "percentil")
        assert label == "A2"

    def test_expression_max(self):
        """Expressão max(a, b) corretamente avaliada."""
        regras = [
            {"min": 87.5, "resultado": "A1"},
            {"min": 75.0, "max": 87.5, "resultado": "A2"},
        ]
        metricas = {"a": _mv(80.0), "b": _mv(90.0)}
        label, trail, missing = metrica_unica(regras, metricas, SCALE_8, "max(a, b)")
        assert label == "A1"

    def test_expression_all_missing(self):
        """Expressão com todos operandos ausentes → None."""
        regras = [{"min": 87.5, "resultado": "A1"}]
        metricas: dict[str, MetricValue] = {}
        label, trail, missing = metrica_unica(
            regras, metricas, SCALE_8, "max(a, b)"
        )
        assert label is None
        assert set(missing) == {"a", "b"}

    def test_value_matches_no_range(self):
        """Valor não cai em nenhuma faixa → None."""
        regras = [
            {"min": 50, "max": 100, "resultado": "A1"},
        ]
        metricas = {"x": _mv(30.0)}
        label, trail, missing = metrica_unica(regras, metricas, SCALE_8, "x")
        assert label is None

    def test_trail_has_expressao_avaliada(self):
        """Trilha inclui entrada 'expressao_avaliada'."""
        regras = [{"min": 0, "resultado": "A1"}]
        metricas = {"x": _mv(50.0)}
        label, trail, missing = metrica_unica(regras, metricas, SCALE_8, "x")
        assert trail[0].etapa == "expressao_avaliada"
        assert trail[0].valor == 50.0


# ---------------------------------------------------------------------------
# primeira_regra
# ---------------------------------------------------------------------------


class TestPrimeiraRegra:
    """Testes para modo primeira_regra."""

    def test_first_match_returned(self):
        """Retorna resultado da primeira regra satisfeita."""
        regras = [
            {"metrica": "x", "in": ["A"], "resultado": "R1"},
            {"metrica": "y", "in": ["B"], "resultado": "R2"},
        ]
        metricas = {"x": _mv("A"), "y": _mv("B")}
        label, trail, missing = primeira_regra(regras, metricas, SCALE_5)
        assert label == "R1"

    def test_second_match_when_first_fails(self):
        """Primeira regra falha → retorna segunda."""
        regras = [
            {"metrica": "x", "in": ["A"], "resultado": "R1"},
            {"metrica": "y", "in": ["B"], "resultado": "R2"},
        ]
        metricas = {"y": _mv("B")}
        label, trail, missing = primeira_regra(regras, metricas, SCALE_5)
        assert label == "R2"

    def test_no_match(self):
        """Nenhuma regra satisfeita → None."""
        regras = [
            {"metrica": "x", "in": ["Z"], "resultado": "R1"},
        ]
        metricas = {"x": _mv("A")}
        label, trail, missing = primeira_regra(regras, metricas, SCALE_5)
        assert label is None

    def test_rule_without_metrica_always_matches(self):
        """Regra sem campo 'metrica' é sempre satisfeita."""
        regras = [
            {"resultado": "NAO_CLASSIFICAVEL"},
        ]
        metricas: dict[str, MetricValue] = {}
        label, trail, missing = primeira_regra(regras, metricas, SCALE_5)
        assert label == "NAO_CLASSIFICAVEL"

    def test_stops_at_first_match(self):
        """Para na primeira regra satisfeita, não avalia restantes."""
        regras = [
            {"metrica": "x", "in": ["A"], "resultado": "R1"},
            {"metrica": "x", "in": ["A"], "resultado": "R2"},
        ]
        metricas = {"x": _mv("A")}
        label, trail, missing = primeira_regra(regras, metricas, SCALE_5)
        assert label == "R1"
        # Trilha deve ter apenas 1 entrada (parou no primeiro match)
        assert len(trail) == 1


# ---------------------------------------------------------------------------
# apply_adjustments
# ---------------------------------------------------------------------------


class TestApplyAdjustments:
    """Testes para aplicação de ajustes pós-classificação."""

    def test_efeito_plus_one(self):
        """Efeito +1 eleva um nível na escala."""
        ajustes = [{"se": "cond", "efeito": "+1"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "B"

    def test_efeito_plus_two(self):
        """Efeito +2 eleva dois níveis."""
        ajustes = [{"se": "cond", "efeito": "+2"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "MB"

    def test_efeito_minus_one(self):
        """Efeito -1 rebaixa um nível."""
        ajustes = [{"se": "cond", "efeito": "-1"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("B", ajustes, SCALE_5, metricas, None)
        assert label == "R"

    def test_efeito_respects_scale_upper_bound(self):
        """Efeito não ultrapassa primeiro rótulo (melhor)."""
        ajustes = [{"se": "cond", "efeito": "+5"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "MB"  # Não vai além do melhor

    def test_efeito_respects_scale_lower_bound(self):
        """Efeito não ultrapassa último rótulo (pior)."""
        ajustes = [{"se": "cond", "efeito": "-10"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "I"  # Não vai além do pior

    def test_resultado_direct_assignment(self):
        """Ajuste com 'resultado' atribui diretamente."""
        ajustes = [{"se": "cond", "resultado": "MB"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("F", ajustes, SCALE_5, metricas, None)
        assert label == "MB"

    def test_teto_limits_adjustment(self):
        """Teto impede ajuste de ir além do limite."""
        ajustes = [{"se": "cond", "efeito": "+3", "teto": "B"}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("I", ajustes, SCALE_5, metricas, None)
        assert label == "B"  # Não ultrapassa teto

    def test_qualitativo_signal_only(self):
        """Ajuste qualitativo: sinaliza na trilha, NÃO aplica."""
        ajustes = [{"se": "cond", "efeito": "+2", "qualitativo": True}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "R"  # Não mudou!
        assert trail[0].etapa == "ajuste_sinalizado"

    def test_condition_not_met_skips_adjustment(self):
        """Condição não atendida → ajuste ignorado."""
        ajustes = [{"se": "cond", "efeito": "+1"}]
        metricas: dict[str, MetricValue] = {}  # Condição ausente
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "R"
        assert trail == []

    def test_teto_qualitativo(self):
        """teto_qualitativo limita sinalizações qualitativas."""
        ajustes = [{"se": "cond", "efeito": "+3", "qualitativo": True}]
        metricas = {"cond": _mv(True)}
        label, trail = apply_adjustments("A5", ajustes, SCALE_8, metricas, "A3")
        # Sinalização: o alvo teórico respeita teto_qualitativo A3
        assert trail[0].etapa == "ajuste_sinalizado"
        assert trail[0].resultado == "A3"  # limitado pelo teto_qualitativo

    def test_condition_with_and_operator(self):
        """Condição com && (conjunção)."""
        ajustes = [{"se": "cond_a && cond_b", "efeito": "+1"}]
        metricas = {"cond_a": _mv(True), "cond_b": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "B"

    def test_condition_and_one_missing(self):
        """Condição && com uma parte ausente → não atendida."""
        ajustes = [{"se": "cond_a && cond_b", "efeito": "+1"}]
        metricas = {"cond_a": _mv(True)}
        label, trail = apply_adjustments("R", ajustes, SCALE_5, metricas, None)
        assert label == "R"


# ---------------------------------------------------------------------------
# classify — Orquestração completa
# ---------------------------------------------------------------------------


@pytest.fixture
def area_rules_simple():
    """Regras de área sintéticas para testes de classify."""
    return {
        "area": 99,
        "nome": "Teste",
        "vigencia": "2025-2028",
        "status": "experimental",
        "data_extracao": "2026-07-01",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4"],
            "pontos": {"A1": 4, "A2": 3, "A3": 2, "A4": 1},
        },
        "veiculos": {
            "journalArticle": {
                "combinacao": "metrica_unica",
                "metrica": "percentil",
                "regras": [
                    {"min": 75, "resultado": "A1"},
                    {"min": 50, "max": 75, "resultado": "A2"},
                    {"min": 25, "max": 50, "resultado": "A3"},
                    {"min": 0, "max": 25, "resultado": "A4"},
                ],
                "ajustes": [],
                "fallback": "NAO_CLASSIFICAVEL",
            },
            "conferencePaper": {
                "combinacao": "primeira_regra",
                "regras": [
                    {"resultado": "NAO_CLASSIFICAVEL", "nota": "Não automatizável"},
                ],
                "fallback": "NAO_CLASSIFICAVEL",
            },
        },
    }


@pytest.fixture
def area_rules_melhor_posicao():
    """Regras com modo melhor_posicao e ajustes."""
    return {
        "area": 27,
        "nome": "Administração",
        "vigencia": "2025-2028",
        "status": "experimental",
        "data_extracao": "2026-07-01",
        "escala": {
            "rotulos": ["MB", "B", "R", "F", "I"],
            "pontos": {"MB": 8, "B": 4, "R": 2, "F": 1, "I": 0},
        },
        "veiculos": {
            "journalArticle": {
                "combinacao": "melhor_posicao",
                "regras": [
                    {"metrica": "abdc_rating", "in": ["A", "A*"], "resultado": "MB"},
                    {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "MB"},
                    {"metrica": "abdc_rating", "in": ["B"], "resultado": "B"},
                    {"metrica": "sjr_quartil", "in": ["Q2"], "resultado": "B"},
                    {"metrica": "abdc_rating", "in": ["C"], "resultado": "R"},
                    {"metrica": "sjr_quartil", "in": ["Q3"], "resultado": "R"},
                    {"metrica": "sjr_quartil", "in": ["Q4"], "resultado": "F"},
                ],
                "ajustes": [
                    {"se": "indexado_scielo_br", "efeito": "+1", "teto": "B"},
                ],
                "fallback": "NAO_CLASSIFICAVEL",
            },
        },
    }


class TestClassify:
    """Testes para classify() — orquestração completa."""

    def test_basic_classification_completo(self, area_rules_simple):
        """Classificação básica com todas métricas presentes → COMPLETO."""
        metricas = {"percentil": _mv(80.0)}
        v = classify("journalArticle", metricas, area_rules_simple)
        assert v.estrato == "A1"
        assert v.estado == "COMPLETO"
        assert v.area == 99

    def test_type_not_in_veiculos(self, area_rules_simple):
        """Tipo não definido em veículos → NAO_CLASSIFICAVEL."""
        metricas = {"x": _mv(1)}
        v = classify("book", metricas, area_rules_simple)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"

    def test_fallback_when_no_rule_matches(self, area_rules_simple):
        """Nenhuma regra corresponde ao valor → fallback."""
        metricas = {"percentil": _mv(-5.0)}  # Abaixo de todas faixas
        v = classify("journalArticle", metricas, area_rules_simple)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"

    def test_fallback_no_metrics_at_all(self, area_rules_simple):
        """Métrica ausente → NAO_CLASSIFICAVEL."""
        metricas: dict[str, MetricValue] = {}
        v = classify("journalArticle", metricas, area_rules_simple)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"

    def test_estimativa_conservadora(self):
        """Expressão max com operando parcial → ESTIMATIVA_CONSERVADORA."""
        rules = {
            "area": 2,
            "nome": "Comp",
            "data_extracao": "2026-07-01",
            "escala": {"rotulos": ["A1", "A2", "A3", "A4"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(wos, scopus)",
                    "regras": [
                        {"min": 75, "resultado": "A1"},
                        {"min": 50, "max": 75, "resultado": "A2"},
                        {"min": 0, "max": 50, "resultado": "A3"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        metricas = {"scopus": _mv(80.0)}  # wos ausente
        v = classify("journalArticle", metricas, rules)
        assert v.estrato == "A1"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"

    def test_primeira_regra_mode(self, area_rules_simple):
        """Modo primeira_regra: retorna resultado da primeira regra."""
        metricas: dict[str, MetricValue] = {}
        v = classify("conferencePaper", metricas, area_rules_simple)
        assert v.estrato == "NAO_CLASSIFICAVEL"

    def test_melhor_posicao_with_adjustments(self, area_rules_melhor_posicao):
        """Modo melhor_posicao com ajuste: SciELO eleva R → B."""
        metricas = {
            "abdc_rating": _mv("C"),
            "indexado_scielo_br": _mv(True),
        }
        v = classify("journalArticle", metricas, area_rules_melhor_posicao)
        assert v.estrato == "B"  # R + 1 nível = B
        assert v.estado == "ESTIMATIVA_CONSERVADORA"  # sjr_quartil ausente

    def test_melhor_posicao_teto_adjustment(self, area_rules_melhor_posicao):
        """Ajuste com teto: mesmo com +1, não ultrapassa B."""
        metricas = {
            "abdc_rating": _mv("B"),
            "indexado_scielo_br": _mv(True),
        }
        v = classify("journalArticle", metricas, area_rules_melhor_posicao)
        assert v.estrato == "B"  # B + 1 = MB, mas teto = B → fica em B

    def test_trilha_has_entries(self, area_rules_simple):
        """Trilha de decisão tem pelo menos uma entrada."""
        metricas = {"percentil": _mv(60.0)}
        v = classify("journalArticle", metricas, area_rules_simple)
        assert len(v.trilha) > 0
        # Deve ter expressao_avaliada e regra_ativada
        etapas = [t.etapa for t in v.trilha]
        assert "expressao_avaliada" in etapas
        assert "regra_ativada" in etapas

    def test_data_snapshot_propagated(self, area_rules_simple):
        """data_snapshot é propagado no Verdict."""
        metricas = {"percentil": _mv(80.0)}
        v = classify("journalArticle", metricas, area_rules_simple)
        assert v.data_snapshot == "2026-07-01"


# ---------------------------------------------------------------------------
# classify — Testes de fallback NAO_CONSIDERADO
# ---------------------------------------------------------------------------


class TestClassifyFallbackNaoConsiderado:
    """Testes para fallback NAO_CONSIDERADO."""

    def test_nao_considerado_fallback(self):
        """Fallback NAO_CONSIDERADO quando nenhuma regra match."""
        rules = {
            "area": 2,
            "nome": "Comp",
            "data_extracao": "2026-07-01",
            "escala": {"rotulos": ["A1", "A2", "A3"]},
            "veiculos": {
                "conferencePaper": {
                    "combinacao": "metrica_unica",
                    "metrica": "h5",
                    "regras": [
                        {"min": 35, "resultado": "A1"},
                        {"min": 25, "max": 35, "resultado": "A2"},
                        {"min": 1, "max": 25, "resultado": "A3"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CONSIDERADO",
                }
            },
        }
        # h5 = 0 → não cai em nenhuma faixa
        metricas = {"h5": _mv(0)}
        v = classify("conferencePaper", metricas, rules)
        assert v.estrato == "NAO_CONSIDERADO"
        assert v.estado == "NAO_CONSIDERADO"

    def test_fallback_trail_entry(self):
        """Trilha registra fallback quando nenhuma regra satisfeita."""
        rules = {
            "area": 99,
            "nome": "T",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["X", "Y"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "m",
                    "regras": [{"min": 100, "resultado": "X"}],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        metricas = {"m": _mv(50)}
        v = classify("journalArticle", metricas, rules)
        fallback_entries = [t for t in v.trilha if t.etapa == "fallback"]
        assert len(fallback_entries) == 1
        assert fallback_entries[0].resultado == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# classify — Estado determination
# ---------------------------------------------------------------------------


class TestClassifyEstado:
    """Testes para determinação correta de estado."""

    def test_completo_all_operands(self):
        """Todos operandos presentes → COMPLETO."""
        rules = {
            "area": 2,
            "nome": "Comp",
            "data_extracao": "2026-07-01",
            "escala": {"rotulos": ["A1", "A2"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(wos, scopus)",
                    "regras": [
                        {"min": 75, "resultado": "A1"},
                        {"min": 0, "max": 75, "resultado": "A2"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        metricas = {"wos": _mv(90.0), "scopus": _mv(85.0)}
        v = classify("journalArticle", metricas, rules)
        assert v.estado == "COMPLETO"

    def test_estimativa_conservadora_partial(self):
        """Operandos parciais → ESTIMATIVA_CONSERVADORA."""
        rules = {
            "area": 2,
            "nome": "Comp",
            "data_extracao": "2026-07-01",
            "escala": {"rotulos": ["A1", "A2"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(wos, scopus)",
                    "regras": [
                        {"min": 75, "resultado": "A1"},
                        {"min": 0, "max": 75, "resultado": "A2"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        metricas = {"scopus": _mv(90.0)}  # wos ausente
        v = classify("journalArticle", metricas, rules)
        assert v.estado == "ESTIMATIVA_CONSERVADORA"

    def test_melhor_posicao_partial_metrics(self):
        """melhor_posicao com métricas parciais → ESTIMATIVA_CONSERVADORA."""
        rules = {
            "area": 27,
            "nome": "Adm",
            "data_extracao": "2026-07-01",
            "escala": {"rotulos": ["MB", "B", "R", "F", "I"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "melhor_posicao",
                    "regras": [
                        {"metrica": "abdc_rating", "in": ["A"], "resultado": "MB"},
                        {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "MB"},
                        {"metrica": "sjr_quartil", "in": ["Q2"], "resultado": "B"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        metricas = {"sjr_quartil": _mv("Q2")}  # abdc_rating ausente
        v = classify("journalArticle", metricas, rules)
        assert v.estrato == "B"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"


# ---------------------------------------------------------------------------
# Testes de integração com cenários realistas (fixtures sintéticas)
# ---------------------------------------------------------------------------


class TestClassifyRealisticScenarios:
    """Cenários realistas baseados nas áreas de Computação e Administração."""

    @pytest.fixture
    def area02_like(self):
        """Regras similares à Área 02 com métrica_unica + max."""
        return {
            "area": 2,
            "nome": "Computação (sintética)",
            "data_extracao": "2026-07-01",
            "escala": {
                "rotulos": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"],
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
                        {
                            "se": "periodico_sbc",
                            "efeito": "+2",
                            "qualitativo": True,
                        },
                    ],
                    "teto_qualitativo": "A3",
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
                        {"min": 1, "max": 15, "resultado": "A5"},
                    ],
                    "ajustes": [],
                    "fallback": "NAO_CONSIDERADO",
                },
            },
        }

    def test_journal_a1_both_metrics(self, area02_like):
        """Periódico com ambos percentis altos → A1 COMPLETO."""
        metricas = {
            "wos_percentil": _mv(95.0),
            "scopus_percentil": _mv(92.0),
        }
        v = classify("journalArticle", metricas, area02_like)
        assert v.estrato == "A1"
        assert v.estado == "COMPLETO"

    def test_journal_a2_single_metric(self, area02_like):
        """Periódico com apenas scopus = 80 → A2 ESTIMATIVA."""
        metricas = {"scopus_percentil": _mv(80.0)}
        v = classify("journalArticle", metricas, area02_like)
        assert v.estrato == "A2"
        assert v.estado == "ESTIMATIVA_CONSERVADORA"

    def test_journal_sbc_qualitativo_signal(self, area02_like):
        """Periódico SBC: sinaliza ajuste +2 mas não aplica."""
        metricas = {
            "wos_percentil": _mv(40.0),
            "scopus_percentil": _mv(45.0),
            "periodico_sbc": _mv(True),
        }
        v = classify("journalArticle", metricas, area02_like)
        assert v.estrato == "A5"  # Não mudou (qualitativo)
        # Trilha deve ter sinalização
        sinalizacoes = [t for t in v.trilha if t.etapa == "ajuste_sinalizado"]
        assert len(sinalizacoes) == 1

    def test_conference_a1(self, area02_like):
        """Evento com h5 alto → A1."""
        metricas = {"h5_google_scholar": _mv(40)}
        v = classify("conferencePaper", metricas, area02_like)
        assert v.estrato == "A1"
        assert v.estado == "COMPLETO"

    def test_conference_no_h5_nao_considerado(self, area02_like):
        """Evento sem h5 → NAO_CONSIDERADO."""
        metricas: dict[str, MetricValue] = {}
        v = classify("conferencePaper", metricas, area02_like)
        assert v.estrato == "NAO_CONSIDERADO"
        assert v.estado == "NAO_CONSIDERADO"

    def test_book_not_defined(self, area02_like):
        """Livro não definido em veículos → NAO_CLASSIFICAVEL."""
        metricas = {"qualquer": _mv(1)}
        v = classify("book", metricas, area02_like)
        assert v.estrato == "NAO_CLASSIFICAVEL"

    def test_teto_qualitativo_respected_in_signal(self, area02_like):
        """Sinalização qualitativa respeita teto_qualitativo A3."""
        # A8 + 2 = A6, mas se fosse não-qualitativo seria A6.
        # Como é qualitativo apenas sinaliza. O alvo teórico
        # respeitando teto_qualitativo seria min(A6, A3) = A6
        # (A6 é pior que A3, logo o teto não limita)
        metricas = {
            "wos_percentil": _mv(5.0),  # → A8
            "scopus_percentil": _mv(5.0),
            "periodico_sbc": _mv(True),
        }
        v = classify("journalArticle", metricas, area02_like)
        assert v.estrato == "A8"  # Não aplicado
        sinais = [t for t in v.trilha if t.etapa == "ajuste_sinalizado"]
        assert len(sinais) == 1
        # O resultado sinalizado = A6 (A8 + 2 posições)
        assert sinais[0].resultado == "A6"
