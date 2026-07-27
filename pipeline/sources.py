"""Resolução de métricas via sources.yml (Camada 1).

Implementa:
- load_sources: carrega sources.yml e retorna mapa de provides
- extract_metrics_from_area: extrai todas as métricas referenciadas em um JSON de área
- validate_metrics_resolvable: verifica que toda métrica tem pelo menos uma fonte
- find_orphan_metrics: retorna lista de métricas órfãs (sem fonte)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

# Padrão para expressões max(...) / min(...)
_EXPR_PATTERN = re.compile(r"^(?:max|min)\((.+)\)$")


def load_sources(sources_path: Path) -> dict[str, list[str]]:
    """Carrega sources.yml e retorna mapa {source_id: [métricas fornecidas]}.

    Args:
        sources_path: Caminho para sources.yml.

    Returns:
        Dicionário onde cada chave é o id da fonte e o valor é a lista
        de nomes canônicos de métricas declarados em `provides`.

    Raises:
        FileNotFoundError: Se o arquivo não existe.
        ValueError: Se o YAML não possui estrutura válida (campo 'fontes' ausente
                    ou entrada sem 'id'/'provides').
    """
    if not sources_path.exists():
        raise FileNotFoundError(f"sources.yml não encontrado: {sources_path}")

    with open(sources_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "fontes" not in data:
        raise ValueError(
            f"sources.yml inválido: campo 'fontes' ausente em {sources_path}"
        )

    result: dict[str, list[str]] = {}

    for entry in data["fontes"]:
        if "id" not in entry:
            raise ValueError(
                f"Entrada em sources.yml sem campo 'id': {entry}"
            )
        if "provides" not in entry:
            raise ValueError(
                f"Fonte '{entry['id']}' em sources.yml sem campo 'provides'"
            )
        result[entry["id"]] = list(entry["provides"])

    return result


def get_all_provided_metrics(sources: dict[str, list[str]]) -> set[str]:
    """Retorna o conjunto de todas as métricas fornecidas por pelo menos uma fonte.

    Args:
        sources: Mapa retornado por load_sources().

    Returns:
        Conjunto de nomes canônicos de métricas.
    """
    metrics: set[str] = set()
    for provides in sources.values():
        metrics.update(provides)
    return metrics


def extract_metrics_from_area(area_rules: dict) -> set[str]:
    """Extrai todos os nomes de métricas referenciados nas regras de uma área.

    Busca em:
    - campo 'metrica' do bloco de veículo (expressões max/min ou métrica simples)
    - campo 'metrica' de cada regra individual
    - campo 'requer' de cada regra individual
    - campo 'se' de cada ajuste (pode conter '&&' para conjunção)

    Args:
        area_rules: Dicionário carregado de um arquivo areas/*.json.

    Returns:
        Conjunto de nomes canônicos de métricas referenciados.
    """
    metrics: set[str] = set()

    veiculos = area_rules.get("veiculos", {})

    for _tipo, bloco in veiculos.items():
        # Expressão de métrica do bloco (metrica_unica)
        if "metrica" in bloco:
            _extract_from_expression(bloco["metrica"], metrics)

        # Regras individuais
        for regra in bloco.get("regras", []):
            if "metrica" in regra:
                _extract_from_expression(regra["metrica"], metrics)
            for req in regra.get("requer", []):
                metrics.add(req)

        # Ajustes
        for ajuste in bloco.get("ajustes", []):
            if "se" in ajuste:
                _extract_from_condition(ajuste["se"], metrics)

    return metrics


def _extract_from_expression(expr: str, metrics: set[str]) -> None:
    """Extrai nomes de métricas de uma expressão (max/min ou simples)."""
    match = _EXPR_PATTERN.match(expr.strip())
    if match:
        # Expressão composta: max(a, b) ou min(a, b)
        operands = [op.strip() for op in match.group(1).split(",")]
        metrics.update(operands)
    else:
        # Métrica simples
        metrics.add(expr.strip())


# Padrão para detectar operadores de comparação em condições
_COMPARISON_PATTERN = re.compile(r"^(\w+)\s*(?:>=|<=|>|<|==|!=)\s*.+$")


def _extract_from_condition(condition: str, metrics: set[str]) -> None:
    """Extrai nomes de métricas de uma condição de ajuste (suporta '&&').

    Lida com:
    - Nomes simples: "periodico_sbc"
    - Conjunções: "sem_h5 && ce_sbc_top"
    - Comparações: "anos_tradicao >= 20" → extrai "anos_tradicao"
    """
    parts = [p.strip() for p in condition.split("&&")]
    for part in parts:
        match = _COMPARISON_PATTERN.match(part)
        if match:
            # Expressão de comparação: extrair apenas o nome da métrica
            metrics.add(match.group(1))
        else:
            metrics.add(part)


def find_orphan_metrics(
    area_rules: dict,
    sources: dict[str, list[str]],
) -> list[str]:
    """Encontra métricas referenciadas na área que não possuem nenhuma fonte.

    Args:
        area_rules: Dicionário carregado de um arquivo areas/*.json.
        sources: Mapa retornado por load_sources().

    Returns:
        Lista ordenada de nomes de métricas órfãs (sem fonte em provides).
        Lista vazia se todas as métricas são resolvíveis.
    """
    referenced = extract_metrics_from_area(area_rules)
    provided = get_all_provided_metrics(sources)
    orphans = referenced - provided
    return sorted(orphans)


def validate_all_areas(
    areas_dir: Path,
    sources_path: Path,
) -> dict[str, list[str]]:
    """Valida que todas as métricas em todos os JSONs de área são resolvíveis.

    Args:
        areas_dir: Diretório contendo arquivos areas/*.json.
        sources_path: Caminho para sources.yml.

    Returns:
        Dicionário {nome_arquivo: [métricas_órfãs]}.
        Vazio se todas as métricas são resolvíveis em todas as áreas.

    Raises:
        FileNotFoundError: Se sources.yml ou diretório de áreas não existe.
        ValueError: Se sources.yml é inválido.
    """
    sources = load_sources(sources_path)
    result: dict[str, list[str]] = {}

    if not areas_dir.exists():
        raise FileNotFoundError(f"Diretório de áreas não encontrado: {areas_dir}")

    for area_file in sorted(areas_dir.glob("*.json")):
        with open(area_file, encoding="utf-8") as f:
            area_rules = json.load(f)

        orphans = find_orphan_metrics(area_rules, sources)
        if orphans:
            result[area_file.name] = orphans

    return result
