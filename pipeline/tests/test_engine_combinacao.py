"""Testes para modos de combinação: melhor_posicao, metrica_unica, primeira_regra."""

import pytest

from pipeline.engine import (
    melhor_posicao,
    metrica_unica,
    primeira_regra,
)
from pipeline.vehicles import MetricValue


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mv(valor, fonte_id="test", data_fonte="2025-01-01"):
    """Atalho para criar MetricValue em testes."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


# Escala padrão para testes (melhor → pior)
ESCALA_8 = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]
ESCALA_5 = ["MB", "B", "R", "F", "I"]


# ─── melhor_posicao ──────────────────────────────────────────────────────────


class TestMelhorPosicao:
    """Testa modo melhor_posicao."""

    def test_multiplas_regras_satisfeitas_retorna_melhor_na_escala(self):
        """Quando múltiplas regras são satisfeitas, retorna o melhor resultado
        (menor índice na escala)."""
        regras = [
            {"metrica": "abdc_rating", "in": ["A*", "A"], "resultado": "MB"},
            {"metrica": "sjr_quartil", "in": ["Q1", "Q2"], "resultado": "B"},
            {"metrica": "abs_rating", "in": ["4*", "4"], "resultado": "MB"},
        ]
        metricas = {
            "abdc_rating": _mv("A"),
            "sjr_quartil": _mv("Q1"),
            "abs_rating": _mv("4"),
        }

        label, trail, missing = melhor_posicao(regras, metricas, ESCALA_5)

        assert label == "MB"
        assert missing == []

    def test_multiplas_regras_diferentes_niveis_retorna_melhor(self):
        """Três regras satisfeitas com resultados diferentes — pega o melhor."""
        regras = [
            {"metrica": "m1", "in": ["x"], "resultado": "R"},
            {"metrica": "m2", "in": ["y"], "resultado": "B"},
            {"metrica": "m3", "in": ["z"], "resultado": "F"},
        ]
        metricas = {
            "m1": _mv("x"),
            "m2": _mv("y"),
            "m3": _mv("z"),
        }

        label, trail, missing = melhor_posicao(regras, metricas, ESCALA_5)

        assert label == "B"

    def test_nenhuma_regra_satisfeita_retorna_none(self):
        """Quando nenhuma regra é satisfeita, retorna None."""
        regras = [
            {"metrica": "abdc_rating", "in": ["A*"], "resultado": "MB"},
            {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "B"},
        ]
        metricas = {
            "abdc_rating": _mv("C"),
            "sjr_quartil": _mv("Q4"),
        }

        label, trail, missing = melhor_posicao(regras, metricas, ESCALA_5)

        assert label is None

    def test_metrica_ausente_nao_satisfaz_regra(self):
        """Regra com métrica não disponível não é satisfeita."""
        regras = [
            {"metrica": "wos_percentil", "min": 75, "resultado": "A1"},
            {"metrica": "scopus_percentil", "min": 50, "resultado": "A3"},
        ]
        metricas = {
            "scopus_percentil": _mv(60),
        }

        label, trail, missing = melhor_posicao(regras, metricas, ESCALA_8)

        assert label == "A3"
        assert "wos_percentil" in missing

    def test_uma_regra_satisfeita_retorna_seu_resultado(self):
        """Apenas uma regra satisfeita — retorna seu resultado."""
        regras = [
            {"metrica": "sjr_quartil", "in": ["Q1"], "resultado": "MB"},
            {"metrica": "abdc_rating", "in": ["A*"], "resultado": "MB"},
        ]
        metricas = {
            "sjr_quartil": _mv("Q2"),
            "abdc_rating": _mv("A*"),
        }

        label, trail, missing = melhor_posicao(regras, metricas, ESCALA_5)

        assert label == "MB"

    def test_trail_registra_todas_regras(self):
        """A trilha deve conter entrada para cada regra avaliada."""
        regras = [
            {"metrica": "m1", "in": ["x"], "resultado": "B"},
            {"metrica": "m2", "in": ["y"], "resultado": "R"},
        ]
        metricas = {"m1": _mv("x"), "m2": _mv("z")}

        label, trail, missing = melhor_posicao(regras, metricas, ESCALA_5)

        assert len(trail) == 2
        assert trail[0].etapa == "regra_ativada"
        assert trail[1].etapa == "regra_avaliada"


# ─── metrica_unica ───────────────────────────────────────────────────────────


class TestMetricaUnica:
    """Testa modo metrica_unica."""

    def test_valor_cai_em_faixa_intermediaria(self):
        """Valor do percentil cai na faixa intermediária (A3: [62.5, 75))."""
        regras = [
            {"min": 87.5, "resultado": "A1"},
            {"min": 75, "max": 87.5, "resultado": "A2"},
            {"min": 62.5, "max": 75, "resultado": "A3"},
            {"min": 50, "max": 62.5, "resultado": "A4"},
            {"min": 37.5, "max": 50, "resultado": "A5"},
            {"min": 25, "max": 37.5, "resultado": "A6"},
            {"min": 12.5, "max": 25, "resultado": "A7"},
            {"min": 0, "max": 12.5, "resultado": "A8"},
        ]
        metricas = {
            "wos_percentil": _mv(70),
            "scopus_percentil": _mv(65),
        }

        label, trail, missing = metrica_unica(
            regras, metricas, ESCALA_8, "max(wos_percentil, scopus_percentil)"
        )

        # max(70, 65) = 70 → A3 (62.5 ≤ 70 < 75)
        assert label == "A3"
        assert missing == []

    def test_expressao_retorna_none_sem_operandos(self):
        """Quando nenhum operando da expressão está disponível, retorna None."""
        regras = [
            {"min": 87.5, "resultado": "A1"},
            {"min": 75, "max": 87.5, "resultado": "A2"},
            {"min": 0, "max": 75, "resultado": "A3"},
        ]
        metricas = {}  # Nenhuma métrica disponível

        label, trail, missing = metrica_unica(
            regras, metricas, ESCALA_8, "max(wos_percentil, scopus_percentil)"
        )

        assert label is None
        assert "wos_percentil" in missing
        assert "scopus_percentil" in missing

    def test_metrica_simples_sem_funcao(self):
        """Expressão simples (sem max/min) funciona como métrica direta."""
        regras = [
            {"min": 75, "resultado": "A1"},
            {"min": 50, "max": 75, "resultado": "A2"},
            {"min": 25, "max": 50, "resultado": "A3"},
            {"min": 0, "max": 25, "resultado": "A4"},
        ]
        metricas = {"test_percentil": _mv(60)}

        label, trail, missing = metrica_unica(
            regras, metricas, ESCALA_8, "test_percentil"
        )

        assert label == "A2"

    def test_um_operando_disponivel_usa_ele(self):
        """Com apenas um operando disponível na expressão max(), usa esse valor."""
        regras = [
            {"min": 87.5, "resultado": "A1"},
            {"min": 75, "max": 87.5, "resultado": "A2"},
            {"min": 0, "max": 75, "resultado": "A3"},
        ]
        metricas = {
            "scopus_percentil": _mv(80),
        }

        label, trail, missing = metrica_unica(
            regras, metricas, ESCALA_8, "max(wos_percentil, scopus_percentil)"
        )

        # Apenas scopus disponível: max(80) = 80 → A2
        assert label == "A2"
        assert "wos_percentil" in missing

    def test_valor_no_limite_inferior_da_faixa(self):
        """Valor exatamente no min inclusivo da faixa."""
        regras = [
            {"min": 75, "resultado": "A1"},
            {"min": 50, "max": 75, "resultado": "A2"},
        ]
        metricas = {"p": _mv(75)}

        label, trail, missing = metrica_unica(regras, metricas, ESCALA_8, "p")

        assert label == "A1"

    def test_trail_inclui_expressao_avaliada(self):
        """A trilha deve incluir uma entrada de expressao_avaliada."""
        regras = [{"min": 0, "resultado": "A1"}]
        metricas = {"wos_percentil": _mv(90)}

        label, trail, missing = metrica_unica(
            regras, metricas, ESCALA_8, "max(wos_percentil, scopus_percentil)"
        )

        assert trail[0].etapa == "expressao_avaliada"
        assert trail[0].valor == 90.0


# ─── primeira_regra ──────────────────────────────────────────────────────────


class TestPrimeiraRegra:
    """Testa modo primeira_regra."""

    def test_primeira_regra_satisfeita_retorna_ela(self):
        """A primeira regra satisfeita é retornada, mesmo que outras também sejam."""
        regras = [
            {"metrica": "m1", "in": ["x"], "resultado": "MB"},
            {"metrica": "m2", "in": ["y"], "resultado": "B"},
        ]
        metricas = {
            "m1": _mv("x"),
            "m2": _mv("y"),
        }

        label, trail, missing = primeira_regra(regras, metricas, ESCALA_5)

        assert label == "MB"
        # Só avaliou até a primeira satisfeita
        assert len(trail) == 1
        assert trail[0].etapa == "regra_ativada"
        assert trail[0].regra_idx == 0

    def test_segunda_regra_satisfeita_retorna_segunda(self):
        """Se apenas a segunda regra é satisfeita, retorna ela."""
        regras = [
            {"metrica": "m1", "in": ["x"], "resultado": "MB"},
            {"metrica": "m2", "in": ["y"], "resultado": "B"},
            {"metrica": "m3", "in": ["z"], "resultado": "R"},
        ]
        metricas = {
            "m1": _mv("outro"),
            "m2": _mv("y"),
            "m3": _mv("z"),
        }

        label, trail, missing = primeira_regra(regras, metricas, ESCALA_5)

        assert label == "B"
        # Avaliou a primeira (falhou) e a segunda (satisfeita)
        assert len(trail) == 2
        assert trail[0].etapa == "regra_avaliada"
        assert trail[0].regra_idx == 0
        assert trail[1].etapa == "regra_ativada"
        assert trail[1].regra_idx == 1

    def test_nenhuma_regra_satisfeita_retorna_none(self):
        """Quando nenhuma regra é satisfeita, retorna None."""
        regras = [
            {"metrica": "m1", "in": ["x"], "resultado": "MB"},
            {"metrica": "m2", "in": ["y"], "resultado": "B"},
        ]
        metricas = {
            "m1": _mv("a"),
            "m2": _mv("b"),
        }

        label, trail, missing = primeira_regra(regras, metricas, ESCALA_5)

        assert label is None
        assert len(trail) == 2

    def test_regra_sem_metrica_sempre_satisfeita(self):
        """Regra sem campo 'metrica' (ex: fallback de book) é sempre satisfeita."""
        regras = [
            {"metrica": "m1", "in": ["x"], "resultado": "MB"},
            {"resultado": "NAO_CLASSIFICAVEL"},
        ]
        metricas = {"m1": _mv("outro")}

        label, trail, missing = primeira_regra(regras, metricas, ESCALA_5)

        # Primeira falha, segunda (sem metrica) sempre satisfeita
        assert label == "NAO_CLASSIFICAVEL"
        assert trail[-1].regra_idx == 1

    def test_metrica_ausente_registra_na_lista_missing(self):
        """Métricas ausentes são registradas na lista de missing."""
        regras = [
            {"metrica": "wos_percentil", "min": 75, "resultado": "A1"},
            {"metrica": "scopus_percentil", "min": 50, "resultado": "A3"},
        ]
        metricas = {}  # Nenhuma métrica

        label, trail, missing = primeira_regra(regras, metricas, ESCALA_8)

        assert label is None
        assert "wos_percentil" in missing
        assert "scopus_percentil" in missing
