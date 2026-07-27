"""Testes para pipeline/validator.py — validação de arquivos JSON de área."""

import json
import tempfile
from pathlib import Path

import pytest

from pipeline.validator import load_area_schema, validate_area_file

# Raiz do monorepo
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def area_schema() -> dict:
    """Schema de área carregado uma vez."""
    return load_area_schema()


@pytest.fixture
def area02_path() -> Path:
    """Caminho para area02-computacao.json."""
    return REPO_ROOT / "areas" / "area02-computacao.json"


@pytest.fixture
def area27_path() -> Path:
    """Caminho para area27-administracao.json."""
    return REPO_ROOT / "areas" / "area27-administracao.json"


class TestValidAreaFiles:
    """Arquivos de área reais devem passar validação."""

    def test_area02_computacao_is_valid(self, area02_path: Path, area_schema: dict):
        result = validate_area_file(area02_path, schema=area_schema)
        assert isinstance(result, dict), f"Esperado dict válido, obteve erros: {result}"
        assert result["area"] == 2
        assert result["nome"] == "Computação"

    def test_area27_administracao_is_valid(self, area27_path: Path, area_schema: dict):
        result = validate_area_file(area27_path, schema=area_schema)
        assert isinstance(result, dict), f"Esperado dict válido, obteve erros: {result}"
        assert result["area"] == 27


class TestInvalidAreaFiles:
    """Arquivos inválidos devem ser rejeitados com indicação do campo."""

    def _write_temp_json(self, data: dict) -> Path:
        """Escreve JSON temporário e retorna o caminho."""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(data, tmp)
        tmp.close()
        return Path(tmp.name)

    def _minimal_valid_area(self) -> dict:
        """Retorna um JSON de área mínimo válido para ser modificado nos testes."""
        return {
            "area": 1,
            "nome": "Teste",
            "vigencia": "2025-2028",
            "procedimento": [1],
            "status": "experimental",
            "fonte_oficial": {
                "landing_url": "https://example.org"
            },
            "data_extracao": "2026-01-01",
            "escala": {
                "rotulos": ["A1", "A2"]
            },
            "veiculos": {
                "journalArticle": {
                    "combinacao": "metrica_unica",
                    "metrica": "sjr_valor",
                    "regras": [
                        {"min": 50, "resultado": "A1"},
                        {"min": 0, "max": 50, "resultado": "A2"}
                    ]
                }
            }
        }

    def test_missing_required_field_rejected(self, area_schema: dict):
        """Campo obrigatório ausente deve ser rejeitado com indicação do campo."""
        data = self._minimal_valid_area()
        del data["vigencia"]  # remove campo obrigatório

        path = self._write_temp_json(data)
        result = validate_area_file(path, schema=area_schema)

        assert isinstance(result, list), "Esperado lista de erros"
        assert len(result) >= 1
        # A mensagem deve indicar que 'vigencia' é requerido
        assert any("vigencia" in msg for msg in result), f"Erros: {result}"

    def test_invalid_enum_value_rejected(self, area_schema: dict):
        """Valor de enum inválido deve ser rejeitado."""
        data = self._minimal_valid_area()
        data["status"] = "invalido"  # deve ser "validada", "experimental" ou "nao_automatizavel"

        path = self._write_temp_json(data)
        result = validate_area_file(path, schema=area_schema)

        assert isinstance(result, list), "Esperado lista de erros"
        assert len(result) >= 1
        # A mensagem deve indicar o campo 'status' e o valor inválido
        assert any("status" in msg for msg in result), f"Erros: {result}"

    def test_invalid_vigencia_pattern_rejected(self, area_schema: dict):
        """Padrão inválido de vigência deve ser rejeitado."""
        data = self._minimal_valid_area()
        data["vigencia"] = "2025/2028"  # pattern exige XXXX-XXXX com dígitos

        path = self._write_temp_json(data)
        result = validate_area_file(path, schema=area_schema)

        assert isinstance(result, list), "Esperado lista de erros"
        assert len(result) >= 1
        # A mensagem deve indicar o campo 'vigencia'
        assert any("vigencia" in msg for msg in result), f"Erros: {result}"
