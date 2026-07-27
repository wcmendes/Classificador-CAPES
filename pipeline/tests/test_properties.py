"""Property-Based Tests (PBT) para o Classificador CAPES.

Implementa as propriedades de corretude definidas no design.md
usando Hypothesis para geração aleatória de inputs.

Cada teste valida uma invariante universal que deve ser verdadeira
para TODOS os inputs válidos, não apenas exemplos específicos.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.issn import normalize_issn, validate_check_digit, normalize_title
from pipeline.engine import (
    evaluate_rule,
    evaluate_expression,
    classify,
    apply_adjustments,
    melhor_posicao,
    metrica_unica,
    primeira_regra,
    TrailEntry,
    Verdict,
)
from pipeline.vehicles import MetricValue


# ---------------------------------------------------------------------------
# Strategies (geradores)
# ---------------------------------------------------------------------------


def _compute_issn_check_digit(digits7: str) -> str:
    """Computa dígito verificador ISSN para 7 dígitos."""
    total = sum((8 - i) * int(digits7[i]) for i in range(7))
    remainder = total % 11
    check = 11 - remainder if remainder != 0 else 0
    if check == 10:
        return "X"
    return str(check)


@st.composite
def valid_issn_strategy(draw):
    """Gera ISSNs válidos com 7 dígitos aleatórios + check digit correto."""
    digits7 = draw(st.text(alphabet="0123456789", min_size=7, max_size=7))
    check = _compute_issn_check_digit(digits7)
    return digits7 + check


def _mv(valor, fonte_id="test", data_fonte="2026-01-01"):
    """Cria MetricValue de teste."""
    return MetricValue(valor=valor, fonte_id=fonte_id, data_fonte=data_fonte)


@st.composite
def scale_strategy(draw):
    """Gera escalas de 2-8 rótulos únicos."""
    n = draw(st.integers(min_value=2, max_value=8))
    labels = draw(
        st.lists(
            st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=4),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    return labels


@st.composite
def metric_value_strategy(draw):
    """Gera MetricValue com valor numérico ou string."""
    valor = draw(
        st.one_of(
            st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
            st.integers(min_value=-1000, max_value=1000),
            st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=5),
        )
    )
    return _mv(valor)


# ---------------------------------------------------------------------------
# Property 1: ISSN round-trip
# Feature: classificador-capes, Property 1: Normalização de ISSN — round-trip
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------


class TestProperty1IssnRoundTrip:
    """normalize_issn em ISSN válido sempre produz XXXX-XXXX que passa validate_check_digit."""

    @given(issn_raw=valid_issn_strategy())
    @settings(max_examples=200)
    def test_normalize_produces_valid_format(self, issn_raw: str):
        """ISSN válido normalizado tem formato XXXX-XXXX e passa validação."""
        result = normalize_issn(issn_raw)
        assert result is not None, f"normalize_issn retornou None para ISSN válido: {issn_raw}"
        # Formato XXXX-XXXX
        assert len(result) == 9
        assert result[4] == "-"
        # Dígitos extraídos são os mesmos
        digits = result.replace("-", "")
        assert digits == issn_raw[:7] + issn_raw[7].upper()
        # Passa validação de check digit
        assert validate_check_digit(result) is True


# ---------------------------------------------------------------------------
# Property 2: Normalização de título — idempotência
# Feature: classificador-capes, Property 2: Normalização de título — idempotência
# Validates: Requirements 1.4
# ---------------------------------------------------------------------------


class TestProperty2TitleIdempotence:
    """normalize_title(normalize_title(t)) == normalize_title(t) para qualquer string."""

    @given(title=st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_idempotent(self, title: str):
        """Aplicar normalize_title duas vezes é o mesmo que uma vez."""
        once = normalize_title(title)
        twice = normalize_title(once)
        assert once == twice


# ---------------------------------------------------------------------------
# Property 4: Campo `in` — pertencimento case-sensitive
# Feature: classificador-capes, Property 4: Campo `in` case-sensitive
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------


class TestProperty4InCaseSensitive:
    """Regra com campo in é satisfeita iff valor pertence ao conjunto (case-sensitive, tipo-exata)."""

    @given(
        value=st.one_of(
            st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=5),
            st.integers(min_value=0, max_value=100),
        ),
        in_set=st.lists(
            st.one_of(
                st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=5),
                st.integers(min_value=0, max_value=100),
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=200)
    def test_in_membership(self, value, in_set):
        """value in set iff exact match including case and type."""
        rule = {"metrica": "m", "in": in_set, "resultado": "X"}
        metricas = {"m": _mv(value)}
        result = evaluate_rule(rule, metricas)
        expected = value in in_set
        assert result == expected


# ---------------------------------------------------------------------------
# Property 5: Campos min/max — semântica de limites
# Feature: classificador-capes, Property 5: Campos min/max — semântica de limites
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------


class TestProperty5MinMaxSemantics:
    """min inclusivo, max exclusivo."""

    @given(
        value=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
        lo=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
        hi=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_min_max_both(self, value, lo, hi):
        """Regra com min e max: satisfeita iff lo <= value < hi."""
        assume(lo < hi)
        rule = {"metrica": "m", "min": lo, "max": hi, "resultado": "X"}
        metricas = {"m": _mv(value)}
        result = evaluate_rule(rule, metricas)
        expected = lo <= value < hi
        assert result == expected

    @given(
        value=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
        lo=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_only_min(self, value, lo):
        """Regra com apenas min: satisfeita iff value >= lo."""
        rule = {"metrica": "m", "min": lo, "resultado": "X"}
        metricas = {"m": _mv(value)}
        result = evaluate_rule(rule, metricas)
        expected = value >= lo
        assert result == expected

    @given(
        value=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
        hi=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_only_max(self, value, hi):
        """Regra com apenas max: satisfeita iff value < hi."""
        rule = {"metrica": "m", "max": hi, "resultado": "X"}
        metricas = {"m": _mv(value)}
        result = evaluate_rule(rule, metricas)
        expected = value < hi
        assert result == expected


# ---------------------------------------------------------------------------
# Property 6: Campo `requer` — conjunção lógica
# Feature: classificador-capes, Property 6: Campo requer — conjunção
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------


class TestProperty6RequerConjunction:
    """Todas as condições devem ser verdadeiras para a regra ser satisfeita."""

    @given(
        num_conditions=st.integers(min_value=1, max_value=5),
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_all_conditions_must_be_true(self, num_conditions, data):
        """requer exige que TODAS as condições sejam truthy e presentes."""
        cond_names = [f"cond_{i}" for i in range(num_conditions)]
        # Decide for each condition: present+truthy, present+falsy, or absent
        metricas = {}
        all_true = True
        for name in cond_names:
            state = data.draw(st.sampled_from(["truthy", "falsy", "absent"]))
            if state == "truthy":
                metricas[name] = _mv(True)
            elif state == "falsy":
                metricas[name] = _mv(False)
                all_true = False
            else:
                all_true = False

        # Rule without metrica field (always satisfied by primary condition)
        # so result depends solely on requer
        rule = {"resultado": "X", "requer": cond_names}
        result = evaluate_rule(rule, metricas)
        assert result == all_true


# ---------------------------------------------------------------------------
# Property 8: Expressões max/min — operandos parciais
# Feature: classificador-capes, Property 8: Expressões max/min com parciais
# Validates: Requirements 2.8
# ---------------------------------------------------------------------------


class TestProperty8MaxMinPartialOperands:
    """max/min com operandos parciais retorna max/min dos disponíveis."""

    @given(
        func=st.sampled_from(["max", "min"]),
        values=st.lists(
            st.one_of(
                st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
                st.none(),
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=200)
    def test_partial_operands(self, func, values):
        """Result is max/min of available operands; None if all absent."""
        names = [f"op_{i}" for i in range(len(values))]
        metricas = {}
        available = []
        expected_missing = []
        for name, val in zip(names, values):
            if val is not None:
                metricas[name] = _mv(val)
                available.append(val)
            else:
                expected_missing.append(name)

        expr = f"{func}({', '.join(names)})"
        result_val, missing = evaluate_expression(expr, metricas)

        if not available:
            assert result_val is None
        else:
            if func == "max":
                assert result_val == max(available)
            else:
                assert result_val == min(available)
        assert set(missing) == set(expected_missing)


# ---------------------------------------------------------------------------
# Property 3: Modos de combinação — semântica correta
# Feature: classificador-capes, Property 3: Modos de combinação
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------


class TestProperty3CombinationModes:
    """Modos de combinação: melhor_posicao, metrica_unica, primeira_regra."""

    @given(
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_melhor_posicao_returns_best(self, data):
        """melhor_posicao retorna o melhor rótulo (menor índice na escala)."""
        scale = ["A1", "A2", "A3", "A4"]
        # Generate 2-5 rules that each check membership in a set
        n_rules = data.draw(st.integers(min_value=2, max_value=5))
        regras = []
        metricas = {}
        for i in range(n_rules):
            metric_name = f"m{i}"
            resultado = data.draw(st.sampled_from(scale))
            match_val = f"V{i}"
            regras.append({"metrica": metric_name, "in": [match_val], "resultado": resultado})
            # Decide if this metric is present and matching
            present = data.draw(st.booleans())
            if present:
                metricas[metric_name] = _mv(match_val)

        label, trail, missing = melhor_posicao(regras, metricas, scale)

        # Compute expected: best satisfied label
        satisfied = []
        for rule in regras:
            m = rule["metrica"]
            if m in metricas and metricas[m].valor in rule["in"]:
                satisfied.append(rule["resultado"])

        if not satisfied:
            assert label is None
        else:
            expected_best = min(satisfied, key=lambda lbl: scale.index(lbl))
            assert label == expected_best

    @given(
        value=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_metrica_unica_finds_correct_range(self, value):
        """metrica_unica retorna rótulo cuja faixa contém o valor."""
        scale = ["A1", "A2", "A3", "A4"]
        regras = [
            {"min": 75, "max": 100.01, "resultado": "A1"},
            {"min": 50, "max": 75, "resultado": "A2"},
            {"min": 25, "max": 50, "resultado": "A3"},
            {"min": 0, "max": 25, "resultado": "A4"},
        ]
        metricas = {"x": _mv(value)}
        label, trail, missing = metrica_unica(regras, metricas, scale, "x")

        # Find expected range
        expected = None
        for rule in regras:
            in_range = True
            if "min" in rule and value < rule["min"]:
                in_range = False
            if "max" in rule and value >= rule["max"]:
                in_range = False
            if in_range:
                expected = rule["resultado"]
                break

        assert label == expected


    @given(data=st.data())
    @settings(max_examples=200)
    def test_primeira_regra_returns_first_match(self, data):
        """primeira_regra retorna o resultado da primeira regra satisfeita."""
        scale = ["A1", "A2", "A3", "A4"]
        n_rules = data.draw(st.integers(min_value=2, max_value=5))
        regras = []
        metricas = {}
        for i in range(n_rules):
            metric_name = f"m{i}"
            resultado = data.draw(st.sampled_from(scale))
            match_val = f"V{i}"
            regras.append({"metrica": metric_name, "in": [match_val], "resultado": resultado})
            present = data.draw(st.booleans())
            if present:
                metricas[metric_name] = _mv(match_val)

        label, trail, missing = primeira_regra(regras, metricas, scale)

        # Expected: first satisfied rule
        expected = None
        for rule in regras:
            m = rule["metrica"]
            if m in metricas and metricas[m].valor in rule["in"]:
                expected = rule["resultado"]
                break

        assert label == expected


# ---------------------------------------------------------------------------
# Property 7: Ajustes — limites de escala e tetos
# Feature: classificador-capes, Property 7: Ajustes respect scale bounds and tetos
# Validates: Requirements 2.6, 2.7
# ---------------------------------------------------------------------------


class TestProperty7AdjustmentBounds:
    """Ajustes nunca ultrapassam limites da escala nem tetos declarados."""

    @given(
        scale_idx=st.integers(min_value=0, max_value=4),
        shift=st.integers(min_value=-10, max_value=10),
    )
    @settings(max_examples=200)
    def test_efeito_respects_scale_bounds(self, scale_idx, shift):
        """Ajuste +N/-N nunca ultrapassa primeiro/último rótulo."""
        scale = ["A1", "A2", "A3", "A4", "A5"]
        base_label = scale[scale_idx]
        ajustes = [{"se": "cond", "efeito": f"{shift:+d}"}]
        metricas = {"cond": _mv(True)}

        result_label, trail = apply_adjustments(base_label, ajustes, scale, metricas, None)

        # Result must be within scale bounds
        assert result_label in scale
        result_idx = scale.index(result_label)
        assert 0 <= result_idx <= len(scale) - 1


    @given(
        scale_idx=st.integers(min_value=0, max_value=4),
        shift=st.integers(min_value=1, max_value=10),
        teto_idx=st.integers(min_value=0, max_value=4),
    )
    @settings(max_examples=200)
    def test_efeito_respects_teto(self, scale_idx, shift, teto_idx):
        """Ajuste com teto: resultado nunca é melhor que o teto."""
        scale = ["A1", "A2", "A3", "A4", "A5"]
        base_label = scale[scale_idx]
        teto_label = scale[teto_idx]
        ajustes = [{"se": "cond", "efeito": f"+{shift}", "teto": teto_label}]
        metricas = {"cond": _mv(True)}

        result_label, trail = apply_adjustments(base_label, ajustes, scale, metricas, None)

        result_idx = scale.index(result_label)
        # Result index must be >= teto_idx (teto is maximum improvement)
        assert result_idx >= teto_idx

    @given(
        scale_idx=st.integers(min_value=0, max_value=4),
        shift=st.integers(min_value=1, max_value=10),
        teto_q_idx=st.integers(min_value=0, max_value=4),
    )
    @settings(max_examples=200)
    def test_qualitativo_respects_teto_qualitativo(self, scale_idx, shift, teto_q_idx):
        """Ajuste qualitativo sinaliza mas não aplica; respeita teto_qualitativo na sinalização."""
        scale = ["A1", "A2", "A3", "A4", "A5"]
        base_label = scale[scale_idx]
        teto_q = scale[teto_q_idx]
        ajustes = [{"se": "cond", "efeito": f"+{shift}", "qualitativo": True}]
        metricas = {"cond": _mv(True)}

        result_label, trail = apply_adjustments(base_label, ajustes, scale, metricas, teto_q)

        # Qualitativo does NOT change the label
        assert result_label == base_label
        # Trail should have the signaled entry
        assert len(trail) == 1
        assert trail[0].etapa == "ajuste_sinalizado"
        # Signaled resultado respects teto_qualitativo
        signaled_idx = scale.index(trail[0].resultado)
        assert signaled_idx >= teto_q_idx


# ---------------------------------------------------------------------------
# Property 9: Trilha de decisão — completude
# Feature: classificador-capes, Property 9: Decision trail completeness
# Validates: Requirements 2.9, 16.4
# ---------------------------------------------------------------------------


class TestProperty9TrailCompleteness:
    """Trilha de decisão contém informações essenciais."""

    @given(
        percentil=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_trail_has_essential_entries(self, percentil):
        """Veredito sempre tem trilha com pelo menos uma entrada."""
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["A1", "A2", "A3", "A4"]},
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
                }
            },
        }
        metricas = {"percentil": _mv(percentil)}
        v = classify("journalArticle", metricas, area_rules)

        # Trail must not be empty
        assert len(v.trilha) > 0
        # Must have expressao_avaliada for metrica_unica mode
        etapas = [t.etapa for t in v.trilha]
        assert "expressao_avaliada" in etapas
        # If classified, must have regra_ativada; if not, must have fallback
        if v.estrato != "NAO_CLASSIFICAVEL":
            assert "regra_ativada" in etapas
        else:
            assert "fallback" in etapas


    @given(data=st.data())
    @settings(max_examples=200)
    def test_trail_contains_missing_metrics_when_conservative(self, data):
        """Quando ESTIMATIVA_CONSERVADORA, trilha menciona métricas ausentes."""
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["A1", "A2", "A3", "A4"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(wos, scopus)",
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
        # Provide only one of two operands
        val = data.draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False))
        which = data.draw(st.sampled_from(["wos", "scopus"]))
        metricas = {which: _mv(val)}

        v = classify("journalArticle", metricas, area_rules)

        if v.estrato != "NAO_CLASSIFICAVEL":
            assert v.estado == "ESTIMATIVA_CONSERVADORA"
            # Trail's expressao_avaliada should mention the missing metric
            expr_entry = next(t for t in v.trilha if t.etapa == "expressao_avaliada")
            assert expr_entry.nota is not None
            assert "ausentes" in expr_entry.nota


# ---------------------------------------------------------------------------
# Property 10: Fallback — nenhuma regra satisfeita
# Feature: classificador-capes, Property 10: Fallback when no rule satisfied
# Validates: Requirements 2.11, 2.13
# ---------------------------------------------------------------------------


class TestProperty10Fallback:
    """Quando nenhuma regra é satisfeita, retorna exatamente o fallback declarado."""

    @given(
        fallback_value=st.sampled_from(["NAO_CLASSIFICAVEL", "NAO_CONSIDERADO"]),
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_fallback_returned(self, fallback_value, data):
        """Se nenhuma regra satisfeita, retorna fallback; trilha registra."""
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["A1", "A2", "A3", "A4"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "percentil",
                    "regras": [
                        {"min": 50, "max": 100, "resultado": "A1"},
                    ],
                    "ajustes": [],
                    "fallback": fallback_value,
                }
            },
        }
        # Value that does NOT satisfy any rule
        value = data.draw(st.floats(min_value=-100, max_value=49.99, allow_nan=False, allow_infinity=False))
        metricas = {"percentil": _mv(value)}
        v = classify("journalArticle", metricas, area_rules)

        assert v.estrato == fallback_value
        # Trail must have a fallback entry
        etapas = [t.etapa for t in v.trilha]
        assert "fallback" in etapas
        fallback_entry = next(t for t in v.trilha if t.etapa == "fallback")
        assert fallback_entry.resultado == fallback_value

    @given(
        metric_name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=2, max_size=10),
    )
    @settings(max_examples=200)
    def test_absent_metric_triggers_fallback(self, metric_name):
        """Métrica ausente para metrica_unica → fallback."""
        assume(metric_name not in ("", " "))
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["A1", "A2"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": metric_name,
                    "regras": [{"min": 0, "resultado": "A1"}],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        # Empty metrics dict → metric absent
        v = classify("journalArticle", {}, area_rules)
        assert v.estrato == "NAO_CLASSIFICAVEL"


# ---------------------------------------------------------------------------
# Property 15: Degradação conservadora — rotulagem correta
# Feature: classificador-capes, Property 15: Conservative degradation labeling
# Validates: Requirements 16.1, 16.2
# ---------------------------------------------------------------------------


class TestProperty15ConservativeDegradation:
    """Operandos parciais → ESTIMATIVA_CONSERVADORA; nenhum → NAO_CLASSIFICAVEL."""

    @given(
        available_val=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_partial_operands_labels_conservative(self, available_val):
        """max(a,b) com apenas um operando → ESTIMATIVA_CONSERVADORA (se classificável)."""
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["A1", "A2", "A3", "A4"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(a, b)",
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
        # Only one of two operands available
        metricas = {"a": _mv(available_val)}
        v = classify("journalArticle", metricas, area_rules)

        if v.estrato != "NAO_CLASSIFICAVEL":
            assert v.estado == "ESTIMATIVA_CONSERVADORA"

    @settings(max_examples=200)
    @given(st.just(None))
    def test_no_operands_labels_nao_classificavel(self, _):
        """max(a,b) com nenhum operando → NAO_CLASSIFICAVEL."""
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": ["A1", "A2"]},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(a, b)",
                    "regras": [{"min": 0, "resultado": "A1"}],
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        v = classify("journalArticle", {}, area_rules)
        assert v.estrato == "NAO_CLASSIFICAVEL"
        assert v.estado == "NAO_CLASSIFICAVEL"


    @given(data=st.data())
    @settings(max_examples=200)
    def test_melhor_posicao_partial_is_conservative(self, data):
        """melhor_posicao com algumas métricas ausentes → ESTIMATIVA_CONSERVADORA."""
        scale = ["A1", "A2", "A3", "A4"]
        # Build rules referencing metrics; provide only some
        regras = [
            {"metrica": "m_present", "in": ["val"], "resultado": "A2"},
            {"metrica": "m_absent", "in": ["val"], "resultado": "A1"},
        ]
        metricas = {"m_present": _mv("val")}  # m_absent is missing

        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": scale},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "melhor_posicao",
                    "regras": regras,
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }
        v = classify("journalArticle", metricas, area_rules)
        # Has result A2 but m_absent is missing → conservative
        assert v.estado == "ESTIMATIVA_CONSERVADORA"


# ---------------------------------------------------------------------------
# Property 16: Monotonicidade — operandos parciais nunca superestimam
# Feature: classificador-capes, Property 16: Monotonicity (partial never overestimate)
# Validates: Requirements 16.5
# ---------------------------------------------------------------------------


class TestProperty16Monotonicity:
    """Adição de operando ausente pode apenas manter ou elevar o estrato, nunca reduzir."""

    @given(
        val_a=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        val_b=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_superset_never_worse_metrica_unica(self, val_a, val_b):
        """max(a,b) com ambos presentes >= max(a,b) com apenas um (monotônico)."""
        scale = ["A1", "A2", "A3", "A4"]
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": scale},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "max(a, b)",
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

        # Partial: only 'a'
        metricas_partial = {"a": _mv(val_a)}
        v_partial = classify("journalArticle", metricas_partial, area_rules)

        # Full: both 'a' and 'b'
        metricas_full = {"a": _mv(val_a), "b": _mv(val_b)}
        v_full = classify("journalArticle", metricas_full, area_rules)

        # Compare positions: lower index = better
        if v_partial.estrato == "NAO_CLASSIFICAVEL":
            # If partial couldn't classify, full should classify or also fail
            pass  # No constraint violated
        elif v_full.estrato == "NAO_CLASSIFICAVEL":
            # Full should never be worse; NAO_CLASSIFICAVEL shouldn't happen if partial succeeded
            # This would mean adding data made things worse - shouldn't happen with max
            assert False, "Full superset produced NAO_CLASSIFICAVEL when partial classified"
        else:
            partial_idx = scale.index(v_partial.estrato)
            full_idx = scale.index(v_full.estrato)
            # Full result should be same or better (lower or equal index)
            assert full_idx <= partial_idx, (
                f"Monotonicity violated: partial={v_partial.estrato} (idx={partial_idx}), "
                f"full={v_full.estrato} (idx={full_idx})"
            )


    @given(data=st.data())
    @settings(max_examples=200)
    def test_superset_never_worse_melhor_posicao(self, data):
        """melhor_posicao: mais métricas presentes pode apenas manter ou elevar."""
        scale = ["MB", "B", "R", "F"]
        regras = [
            {"metrica": "m1", "in": ["hit"], "resultado": "MB"},
            {"metrica": "m2", "in": ["hit"], "resultado": "B"},
            {"metrica": "m3", "in": ["hit"], "resultado": "R"},
        ]
        area_rules = {
            "area": 99,
            "nome": "Teste",
            "data_extracao": "2026-01-01",
            "escala": {"rotulos": scale},
            "veiculos": {
                "journalArticle": {
                    "combinacao": "melhor_posicao",
                    "regras": regras,
                    "ajustes": [],
                    "fallback": "NAO_CLASSIFICAVEL",
                }
            },
        }

        # Partial: subset of metrics
        partial_set = data.draw(
            st.lists(st.sampled_from(["m1", "m2", "m3"]), min_size=1, max_size=2, unique=True)
        )
        extra = data.draw(
            st.lists(st.sampled_from(["m1", "m2", "m3"]), min_size=0, max_size=3, unique=True)
        )
        full_set = list(set(partial_set) | set(extra))

        metricas_partial = {m: _mv("hit") for m in partial_set}
        metricas_full = {m: _mv("hit") for m in full_set}

        v_partial = classify("journalArticle", metricas_partial, area_rules)
        v_full = classify("journalArticle", metricas_full, area_rules)

        if v_partial.estrato == "NAO_CLASSIFICAVEL":
            pass
        elif v_full.estrato == "NAO_CLASSIFICAVEL":
            assert False, "Superset should not fail when partial succeeded"
        else:
            partial_idx = scale.index(v_partial.estrato)
            full_idx = scale.index(v_full.estrato)
            assert full_idx <= partial_idx
