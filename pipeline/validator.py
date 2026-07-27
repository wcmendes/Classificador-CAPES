"""Validação de arquivos JSON de área contra schema/area.schema.json.

Implementa:
- validate_area_file: valida um arquivo JSON de área e retorna erros ou dados carregados
- load_area_schema: carrega o schema de área do diretório schema/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError


# Raiz do monorepo (um nível acima de pipeline/)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schema" / "area.schema.json"


def load_area_schema(schema_path: Path | None = None) -> dict[str, Any]:
    """Carrega o JSON Schema de área.

    Args:
        schema_path: Caminho para o schema. Se None, usa o padrão em schema/area.schema.json.

    Returns:
        Dicionário com o schema carregado.

    Raises:
        FileNotFoundError: Se o arquivo de schema não existe.
        json.JSONDecodeError: Se o schema não é JSON válido.
    """
    path = schema_path or _SCHEMA_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_area_file(
    area_path: Path | str,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any] | list[str]:
    """Valida um arquivo JSON de área contra o schema.

    Args:
        area_path: Caminho para o arquivo JSON de área.
        schema: Schema já carregado. Se None, carrega do caminho padrão.

    Returns:
        - Se válido: dicionário com os dados carregados do arquivo.
        - Se inválido: lista de strings descrevendo os erros de validação,
          incluindo a localização do campo inválido (JSON path).
    """
    area_path = Path(area_path)

    # Carregar o arquivo de área
    with open(area_path, encoding="utf-8") as f:
        data = json.load(f)

    # Carregar schema se não fornecido
    if schema is None:
        schema = load_area_schema()

    # Remover campo $schema do dado antes de validar (é um meta-campo de IDE,
    # não faz parte do conteúdo semântico do arquivo de área)
    data_to_validate = {k: v for k, v in data.items() if k != "$schema"}

    # Criar validador e coletar erros
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data_to_validate), key=lambda e: list(e.absolute_path))

    if not errors:
        return data

    # Formatar mensagens de erro com localização do campo
    messages: list[str] = []
    for error in errors:
        path = _format_path(error)
        messages.append(f"{path}: {error.message}")

    return messages


def _format_path(error: ValidationError) -> str:
    """Formata o caminho JSON de um erro de validação.

    Ex: $.veiculos.journalArticle.combinacao
    """
    parts = list(error.absolute_path)
    if not parts:
        return "$"
    return "$." + ".".join(str(p) for p in parts)
