#!/usr/bin/env python3
"""
check-restricted-sources.py — Enforcement de fronteira de redistribuição.

Valida que:
1. Fontes com `licenca: restrita` em sources.yml não têm dados rastreados no git.
2. Toda métrica referenciada em areas/*.json é resolvível via sources.yml.

Usado como pre-commit hook e no CI. Falha com mensagem indicando:
- O arquivo violador e a fonte restrita correspondente.
- Métricas órfãs e a área de origem.

Requirements: 13.4, 13.7

Uso:
    python scripts/check-restricted-sources.py [--ci]

Flags:
    --ci  Verificar todos os arquivos rastreados (modo CI).
          Sem --ci, verifica apenas arquivos staged (modo pre-commit).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit(
        "Erro: pyyaml não está instalado.\n"
        "Instale com: pip install pyyaml"
    )

# Raiz do repositório (onde sources.yml vive)
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_YML = REPO_ROOT / "sources.yml"
AREAS_DIR = REPO_ROOT / "areas"

# Padrões de caminhos que indicam dados de fontes restritas
RESTRICTED_DATA_PATTERNS = [
    r"^data/restricted/",
]

# Expressões max(...)/min(...) para extrair operandos
_EXPR_PATTERN = re.compile(r"^(?:max|min)\((.+)\)$")

# Padrão para comparações em condições de ajuste (ex: "anos_tradicao >= 20")
_COMPARISON_PATTERN = re.compile(r"^(\w+)\s*(?:>=|<=|>|<|==|!=)\s*.+$")


def load_restricted_sources() -> dict[str, list[str]]:
    """Carrega sources.yml e retorna {source_id: provides} para fontes restritas.

    Returns:
        Mapa de ID da fonte restrita para lista de métricas que fornece.
    """
    if not SOURCES_YML.exists():
        print(f"⚠ sources.yml não encontrado em {SOURCES_YML}", file=sys.stderr)
        return {}

    with open(SOURCES_YML, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "fontes" not in data:
        print("⚠ sources.yml inválido: campo 'fontes' ausente", file=sys.stderr)
        return {}

    restricted: dict[str, list[str]] = {}
    for entry in data["fontes"]:
        if entry.get("licenca") == "restrita":
            restricted[entry["id"]] = list(entry.get("provides", []))

    return restricted


def load_all_sources() -> dict[str, list[str]]:
    """Carrega sources.yml e retorna {source_id: provides} para todas as fontes."""
    if not SOURCES_YML.exists():
        return {}

    with open(SOURCES_YML, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "fontes" not in data:
        return {}

    result: dict[str, list[str]] = {}
    for entry in data["fontes"]:
        if "id" in entry and "provides" in entry:
            result[entry["id"]] = list(entry["provides"])

    return result


def get_all_provided_metrics(sources: dict[str, list[str]]) -> set[str]:
    """Retorna o conjunto de todas as métricas fornecidas por pelo menos uma fonte."""
    metrics: set[str] = set()
    for provides in sources.values():
        metrics.update(provides)
    return metrics


def get_tracked_files(ci_mode: bool) -> list[str]:
    """Retorna lista de arquivos a verificar.

    Args:
        ci_mode: Se True, verifica todos os rastreados. Se False, apenas staged.
    """
    try:
        if ci_mode:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                check=True,
            )
        else:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                check=True,
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: verificar todos os arquivos rastreados
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_restricted_files(
    files: list[str],
    restricted_sources: dict[str, list[str]],
) -> list[str]:
    """Verifica se algum arquivo rastreado pertence a uma fonte restrita.

    Padrões verificados:
    - data/restricted/*  (diretório genérico de dados restritos)
    - docs/fontes/ com arquivos que contêm IDs de fontes restritas no nome

    Returns:
        Lista de mensagens de erro (vazia = OK).
    """
    errors: list[str] = []
    restricted_ids = set(restricted_sources.keys())

    for filepath in files:
        # Verificar padrão data/restricted/
        for pattern in RESTRICTED_DATA_PATTERNS:
            if re.match(pattern, filepath):
                # Tentar identificar qual fonte restrita
                source_match = _identify_restricted_source(filepath, restricted_ids)
                if source_match:
                    errors.append(
                        f"VIOLAÇÃO: Arquivo '{filepath}' pertence à fonte restrita "
                        f"'{source_match}' (licenca: restrita em sources.yml). "
                        f"Dados de fontes restritas não podem ser rastreados pelo git."
                    )
                else:
                    errors.append(
                        f"VIOLAÇÃO: Arquivo '{filepath}' está em data/restricted/ "
                        f"e não pode ser rastreado pelo git. "
                        f"Fontes restritas: {', '.join(sorted(restricted_ids))}."
                    )

        # Verificar arquivos em docs/fontes/ que correspondem a fontes restritas
        # (exceto _schema.md que é documentação permitida)
        if filepath.startswith("docs/fontes/") and not filepath.endswith("_schema.md"):
            basename = Path(filepath).stem.lower()
            for source_id in restricted_ids:
                # Verificar se o nome do arquivo contém o ID da fonte restrita
                # Ex: "ABDC-JQL-2025-v1.xlsx" contém "abdc"
                if source_id.lower() in basename:
                    # Verificar se não é um sample CSV (gitignored por padrão)
                    if filepath.endswith("_sample.csv"):
                        continue
                    errors.append(
                        f"VIOLAÇÃO: Arquivo '{filepath}' parece conter dados da "
                        f"fonte restrita '{source_id}' (licenca: restrita em sources.yml). "
                        f"Dados de fontes restritas não podem ser rastreados pelo git. "
                        f"Use config/local.yml para referenciar o arquivo localmente."
                    )

    return errors


def _identify_restricted_source(filepath: str, restricted_ids: set[str]) -> str | None:
    """Tenta identificar qual fonte restrita um arquivo pertence pelo nome."""
    lower = filepath.lower()
    for source_id in restricted_ids:
        if source_id.lower() in lower:
            return source_id
    return None


def extract_metrics_from_area(area_rules: dict) -> set[str]:
    """Extrai todos os nomes de métricas referenciados nas regras de uma área."""
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
        operands = [op.strip() for op in match.group(1).split(",")]
        metrics.update(operands)
    else:
        metrics.add(expr.strip())


def _extract_from_condition(condition: str, metrics: set[str]) -> None:
    """Extrai nomes de métricas de uma condição de ajuste (suporta '&&')."""
    parts = [p.strip() for p in condition.split("&&")]
    for part in parts:
        match = _COMPARISON_PATTERN.match(part)
        if match:
            metrics.add(match.group(1))
        else:
            metrics.add(part)


def check_metric_resolution() -> list[str]:
    """Valida que toda métrica em areas/*.json é resolvível via sources.yml.

    Returns:
        Lista de mensagens de erro (vazia = OK).
    """
    errors: list[str] = []

    all_sources = load_all_sources()
    if not all_sources:
        errors.append(
            "AVISO: Não foi possível carregar sources.yml para validar resolução de métricas."
        )
        return errors

    provided = get_all_provided_metrics(all_sources)

    if not AREAS_DIR.exists():
        return errors  # Sem áreas para validar

    for area_file in sorted(AREAS_DIR.glob("*.json")):
        try:
            with open(area_file, encoding="utf-8") as f:
                area_rules = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"ERRO: Não foi possível ler '{area_file.name}': {e}")
            continue

        referenced = extract_metrics_from_area(area_rules)
        orphans = referenced - provided

        if orphans:
            area_name = area_rules.get("nome", area_file.stem)
            for metric in sorted(orphans):
                errors.append(
                    f"MÉTRICA ÓRFÃ: '{metric}' referenciada em '{area_file.name}' "
                    f"(área: {area_name}) não possui nenhuma fonte em sources.yml "
                    f"que a forneça via campo 'provides'."
                )

    return errors


def main() -> int:
    """Executa validações e retorna código de saída (0=OK, 1=falha)."""
    ci_mode = "--ci" in sys.argv

    all_errors: list[str] = []

    # 1. Verificar arquivos de fontes restritas rastreados no git
    restricted_sources = load_restricted_sources()
    if restricted_sources:
        files = get_tracked_files(ci_mode)
        restricted_errors = check_restricted_files(files, restricted_sources)
        all_errors.extend(restricted_errors)

    # 2. Validar resolução de métricas (areas/*.json vs sources.yml)
    metric_errors = check_metric_resolution()
    all_errors.extend(metric_errors)

    # Relatório
    if all_errors:
        print("=" * 70, file=sys.stderr)
        print(
            "FALHA: Validação de fronteira de redistribuição detectou problemas:",
            file=sys.stderr,
        )
        print("=" * 70, file=sys.stderr)
        for error in all_errors:
            print(f"\n  ❌ {error}", file=sys.stderr)
        print("\n" + "=" * 70, file=sys.stderr)
        print(
            "\nAções sugeridas:",
            file=sys.stderr,
        )
        if any("VIOLAÇÃO" in e for e in all_errors):
            print(
                "  • Remova arquivos de fontes restritas do git: git rm --cached <arquivo>",
                file=sys.stderr,
            )
            print(
                "  • Adicione o caminho ao .gitignore ou use data/restricted/ (já ignorado)",
                file=sys.stderr,
            )
            print(
                "  • Configure o caminho local em config/local.yml",
                file=sys.stderr,
            )
        if any("MÉTRICA ÓRFÃ" in e for e in all_errors):
            print(
                "  • Adicione a fonte que fornece a métrica em sources.yml (campo 'provides')",
                file=sys.stderr,
            )
            print(
                "  • Ou remova a referência à métrica do arquivo de área",
                file=sys.stderr,
            )
        print(file=sys.stderr)
        return 1

    if ci_mode:
        print("✅ Validação de fronteira de redistribuição: OK")
        print(f"   • {len(restricted_sources)} fontes restritas verificadas")
        print(f"   • Métricas em areas/*.json todas resolvíveis via sources.yml")

    return 0


if __name__ == "__main__":
    sys.exit(main())
