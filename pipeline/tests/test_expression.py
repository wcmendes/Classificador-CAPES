"""Testes para evaluate_expression — fixtures sintéticas apenas."""

import pytest

from pipeline.engine import evaluate_expression
from pipeline.vehicles import MetricValue


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mv(valor, fonte_id="test", data_fonte="2025-01-01"):
    """Atalho para criar MetricValue em testes."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


# ─── max() com todos operandos presentes ─────────────────────────────────────


class TestMaxAllPresent:
    """max(...) com todos os operandos disponíveis."""

    def test_max_dois_operandos(self):
        metricas = {
            "wos_percentil": _mv(80.0),
            "scopus_percentil": _mv(90.0),
        }
        valor, ausentes = evaluate_expression(
            "max(wos_percentil, scopus_percentil)", metricas
        )
        assert valor == 90.0
        assert ausentes == []

    def test_max_tres_operandos(self):
        metricas = {
            "a": _mv(10.0),
            "b": _mv(50.0),
            "c": _mv(30.0),
        }
        valor, ausentes = evaluate_expression("max(a, b, c)", metricas)
        assert valor == 50.0
        assert ausentes == []

    def test_max_operandos_iguais(self):
        metricas = {
            "x": _mv(75.0),
            "y": _mv(75.0),
        }
        valor, ausentes = evaluate_expression("max(x, y)", metricas)
        assert valor == 75.0
        assert ausentes == []


# ─── max() com operandos parciais ────────────────────────────────────────────


class TestMaxPartialOperands:
    """max(...) com um ou mais operandos ausentes."""

    def test_max_um_ausente(self):
        """Retorna max dos disponíveis e lista o ausente."""
        metricas = {
            "wos_percentil": _mv(80.0),
        }
        valor, ausentes = evaluate_expression(
            "max(wos_percentil, scopus_percentil)", metricas
        )
        assert valor == 80.0
        assert ausentes == ["scopus_percentil"]

    def test_max_primeiro_ausente(self):
        """Operando ausente é o primeiro da lista."""
        metricas = {
            "scopus_percentil": _mv(65.0),
        }
        valor, ausentes = evaluate_expression(
            "max(wos_percentil, scopus_percentil)", metricas
        )
        assert valor == 65.0
        assert ausentes == ["wos_percentil"]

    def test_max_dois_de_tres_ausentes(self):
        metricas = {
            "b": _mv(42.0),
        }
        valor, ausentes = evaluate_expression("max(a, b, c)", metricas)
        assert valor == 42.0
        assert ausentes == ["a", "c"]


# ─── max() com todos ausentes ─────────────────────────────────────────────────


class TestMaxAllAbsent:
    """max(...) sem nenhum operando disponível → (None, todos)."""

    def test_max_todos_ausentes(self):
        metricas = {}
        valor, ausentes = evaluate_expression(
            "max(wos_percentil, scopus_percentil)", metricas
        )
        assert valor is None
        assert ausentes == ["wos_percentil", "scopus_percentil"]

    def test_max_metricas_irrelevantes(self):
        """Métricas existem mas nenhuma é operando da expressão."""
        metricas = {
            "sjr_quartil": _mv("Q1"),
            "h5_google_scholar": _mv(30),
        }
        valor, ausentes = evaluate_expression(
            "max(wos_percentil, scopus_percentil)", metricas
        )
        assert valor is None
        assert ausentes == ["wos_percentil", "scopus_percentil"]


# ─── min() com todos operandos presentes ─────────────────────────────────────


class TestMinAllPresent:
    """min(...) com todos os operandos disponíveis."""

    def test_min_dois_operandos(self):
        metricas = {
            "a": _mv(30.0),
            "b": _mv(50.0),
        }
        valor, ausentes = evaluate_expression("min(a, b)", metricas)
        assert valor == 30.0
        assert ausentes == []

    def test_min_tres_operandos(self):
        metricas = {
            "x": _mv(10.0),
            "y": _mv(5.0),
            "z": _mv(20.0),
        }
        valor, ausentes = evaluate_expression("min(x, y, z)", metricas)
        assert valor == 5.0
        assert ausentes == []

    def test_min_um_ausente(self):
        metricas = {
            "a": _mv(30.0),
        }
        valor, ausentes = evaluate_expression("min(a, b)", metricas)
        assert valor == 30.0
        assert ausentes == ["b"]

    def test_min_todos_ausentes(self):
        metricas = {}
        valor, ausentes = evaluate_expression("min(a, b)", metricas)
        assert valor is None
        assert ausentes == ["a", "b"]


# ─── Expressão simples (sem parênteses) ──────────────────────────────────────


class TestPlainMetricName:
    """Métrica simples sem max/min wrapper."""

    def test_metrica_simples_presente(self):
        metricas = {"h5_google_scholar": _mv(25.0)}
        valor, ausentes = evaluate_expression("h5_google_scholar", metricas)
        assert valor == 25.0
        assert ausentes == []

    def test_metrica_simples_ausente(self):
        metricas = {}
        valor, ausentes = evaluate_expression("h5_google_scholar", metricas)
        assert valor is None
        assert ausentes == ["h5_google_scholar"]

    def test_metrica_simples_inteiro(self):
        """Valor inteiro é convertido para float."""
        metricas = {"nivel": _mv(3)}
        valor, ausentes = evaluate_expression("nivel", metricas)
        assert valor == 3.0
        assert ausentes == []


# ─── Whitespace variations ────────────────────────────────────────────────────


class TestWhitespace:
    """Expressões com espaços variados."""

    def test_espacos_internos(self):
        metricas = {
            "a": _mv(10.0),
            "b": _mv(20.0),
        }
        valor, ausentes = evaluate_expression("max( a , b )", metricas)
        assert valor == 20.0
        assert ausentes == []

    def test_espacos_ao_redor(self):
        metricas = {
            "x": _mv(5.0),
            "y": _mv(15.0),
        }
        valor, ausentes = evaluate_expression("  max(x, y)  ", metricas)
        assert valor == 15.0
        assert ausentes == []

    def test_metrica_simples_com_espacos(self):
        metricas = {"h5_google_scholar": _mv(10.0)}
        valor, ausentes = evaluate_expression("  h5_google_scholar  ", metricas)
        assert valor == 10.0
        assert ausentes == []
