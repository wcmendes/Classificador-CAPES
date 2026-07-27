"""Testes de validação do schema/snapshot.schema.json.

Valida que:
- O schema aceita snapshots completos e com zero veículos (R15.1)
- O schema rejeita documentos inválidos (campos faltando, tipos errados)
- Todos os valores de enum são aceitos corretamente (R16.3)
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


@pytest.fixture
def snapshot_schema(schema_dir: Path) -> dict:
    """Carrega o schema de snapshot."""
    schema_path = schema_dir / "snapshot.schema.json"
    assert schema_path.exists(), f"Schema não encontrado: {schema_path}"
    return json.loads(schema_path.read_text(encoding="utf-8-sig"))


@pytest.fixture
def minimal_snapshot() -> dict:
    """Snapshot mínimo válido — zero veículos (sistema nasce vazio)."""
    return {
        "area": 2,
        "nome": "Computação",
        "vigencia": "2025-2028",
        "status": "experimental",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"],
            "pontos": {"A1": 1, "A2": 0.875, "A3": 0.75, "A4": 0.625, "A5": 0, "A6": 0, "A7": 0, "A8": 0},
        },
        "data_snapshot": "2026-07-15",
        "fontes_utilizadas": [],
        "nao_automatizavel": [],
        "veiculos": {},
    }


@pytest.fixture
def full_snapshot() -> dict:
    """Snapshot completo com veículos e trilha de decisão."""
    return {
        "area": 2,
        "nome": "Computação",
        "vigencia": "2025-2028",
        "status": "experimental",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"],
            "pontos": {"A1": 1, "A2": 0.875, "A3": 0.75, "A4": 0.625, "A5": 0, "A6": 0, "A7": 0, "A8": 0},
        },
        "data_snapshot": "2026-07-15",
        "fontes_utilizadas": [
            {"id": "scopus", "data_arquivo": "2026-06-01", "registros": 28450},
        ],
        "nao_automatizavel": [
            "FWCI: os 5% dos artigos com maior FWCI sobem 1 nível."
        ],
        "veiculos": {
            "0001-0782": {
                "titulo": "Communications of the ACM",
                "issns": ["0001-0782", "1557-7317"],
                "tipos": {
                    "journalArticle": {
                        "estrato": "A1",
                        "estado": "COMPLETO",
                        "trilha": [
                            {
                                "etapa": "expressao_avaliada",
                                "metrica": "max(wos_percentil, scopus_percentil)",
                                "operandos": {"scopus_percentil": 98.2, "wos_percentil": None},
                                "valor_calculado": 98.2,
                                "nota": "wos_percentil ausente",
                            },
                            {
                                "etapa": "regra_ativada",
                                "regra_idx": 0,
                                "condicao": "min=87.5",
                                "resultado": "A1",
                            },
                            {
                                "etapa": "ajuste_sinalizado",
                                "condicao": "periodico_sbc",
                                "elegivel": False,
                            },
                        ],
                        "metricas_utilizadas": {
                            "scopus_percentil": {"valor": 98.2, "fonte": "scopus", "data": "2026-06-01"},
                        },
                        "metricas_ausentes": ["wos_percentil"],
                    }
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# Testes de aceitação — documentos válidos
# ---------------------------------------------------------------------------


class TestSnapshotSchemaValid:
    """Documentos que DEVEM ser aceitos pelo schema."""

    def test_zero_veiculos(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """R15.1: snapshot válido com zero veículos (sistema nasce vazio)."""
        jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_completo(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """Snapshot com veículos e trilha completa."""
        jsonschema.validate(full_snapshot, snapshot_schema)

    def test_com_schema_ref(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Snapshot pode ter campo $schema para validação local."""
        minimal_snapshot["$schema"] = "../schema/snapshot.schema.json"
        jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_fontes_utilizadas_vazio(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """fontes_utilizadas pode ser array vazio (zero fontes carregadas)."""
        minimal_snapshot["fontes_utilizadas"] = []
        jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_todos_status_validos(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Todos os valores de status devem ser aceitos."""
        for status in ("validada", "experimental", "nao_automatizavel"):
            minimal_snapshot["status"] = status
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_todos_estados_validos(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """Todos os valores de estado devem ser aceitos (R16.3)."""
        tipo_veredito = full_snapshot["veiculos"]["0001-0782"]["tipos"]["journalArticle"]
        for estado in ("COMPLETO", "ESTIMATIVA_CONSERVADORA", "NAO_CLASSIFICAVEL", "NAO_CONSIDERADO"):
            tipo_veredito["estado"] = estado
            jsonschema.validate(full_snapshot, snapshot_schema)

    def test_trilha_flexivel(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """Itens de trilha aceitam campos variáveis conforme etapa."""
        tipo_veredito = full_snapshot["veiculos"]["0001-0782"]["tipos"]["journalArticle"]
        tipo_veredito["trilha"] = [
            {"etapa": "fallback", "motivo": "nenhuma regra satisfeita"},
            {"etapa": "expressao_avaliada", "valor_calculado": 42.0, "extra_field": True},
        ]
        jsonschema.validate(full_snapshot, snapshot_schema)

    def test_escala_sem_pontos(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Escala sem campo pontos é válida (pontos é opcional)."""
        minimal_snapshot["escala"] = {"rotulos": ["A1", "A2"]}
        jsonschema.validate(minimal_snapshot, snapshot_schema)


# ---------------------------------------------------------------------------
# Testes de rejeição — documentos inválidos
# ---------------------------------------------------------------------------


class TestSnapshotSchemaInvalid:
    """Documentos que DEVEM ser rejeitados pelo schema."""

    def test_sem_area(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Faltando campo obrigatório 'area'."""
        del minimal_snapshot["area"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_sem_veiculos(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Faltando campo obrigatório 'veiculos'."""
        del minimal_snapshot["veiculos"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_vigencia_invalida(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Vigência com formato inválido (usa / em vez de -)."""
        minimal_snapshot["vigencia"] = "2025/2028"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_status_invalido(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Status com valor fora do enum."""
        minimal_snapshot["status"] = "invalido"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_estado_invalido(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """Estado com valor fora do enum."""
        full_snapshot["veiculos"]["0001-0782"]["tipos"]["journalArticle"]["estado"] = "PARCIAL"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(full_snapshot, snapshot_schema)

    def test_issn_invalido(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """ISSN com formato inválido no array issns."""
        full_snapshot["veiculos"]["0001-0782"]["issns"] = ["invalid"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(full_snapshot, snapshot_schema)

    def test_escala_sem_rotulos(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Escala sem rotulos é inválida."""
        minimal_snapshot["escala"] = {"pontos": {"A1": 1}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_escala_rotulos_insuficientes(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Escala com menos de 2 rotulos é inválida."""
        minimal_snapshot["escala"] = {"rotulos": ["A1"]}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_campo_adicional_raiz(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Campo não declarado na raiz é rejeitado."""
        minimal_snapshot["campo_extra"] = "valor"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_fonte_sem_id(
        self, snapshot_schema: dict, minimal_snapshot: dict
    ) -> None:
        """Fonte utilizada sem campo 'id' obrigatório."""
        minimal_snapshot["fontes_utilizadas"] = [
            {"data_arquivo": "2026-01-01", "registros": 100}
        ]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(minimal_snapshot, snapshot_schema)

    def test_veiculo_sem_titulo(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """Veículo sem campo 'titulo' obrigatório."""
        del full_snapshot["veiculos"]["0001-0782"]["titulo"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(full_snapshot, snapshot_schema)

    def test_veredito_sem_trilha(
        self, snapshot_schema: dict, full_snapshot: dict
    ) -> None:
        """Veredito sem campo 'trilha' obrigatório."""
        del full_snapshot["veiculos"]["0001-0782"]["tipos"]["journalArticle"]["trilha"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(full_snapshot, snapshot_schema)
