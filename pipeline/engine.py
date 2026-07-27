"""Motor de regras declarativo para classificação CAPES.

Implementa:
- evaluate_rule: avaliação de regras individuais (in, min/max, requer)
- evaluate_expression: parse e avaliação de max(...)/min(...)
- melhor_posicao, metrica_unica, primeira_regra: modos de combinação
- apply_adjustments: ajustes pós-classificação (efeito, resultado, teto, qualitativo)
- classify: orquestração completa com trilha de decisão
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.vehicles import MetricValue


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TrailEntry:
    """Uma entrada na trilha de decisão."""

    etapa: str  # "regra_avaliada" | "regra_ativada" | "ajuste_sinalizado" | "ajuste_aplicado" | "fallback" | "expressao_avaliada"
    metrica: str | None = None
    valor: str | int | float | None = None
    regra_idx: int | None = None
    resultado: str | None = None
    fonte_id: str | None = None
    data_fonte: str | None = None
    nota: str | None = None


@dataclass
class Verdict:
    """Resultado completo de uma classificação."""

    estrato: str  # Rótulo final (ex: "A1", "MB", "NAO_CLASSIFICAVEL")
    estado: str  # "COMPLETO" | "ESTIMATIVA_CONSERVADORA" | "NAO_CLASSIFICAVEL" | "NAO_CONSIDERADO"
    trilha: list[TrailEntry]
    area: int
    data_snapshot: str


# ---------------------------------------------------------------------------
# evaluate_rule
# ---------------------------------------------------------------------------


def evaluate_rule(rule: dict, metricas: dict[str, MetricValue]) -> bool:
    """Avalia uma regra individual contra métricas disponíveis.

    Campo "in": pertencimento a conjunto (case-sensitive, tipo-exata)
    Campo "min"/"max": min inclusivo, max exclusivo
    Campo "requer": conjunção lógica de condições booleanas

    Se a métrica requerida não está disponível → regra não satisfeita (False).
    Uma regra sem campo "metrica" (ex: regras de book/bookSection que apenas
    possuem "resultado") é sempre satisfeita (sujeita a requer).
    """
    # 1. Se a regra não tem campo "metrica", apenas checar requer
    if "metrica" not in rule:
        return _check_requer(rule, metricas)

    # 2. Buscar a métrica no dicionário
    nome_metrica = rule["metrica"]
    if nome_metrica not in metricas:
        return False

    valor = metricas[nome_metrica].valor

    # 3. Campo "in": pertencimento a conjunto (case-sensitive, tipo-exata)
    if "in" in rule:
        if valor not in rule["in"]:
            return False

    # 4. Campos "min" e/ou "max": faixas numéricas
    if "min" in rule:
        if valor < rule["min"]:
            return False

    if "max" in rule:
        if valor >= rule["max"]:
            return False

    # 5. Campo "requer": conjunção lógica
    return _check_requer(rule, metricas)


def _check_requer(rule: dict, metricas: dict[str, MetricValue]) -> bool:
    """Verifica campo 'requer': cada string é um nome de métrica que deve
    existir em metricas e ter valor truthy.
    """
    if "requer" not in rule:
        return True

    for cond in rule["requer"]:
        if cond not in metricas:
            return False
        if not metricas[cond].valor:
            return False

    return True


# ---------------------------------------------------------------------------
# evaluate_expression
# ---------------------------------------------------------------------------

_EXPR_PATTERN = re.compile(r"^(max|min)\((.+)\)$")


def evaluate_expression(
    expr: str, metricas: dict[str, MetricValue]
) -> tuple[float | None, list[str]]:
    """Avalia expressão max(...) ou min(...).

    Retorna:
      - valor: resultado numérico ou None se nenhum operando disponível
      - ausentes: lista de nomes de métricas que não estavam disponíveis

    Regras:
      - Ignora operandos cujo valor não está em `metricas`
      - Se pelo menos 1 operando disponível: retorna max/min dos disponíveis
      - Se nenhum operando disponível: retorna None

    Se a expressão não é max/min (métrica simples), retorna o valor da métrica
    ou None se ausente.
    """
    match = _EXPR_PATTERN.match(expr.strip())

    if not match:
        # Expressão simples: nome de métrica único
        if expr.strip() in metricas:
            val = metricas[expr.strip()].valor
            return (float(val), [])
        return (None, [expr.strip()])

    func_name = match.group(1)  # "max" ou "min"
    operands_str = match.group(2)
    operand_names = [op.strip() for op in operands_str.split(",")]

    available_values: list[float] = []
    missing: list[str] = []

    for name in operand_names:
        if name in metricas:
            available_values.append(float(metricas[name].valor))
        else:
            missing.append(name)

    if not available_values:
        return (None, missing)

    if func_name == "max":
        return (max(available_values), missing)
    else:  # min
        return (min(available_values), missing)


# ---------------------------------------------------------------------------
# Modos de combinação
# ---------------------------------------------------------------------------


def melhor_posicao(
    regras: list[dict],
    metricas: dict[str, MetricValue],
    scale: list[str],
) -> tuple[str | None, list[TrailEntry], list[str]]:
    """Modo melhor_posicao: avalia TODAS as regras, retorna melhor resultado.

    Retorna:
      - label: melhor rótulo encontrado (ou None se nenhuma regra satisfeita)
      - trail: lista de TrailEntries
      - missing: lista de métricas ausentes que impediram avaliação
    """
    trail: list[TrailEntry] = []
    satisfied_labels: list[str] = []
    all_missing: list[str] = []

    for idx, rule in enumerate(regras):
        metrica_name = rule.get("metrica")
        satisfied = evaluate_rule(rule, metricas)

        if satisfied:
            label = rule["resultado"]
            satisfied_labels.append(label)

            # Obter valor e fonte
            valor = None
            fonte_id = None
            data_fonte = None
            if metrica_name and metrica_name in metricas:
                mv = metricas[metrica_name]
                valor = mv.valor
                fonte_id = mv.fonte_id
                data_fonte = mv.data_fonte

            trail.append(
                TrailEntry(
                    etapa="regra_ativada",
                    metrica=metrica_name,
                    valor=valor,
                    regra_idx=idx,
                    resultado=label,
                    fonte_id=fonte_id,
                    data_fonte=data_fonte,
                )
            )
        else:
            # Regra não satisfeita
            nota = None
            if metrica_name and metrica_name not in metricas:
                nota = f"metrica '{metrica_name}' ausente"
                all_missing.append(metrica_name)

            trail.append(
                TrailEntry(
                    etapa="regra_avaliada",
                    metrica=metrica_name,
                    regra_idx=idx,
                    resultado=None,
                    nota=nota,
                )
            )

    if not satisfied_labels:
        return (None, trail, all_missing)

    # Melhor posição = menor índice na escala (escala é do melhor ao pior)
    best_label = min(satisfied_labels, key=lambda lbl: scale.index(lbl))
    return (best_label, trail, all_missing)


def metrica_unica(
    regras: list[dict],
    metricas: dict[str, MetricValue],
    scale: list[str],
    metrica_expr: str,
) -> tuple[str | None, list[TrailEntry], list[str]]:
    """Modo metrica_unica: resolve expressão, encontra faixa correspondente.

    Retorna:
      - label: rótulo encontrado (ou None se expressão não avaliável ou
               nenhuma faixa corresponde)
      - trail: lista de TrailEntries
      - missing: lista de métricas ausentes
    """
    trail: list[TrailEntry] = []

    # Avaliar expressão
    value, missing = evaluate_expression(metrica_expr, metricas)

    trail.append(
        TrailEntry(
            etapa="expressao_avaliada",
            metrica=metrica_expr,
            valor=value,
            nota=f"ausentes: {missing}" if missing else None,
        )
    )

    if value is None:
        return (None, trail, missing)

    # Encontrar qual regra/faixa corresponde ao valor
    for idx, rule in enumerate(regras):
        # Para metrica_unica as regras são faixas numéricas (min/max)
        satisfied = True

        if "min" in rule:
            if value < rule["min"]:
                satisfied = False

        if "max" in rule:
            if value >= rule["max"]:
                satisfied = False

        if satisfied:
            label = rule["resultado"]
            trail.append(
                TrailEntry(
                    etapa="regra_ativada",
                    metrica=metrica_expr,
                    valor=value,
                    regra_idx=idx,
                    resultado=label,
                )
            )
            return (label, trail, missing)

    # Nenhuma faixa corresponde
    return (None, trail, missing)


def primeira_regra(
    regras: list[dict],
    metricas: dict[str, MetricValue],
    scale: list[str],
) -> tuple[str | None, list[TrailEntry], list[str]]:
    """Modo primeira_regra: avalia regras em ordem, retorna primeiro match.

    Retorna:
      - label: resultado da primeira regra satisfeita (ou None)
      - trail: lista de TrailEntries
      - missing: lista de métricas ausentes
    """
    trail: list[TrailEntry] = []
    all_missing: list[str] = []

    for idx, rule in enumerate(regras):
        metrica_name = rule.get("metrica")
        satisfied = evaluate_rule(rule, metricas)

        if satisfied:
            # Obter valor e fonte
            valor = None
            fonte_id = None
            data_fonte = None
            if metrica_name and metrica_name in metricas:
                mv = metricas[metrica_name]
                valor = mv.valor
                fonte_id = mv.fonte_id
                data_fonte = mv.data_fonte

            label = rule["resultado"]
            trail.append(
                TrailEntry(
                    etapa="regra_ativada",
                    metrica=metrica_name,
                    valor=valor,
                    regra_idx=idx,
                    resultado=label,
                    fonte_id=fonte_id,
                    data_fonte=data_fonte,
                )
            )
            return (label, trail, all_missing)
        else:
            nota = None
            if metrica_name and metrica_name not in metricas:
                nota = f"metrica '{metrica_name}' ausente"
                all_missing.append(metrica_name)

            trail.append(
                TrailEntry(
                    etapa="regra_avaliada",
                    metrica=metrica_name,
                    regra_idx=idx,
                    resultado=None,
                    nota=nota,
                )
            )

    return (None, trail, all_missing)


# ---------------------------------------------------------------------------
# apply_adjustments
# ---------------------------------------------------------------------------


def apply_adjustments(
    base_label: str,
    adjustments: list[dict],
    scale: list[str],
    metricas: dict[str, MetricValue],
    teto_qualitativo: str | None,
) -> tuple[str, list[TrailEntry]]:
    """Aplica ajustes na ordem declarada.

    Tipos de ajuste:
    - "efeito": "+N" ou "-N" → desloca N posições na escala
    - "resultado": atribuição direta de rótulo
    - "teto": limite máximo do ajuste específico

    Se qualitativo=True:
      - NÃO aplica o ajuste
      - Registra sinalização na trilha
      - Respeita teto_qualitativo do bloco

    Limites:
      - Nunca ultrapassa primeiro rótulo (melhor) nem último (pior)
      - Nunca ultrapassa teto do ajuste
      - Ajustes qualitativos respeitam teto_qualitativo

    Retorna:
      - label: rótulo final após ajustes
      - trail: lista de TrailEntries para os ajustes
    """
    current_label = base_label
    trail: list[TrailEntry] = []

    for adj in adjustments:
        condition = adj["se"]
        is_qualitative = adj.get("qualitativo", False)

        # Verificar condição: o campo "se" pode conter operadores lógicos
        # simples (&&) ou ser um nome de métrica simples.
        condition_met = _evaluate_condition(condition, metricas)

        if not condition_met:
            continue

        if is_qualitative:
            # Sinalizar sem aplicar
            trail.append(
                TrailEntry(
                    etapa="ajuste_sinalizado",
                    metrica=condition,
                    resultado=_compute_adjustment_target(
                        current_label, adj, scale, teto_qualitativo
                    ),
                    nota=adj.get("nota", f"qualitativo: elegivel, teto_qualitativo={teto_qualitativo}"),
                )
            )
        else:
            # Aplicar ajuste
            new_label = _apply_single_adjustment(current_label, adj, scale, teto_qualitativo=None)
            trail.append(
                TrailEntry(
                    etapa="ajuste_aplicado",
                    metrica=condition,
                    valor=adj.get("efeito") or adj.get("resultado"),
                    resultado=new_label,
                    nota=adj.get("nota"),
                )
            )
            current_label = new_label

    return (current_label, trail)


def _evaluate_condition(condition: str, metricas: dict[str, MetricValue]) -> bool:
    """Avalia condição de ajuste.

    Suporta:
    - Nome simples de métrica: verdadeiro se existe e tem valor truthy
    - Conjunção com "&&": todas as partes devem ser verdadeiras
    """
    parts = [p.strip() for p in condition.split("&&")]

    for part in parts:
        if part not in metricas:
            return False
        if not metricas[part].valor:
            return False

    return True


def _compute_adjustment_target(
    current_label: str,
    adj: dict,
    scale: list[str],
    teto_qualitativo: str | None,
) -> str:
    """Calcula o alvo teórico de um ajuste (para sinalização)."""
    target = _apply_single_adjustment(current_label, adj, scale, teto_qualitativo)
    return target


def _apply_single_adjustment(
    current_label: str,
    adj: dict,
    scale: list[str],
    teto_qualitativo: str | None,
) -> str:
    """Aplica um único ajuste e retorna o novo rótulo."""
    current_idx = scale.index(current_label)

    if "resultado" in adj:
        # Atribuição direta
        new_label = adj["resultado"]
        new_idx = scale.index(new_label) if new_label in scale else current_idx
    elif "efeito" in adj:
        # Deslocamento: "+N" melhora (menor índice), "-N" piora (maior índice)
        shift = int(adj["efeito"])
        new_idx = current_idx - shift  # + melhora = menor índice
        # Clamp aos limites da escala
        new_idx = max(0, min(len(scale) - 1, new_idx))
        new_label = scale[new_idx]
    else:
        return current_label

    # Aplicar teto do ajuste (nunca melhor que teto)
    if "teto" in adj:
        teto_idx = scale.index(adj["teto"])
        adj_idx = scale.index(new_label) if new_label in scale else current_idx
        if adj_idx < teto_idx:
            new_label = adj["teto"]

    # Aplicar teto_qualitativo (para sinalizações)
    if teto_qualitativo is not None and new_label in scale:
        teto_q_idx = scale.index(teto_qualitativo)
        new_label_idx = scale.index(new_label)
        if new_label_idx < teto_q_idx:
            new_label = teto_qualitativo

    return new_label


# ---------------------------------------------------------------------------
# classify (orquestração principal)
# ---------------------------------------------------------------------------


def classify(
    item_type: str,
    metricas: dict[str, MetricValue],
    area_rules: dict,
) -> Verdict:
    """Classifica um item usando as regras da área.

    Algoritmo:
    1. Selecionar bloco de veículo por item_type
    2. Avaliar conforme modo de combinação
    3. Aplicar ajustes pós-classificação
    4. Rotular estado (COMPLETO / ESTIMATIVA_CONSERVADORA / NAO_CLASSIFICAVEL)
    5. Retornar Verdict com trilha completa
    """
    trail: list[TrailEntry] = []
    scale = area_rules["escala"]["rotulos"]
    area_code = area_rules["area"]
    data_snapshot = area_rules.get("data_extracao", "")

    # 1. Selecionar bloco de veículo
    veiculos = area_rules.get("veiculos", {})
    if item_type not in veiculos:
        trail.append(
            TrailEntry(
                etapa="fallback",
                nota=f"tipo '{item_type}' nao definido em veiculos",
                resultado="NAO_CLASSIFICAVEL",
            )
        )
        return Verdict(
            estrato="NAO_CLASSIFICAVEL",
            estado="NAO_CLASSIFICAVEL",
            trilha=trail,
            area=area_code,
            data_snapshot=data_snapshot,
        )

    bloco = veiculos[item_type]
    combinacao = bloco["combinacao"]
    regras = bloco["regras"]
    fallback = bloco.get("fallback", "NAO_CLASSIFICAVEL")
    adjustments = bloco.get("ajustes", [])
    teto_qualitativo = bloco.get("teto_qualitativo")

    # 2. Avaliar conforme modo de combinação
    if combinacao == "melhor_posicao":
        base_label, mode_trail, missing = melhor_posicao(regras, metricas, scale)
    elif combinacao == "metrica_unica":
        metrica_expr = bloco["metrica"]
        base_label, mode_trail, missing = metrica_unica(
            regras, metricas, scale, metrica_expr
        )
    elif combinacao == "primeira_regra":
        base_label, mode_trail, missing = primeira_regra(regras, metricas, scale)
    else:
        raise ValueError(f"Modo de combinação desconhecido: {combinacao}")

    trail.extend(mode_trail)

    # 3. Se nenhuma regra satisfeita → fallback
    if base_label is None:
        trail.append(
            TrailEntry(
                etapa="fallback",
                resultado=fallback,
                nota="nenhuma regra satisfeita",
            )
        )

        # Determinar estado do fallback
        if fallback == "NAO_CONSIDERADO":
            estado = "NAO_CONSIDERADO"
        else:
            estado = "NAO_CLASSIFICAVEL"

        return Verdict(
            estrato=fallback,
            estado=estado,
            trilha=trail,
            area=area_code,
            data_snapshot=data_snapshot,
        )

    # 4. Aplicar ajustes pós-classificação
    final_label, adj_trail = apply_adjustments(
        base_label, adjustments, scale, metricas, teto_qualitativo
    )
    trail.extend(adj_trail)

    # 5. Determinar estado
    # Se há métricas ausentes que poderiam participar → ESTIMATIVA_CONSERVADORA
    # Se todos os operandos estão presentes → COMPLETO
    if missing:
        estado = "ESTIMATIVA_CONSERVADORA"
    else:
        estado = "COMPLETO"

    return Verdict(
        estrato=final_label,
        estado=estado,
        trilha=trail,
        area=area_code,
        data_snapshot=data_snapshot,
    )
