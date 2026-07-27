"""Testes para apply_adjustments em pipeline/engine.py.

Valida:
- Efeito (+N/-N): deslocamento na escala
- Resultado direto: atribuição direta de rótulo
- Teto: limite máximo de melhoria por ajuste
- Teto qualitativo: limite para sinalizações qualitativas
- Ajustes qualitativos: sinalização sem aplicação
- Limites de escala: nunca ultrapassa primeiro/último rótulo
- Condições simples e com conjunção (&&)
- Múltiplos ajustes em sequência

Requirements: 2.6, 2.7
"""

import pytest

from pipeline.engine import apply_adjustments, TrailEntry
from pipeline.vehicles import MetricValue


# ---------------------------------------------------------------------------
# Escalas de teste
# ---------------------------------------------------------------------------

SCALE_5 = ["MB", "B", "R", "F", "I"]  # Área 27 style (melhor → pior)
SCALE_4 = ["A1", "A2", "A3", "A4"]  # 4-item scale


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mv(valor, fonte_id="test", data_fonte="2025-01-01"):
    """Cria MetricValue de teste."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


def _metricas_truthy(*names: str) -> dict[str, MetricValue]:
    """Cria dict de métricas com valores truthy para as chaves dadas."""
    return {name: _mv(True) for name in names}


# ---------------------------------------------------------------------------
# Efeito +N: melhora (menor índice)
# ---------------------------------------------------------------------------


class TestEfeitoPositivo:
    """Efeito com valor positivo melhora o estrato (menor índice na escala)."""

    def test_efeito_plus_1_r_para_b(self):
        """Efeito +1: R → B na escala [MB, B, R, F, I]."""
        adjustments = [{"se": "cond", "efeito": "+1"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "B"
        assert len(trail) == 1
        assert trail[0].etapa == "ajuste_aplicado"
        assert trail[0].resultado == "B"

    def test_efeito_plus_2_f_para_b(self):
        """Efeito +2: F → B na escala [MB, B, R, F, I]."""
        adjustments = [{"se": "cond", "efeito": "+2"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("F", adjustments, SCALE_5, metricas, None)

        assert result == "B"

    def test_efeito_beyond_scale_limit_capped(self):
        """Efeito +5 de A3 em escala de 4 itens → capped em A1 (índice 0)."""
        adjustments = [{"se": "cond", "efeito": "+5"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("A3", adjustments, SCALE_4, metricas, None)

        assert result == "A1"  # Capped ao melhor rótulo


# ---------------------------------------------------------------------------
# Efeito -N: piora (maior índice)
# ---------------------------------------------------------------------------


class TestEfeitoNegativo:
    """Efeito com valor negativo piora o estrato (maior índice na escala)."""

    def test_efeito_minus_1_b_para_r(self):
        """Efeito -1: B → R na escala [MB, B, R, F, I]."""
        adjustments = [{"se": "cond", "efeito": "-1"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("B", adjustments, SCALE_5, metricas, None)

        assert result == "R"

    def test_efeito_negativo_beyond_scale_limit_capped(self):
        """Efeito -10 de A2 em escala de 4 itens → capped em A4 (último)."""
        adjustments = [{"se": "cond", "efeito": "-10"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("A2", adjustments, SCALE_4, metricas, None)

        assert result == "A4"  # Capped ao pior rótulo


# ---------------------------------------------------------------------------
# Efeito com teto
# ---------------------------------------------------------------------------


class TestEfeitoComTeto:
    """Teto limita o resultado do efeito."""

    def test_efeito_plus_2_com_teto_b(self):
        """Efeito +2 de R mas teto=B → B (não MB)."""
        adjustments = [{"se": "cond", "efeito": "+2", "teto": "B"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "B"  # Teto impede chegar a MB

    def test_efeito_plus_1_ja_no_teto(self):
        """Efeito +1 de B com teto=B → B (já está no teto, não pode melhorar)."""
        adjustments = [{"se": "cond", "efeito": "+1", "teto": "B"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("B", adjustments, SCALE_5, metricas, None)

        # Efeito desloca para MB mas teto impede
        assert result == "B"

    def test_efeito_sem_teto_pode_chegar_ao_melhor(self):
        """Efeito +2 de R sem teto → MB (o melhor da escala)."""
        adjustments = [{"se": "cond", "efeito": "+2"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "MB"


# ---------------------------------------------------------------------------
# Resultado direto
# ---------------------------------------------------------------------------


class TestResultadoDireto:
    """Resultado direto sobrescreve o rótulo atual."""

    def test_resultado_direto_override(self):
        """Resultado direto sobrescreve independentemente do rótulo atual."""
        adjustments = [{"se": "cond", "resultado": "A1"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("A4", adjustments, SCALE_4, metricas, None)

        assert result == "A1"

    def test_resultado_direto_com_teto(self):
        """Resultado direto respeita teto do ajuste."""
        adjustments = [{"se": "cond", "resultado": "A1", "teto": "A2"}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("A4", adjustments, SCALE_4, metricas, None)

        assert result == "A2"  # Teto impede A1


# ---------------------------------------------------------------------------
# Ajustes qualitativos
# ---------------------------------------------------------------------------


class TestQualitativo:
    """Ajustes qualitativos sinalizam sem aplicar."""

    def test_qualitativo_nao_altera_label(self):
        """Qualitativo=true: sinaliza mas NÃO muda o rótulo atual."""
        adjustments = [{"se": "cond", "efeito": "+2", "qualitativo": True}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "R"  # Não mudou!
        assert len(trail) == 1
        assert trail[0].etapa == "ajuste_sinalizado"

    def test_qualitativo_registra_alvo_na_trilha(self):
        """Qualitativo registra o resultado teórico na trilha."""
        adjustments = [{"se": "cond", "efeito": "+1", "qualitativo": True}]
        metricas = _metricas_truthy("cond")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert trail[0].resultado == "B"  # Alvo teórico (sem teto_qualitativo)

    def test_qualitativo_com_teto_qualitativo(self):
        """Teto_qualitativo limita a sinalização qualitativa."""
        adjustments = [{"se": "cond", "efeito": "+3", "qualitativo": True}]
        metricas = _metricas_truthy("cond")

        # teto_qualitativo = "B" impede sinalizar acima de B
        result, trail = apply_adjustments("F", adjustments, SCALE_5, metricas, "B")

        assert result == "F"  # Não aplicado (qualitativo)
        assert trail[0].resultado == "B"  # Alvo limitado pelo teto_qualitativo (não MB)

    def test_qualitativo_teto_qualitativo_a3(self):
        """Teto_qualitativo A3 para escala de 4 (cenário Área 02)."""
        scale_8 = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]
        adjustments = [{"se": "periodico_sbc", "efeito": "+3", "qualitativo": True}]
        metricas = _metricas_truthy("periodico_sbc")

        # A6 com +3 → A3, mas teto_qualitativo A3 → A3 (exatamente no limite)
        result, trail = apply_adjustments("A6", adjustments, scale_8, metricas, "A3")

        assert result == "A6"  # Não aplicado
        assert trail[0].resultado == "A3"  # Limitado a A3

    def test_qualitativo_teto_qualitativo_efetivo(self):
        """Teto_qualitativo impede sinalizar acima do limite."""
        scale_8 = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]
        adjustments = [{"se": "ce_sbc_top10", "efeito": "+5", "qualitativo": True}]
        metricas = _metricas_truthy("ce_sbc_top10")

        # A5 com +5 → A1 (teórico), mas teto_qualitativo A3 → sinaliza A3
        result, trail = apply_adjustments("A5", adjustments, scale_8, metricas, "A3")

        assert result == "A5"  # Não aplicado
        assert trail[0].resultado == "A3"  # Limitado a A3 (não A1)


# ---------------------------------------------------------------------------
# Condição não satisfeita
# ---------------------------------------------------------------------------


class TestCondicaoNaoSatisfeita:
    """Ajuste é ignorado se condição não é satisfeita."""

    def test_condicao_nao_satisfeita_skip(self):
        """Condição não satisfeita: ajuste completamente ignorado."""
        adjustments = [{"se": "cond_inexistente", "efeito": "+2"}]
        metricas = {}  # Sem métricas → condição falha

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "R"  # Inalterado
        assert len(trail) == 0  # Nenhuma entrada na trilha

    def test_condicao_com_valor_falsy(self):
        """Condição com valor falsy (0, False, None, '') → skip."""
        adjustments = [{"se": "cond", "efeito": "+1"}]
        metricas = {"cond": _mv(0)}  # valor falsy

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "R"  # Inalterado

    def test_condicao_com_valor_truthy(self):
        """Condição com valor truthy → aplica."""
        adjustments = [{"se": "cond", "efeito": "+1"}]
        metricas = {"cond": _mv(1)}  # valor truthy

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "B"


# ---------------------------------------------------------------------------
# Múltiplos ajustes em sequência
# ---------------------------------------------------------------------------


class TestMultiplosAjustes:
    """Múltiplos ajustes aplicados em ordem declarada."""

    def test_multiplos_ajustes_em_sequencia(self):
        """Ajustes aplicados na ordem: primeiro +1, depois -1 → volta ao original."""
        adjustments = [
            {"se": "cond_a", "efeito": "+1"},
            {"se": "cond_b", "efeito": "-1"},
        ]
        metricas = _metricas_truthy("cond_a", "cond_b")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        # R → B (primeiro) → R (segundo)
        assert result == "R"
        assert len(trail) == 2

    def test_multiplos_ajustes_parciais(self):
        """Primeiro ajuste aplica, segundo pula (condição não satisfeita)."""
        adjustments = [
            {"se": "cond_a", "efeito": "+1"},
            {"se": "cond_b", "efeito": "-2"},  # cond_b não disponível
        ]
        metricas = _metricas_truthy("cond_a")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "B"  # Só primeiro ajuste aplicado
        assert len(trail) == 1

    def test_ajuste_acumula_sobre_resultado_anterior(self):
        """Segundo ajuste opera sobre o resultado do primeiro."""
        adjustments = [
            {"se": "cond_a", "efeito": "+1"},  # R → B
            {"se": "cond_b", "efeito": "+1"},  # B → MB
        ]
        metricas = _metricas_truthy("cond_a", "cond_b")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "MB"

    def test_qualitativo_nao_afeta_proximos_ajustes(self):
        """Ajuste qualitativo não modifica label → próximo ajuste parte do original."""
        adjustments = [
            {"se": "cond_a", "efeito": "+2", "qualitativo": True},  # Sinaliza apenas
            {"se": "cond_b", "efeito": "+1"},  # Opera sobre label não modificado
        ]
        metricas = _metricas_truthy("cond_a", "cond_b")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        # Qualitativo não aplica, depois +1 de R → B
        assert result == "B"


# ---------------------------------------------------------------------------
# Condição com && (conjunção)
# ---------------------------------------------------------------------------


class TestConjuncao:
    """Condição com && requer todas as partes verdadeiras."""

    def test_conjuncao_ambas_verdadeiras(self):
        """Condição 'a && b' com ambas verdadeiras → aplica."""
        adjustments = [{"se": "indexado_scielo_br && spell_faixa", "efeito": "+1"}]
        metricas = _metricas_truthy("indexado_scielo_br", "spell_faixa")

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "B"

    def test_conjuncao_uma_ausente(self):
        """Condição 'a && b' com uma ausente → skip."""
        adjustments = [{"se": "indexado_scielo_br && spell_faixa", "efeito": "+1"}]
        metricas = _metricas_truthy("indexado_scielo_br")  # spell_faixa ausente

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "R"  # Não aplicado
        assert len(trail) == 0

    def test_conjuncao_uma_falsy(self):
        """Condição 'a && b' com uma falsy → skip."""
        adjustments = [{"se": "cond_a && cond_b", "efeito": "+1"}]
        metricas = {
            "cond_a": _mv(True),
            "cond_b": _mv(0),  # falsy
        }

        result, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert result == "R"  # Não aplicado


# ---------------------------------------------------------------------------
# Trilha de decisão
# ---------------------------------------------------------------------------


class TestTrailEntries:
    """Verifica o conteúdo das entradas na trilha."""

    def test_ajuste_aplicado_registra_efeito(self):
        """Trail entry para ajuste aplicado contém efeito e resultado."""
        adjustments = [{"se": "cond", "efeito": "+1"}]
        metricas = _metricas_truthy("cond")

        _, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        entry = trail[0]
        assert entry.etapa == "ajuste_aplicado"
        assert entry.metrica == "cond"
        assert entry.valor == "+1"
        assert entry.resultado == "B"

    def test_ajuste_sinalizado_registra_condicao(self):
        """Trail entry para ajuste sinalizado contém condição e alvo."""
        adjustments = [{"se": "periodico_sbc", "efeito": "+1", "qualitativo": True}]
        metricas = _metricas_truthy("periodico_sbc")

        _, trail = apply_adjustments("A4", adjustments, SCALE_4, metricas, None)

        entry = trail[0]
        assert entry.etapa == "ajuste_sinalizado"
        assert entry.metrica == "periodico_sbc"
        assert entry.resultado == "A3"  # A4 com +1 → A3

    def test_nenhum_ajuste_aplicado_trilha_vazia(self):
        """Se nenhuma condição é satisfeita, trilha é vazia."""
        adjustments = [
            {"se": "cond_x", "efeito": "+1"},
            {"se": "cond_y", "resultado": "MB"},
        ]
        metricas = {}  # Nenhuma condição satisfeita

        _, trail = apply_adjustments("R", adjustments, SCALE_5, metricas, None)

        assert trail == []
