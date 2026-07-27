"""Testes para pipeline/snapshot.py.

Valida:
- Geração de snapshot com zero veículos → snapshot vazio mas válido
- Geração de snapshot com um veículo + métricas → veredito correto
- Validação do snapshot gerado contra schema
- Geração de nome de arquivo (snapshot_filename)
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from pipeline.snapshot import generate_snapshot, snapshot_filename
from pipeline.vehicles import MetricValue, VehicleRecord


SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "snapshot.schema.json"


@pytest.fixture
def snapshot_schema() -> dict:
    """Carrega o schema de snapshot."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))


@pytest.fixture
def area_rules_simple() -> dict:
    """Regras de área sintéticas mínimas para testes do snapshot."""
    return {
        "area": 99,
        "nome": "Área de Teste",
        "vigencia": "2025-2028",
        "status": "experimental",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4"],
            "pontos": {"A1": 4, "A2": 3, "A3": 2, "A4": 1},
        },
        "nao_automatizavel": ["Critério X requer avaliação humana."],
        "veiculos": {
            "journalArticle": {
                "combinacao": "metrica_unica",
                "metrica": "test_percentil",
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


class TestGenerateSnapshotZeroVehicles:
    """Snapshot com zero veículos deve ser válido (R15.1)."""

    def test_zero_vehicles_returns_valid_snapshot(
        self, area_rules_simple: dict, snapshot_schema: dict
    ) -> None:
        """Snapshot vazio passa na validação de schema."""
        result = generate_snapshot(
            area_rules=area_rules_simple,
            vehicles={},
            snapshot_date="2026-07-15",
        )

        # Deve ter campos obrigatórios
        assert result["area"] == 99
        assert result["nome"] == "Área de Teste"
        assert result["vigencia"] == "2025-2028"
        assert result["status"] == "experimental"
        assert result["data_snapshot"] == "2026-07-15"
        assert result["veiculos"] == {}
        assert result["fontes_utilizadas"] == []
        assert result["nao_automatizavel"] == ["Critério X requer avaliação humana."]

        # Deve passar no schema
        jsonschema.validate(result, snapshot_schema)

    def test_zero_vehicles_with_fontes(
        self, area_rules_simple: dict, snapshot_schema: dict
    ) -> None:
        """Snapshot vazio com fontes_utilizadas preenchidas."""
        fontes = [{"id": "sjr", "data_arquivo": "2026-06-01", "registros": 0}]
        result = generate_snapshot(
            area_rules=area_rules_simple,
            vehicles={},
            snapshot_date="2026-07-15",
            fontes_utilizadas=fontes,
        )

        assert result["fontes_utilizadas"] == fontes
        jsonschema.validate(result, snapshot_schema)


class TestGenerateSnapshotWithVehicles:
    """Snapshot com veículos deve conter vereditos corretos."""

    def test_one_vehicle_correct_verdict(
        self, area_rules_simple: dict, snapshot_schema: dict
    ) -> None:
        """Um veículo com métrica produz veredito correto no snapshot."""
        vehicle = VehicleRecord(
            issn_l="1234-5678",
            titulos=["Journal of Testing"],
            issns={"1234-5678", "8765-4321"},
            metricas={
                "test_percentil": MetricValue(
                    valor=80.0, fonte_id="scopus", data_fonte="2026-06-01"
                )
            },
        )

        result = generate_snapshot(
            area_rules=area_rules_simple,
            vehicles={"1234-5678": vehicle},
            snapshot_date="2026-07-15",
            fontes_utilizadas=[
                {"id": "scopus", "data_arquivo": "2026-06-01", "registros": 100}
            ],
        )

        # Veículo deve estar presente
        assert "1234-5678" in result["veiculos"]
        veiculo = result["veiculos"]["1234-5678"]

        # Verificar metadados do veículo
        assert veiculo["titulo"] == "Journal of Testing"
        assert set(veiculo["issns"]) == {"1234-5678", "8765-4321"}

        # Verificar veredito para journalArticle
        assert "journalArticle" in veiculo["tipos"]
        tipo = veiculo["tipos"]["journalArticle"]
        assert tipo["estrato"] == "A1"  # 80 >= 75 → A1
        assert tipo["estado"] == "COMPLETO"
        assert isinstance(tipo["trilha"], list)
        assert len(tipo["trilha"]) > 0
        assert isinstance(tipo["metricas_utilizadas"], dict)
        assert isinstance(tipo["metricas_ausentes"], list)

        # Deve passar no schema
        jsonschema.validate(result, snapshot_schema)

    def test_vehicle_with_missing_metric_nao_classificavel(
        self, area_rules_simple: dict, snapshot_schema: dict
    ) -> None:
        """Veículo sem métricas relevantes → NAO_CLASSIFICAVEL."""
        vehicle = VehicleRecord(
            issn_l="9999-0001",
            titulos=["Journal Without Metrics"],
            issns={"9999-0001"},
            metricas={},  # Nenhuma métrica
        )

        result = generate_snapshot(
            area_rules=area_rules_simple,
            vehicles={"9999-0001": vehicle},
            snapshot_date="2026-07-15",
        )

        assert "9999-0001" in result["veiculos"]
        tipo = result["veiculos"]["9999-0001"]["tipos"]["journalArticle"]
        assert tipo["estrato"] == "NAO_CLASSIFICAVEL"
        assert tipo["estado"] == "NAO_CLASSIFICAVEL"

        # Deve passar no schema
        jsonschema.validate(result, snapshot_schema)


class TestSnapshotSchemaValidation:
    """Validação do snapshot gerado contra schema."""

    def test_generated_snapshot_conforms_to_schema(
        self, area_rules_simple: dict, snapshot_schema: dict
    ) -> None:
        """Snapshot gerado deve ser conforme ao schema."""
        vehicle = VehicleRecord(
            issn_l="0001-0782",
            titulos=["Communications of the ACM"],
            issns={"0001-0782", "1557-7317"},
            metricas={
                "test_percentil": MetricValue(
                    valor=55.0, fonte_id="scopus", data_fonte="2026-06-01"
                )
            },
        )

        result = generate_snapshot(
            area_rules=area_rules_simple,
            vehicles={"0001-0782": vehicle},
            snapshot_date="2026-07-15",
            fontes_utilizadas=[
                {"id": "scopus", "data_arquivo": "2026-06-01", "registros": 500}
            ],
        )

        # Validação explícita contra schema
        jsonschema.validate(result, snapshot_schema)

        # Verificar estrato correto (55 → A2 pois 50 <= 55 < 75)
        tipo = result["veiculos"]["0001-0782"]["tipos"]["journalArticle"]
        assert tipo["estrato"] == "A2"
        assert tipo["estado"] == "COMPLETO"


class TestSnapshotFilename:
    """Testes para geração de nome de arquivo."""

    def test_area02_date_2026_07_15(self) -> None:
        """area02 + 2026-07-15 → 'area02-2026-07.json'."""
        assert snapshot_filename(2, "2026-07-15") == "area02-2026-07.json"

    def test_area27_date_2025_01_31(self) -> None:
        """area27 + 2025-01-31 → 'area27-2025-01.json'."""
        assert snapshot_filename(27, "2025-01-31") == "area27-2025-01.json"

    def test_single_digit_area_padded(self) -> None:
        """Áreas com código de 1 dígito recebem zero-padding."""
        assert snapshot_filename(2, "2026-12-01") == "area02-2026-12.json"

    def test_three_digit_area(self) -> None:
        """Áreas com código > 99 não são truncadas."""
        assert snapshot_filename(100, "2026-03-10") == "area100-2026-03.json"
