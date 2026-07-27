"""Gerador de snapshots imutáveis para o pipeline.

Gera snapshots conformes a schema/snapshot.schema.json, pré-calculando
vereditos para todos os veículos de uma área em uma data específica.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from pipeline.engine import TrailEntry, Verdict, classify
from pipeline.vehicles import MetricValue, VehicleRecord


# Caminho para o schema de snapshot
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "snapshot.schema.json"


def _load_snapshot_schema() -> dict:
    """Carrega e retorna o JSON Schema do snapshot."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8-sig"))


def _trail_entry_to_dict(entry: TrailEntry) -> dict:
    """Converte um TrailEntry em dicionário para o snapshot JSON."""
    d: dict = {"etapa": entry.etapa}
    if entry.metrica is not None:
        d["metrica"] = entry.metrica
    if entry.valor is not None:
        d["valor"] = entry.valor
    if entry.regra_idx is not None:
        d["regra_idx"] = entry.regra_idx
    if entry.resultado is not None:
        d["resultado"] = entry.resultado
    if entry.fonte_id is not None:
        d["fonte_id"] = entry.fonte_id
    if entry.data_fonte is not None:
        d["data_fonte"] = entry.data_fonte
    if entry.nota is not None:
        d["nota"] = entry.nota
    return d


def _extract_metricas_utilizadas(
    metricas: dict[str, MetricValue],
    trail: list[TrailEntry],
) -> dict[str, dict]:
    """Extrai métricas que foram efetivamente consumidas na classificação.

    Retorna dict no formato esperado pelo schema:
    { nome_metrica: { valor, fonte, data } }
    """
    # Coletar nomes de métricas mencionadas na trilha
    used_names: set[str] = set()
    for entry in trail:
        if entry.metrica and entry.metrica in metricas:
            used_names.add(entry.metrica)
        # Para expressões max/min, extrair os operandos individuais
        if entry.metrica and "(" in entry.metrica:
            # Parse operandos de expressões tipo max(a, b)
            inner = entry.metrica.split("(", 1)[1].rstrip(")")
            for operand in inner.split(","):
                op_name = operand.strip()
                if op_name in metricas:
                    used_names.add(op_name)

    result: dict[str, dict] = {}
    for name in sorted(used_names):
        mv = metricas[name]
        result[name] = {
            "valor": mv.valor,
            "fonte": mv.fonte_id,
            "data": mv.data_fonte,
        }
    return result


def _extract_metricas_ausentes(trail: list[TrailEntry], metricas: dict[str, MetricValue]) -> list[str]:
    """Extrai nomes de métricas que estavam ausentes durante a classificação."""
    ausentes: set[str] = set()
    for entry in trail:
        if entry.nota and "ausente" in entry.nota:
            # Extrair nome da métrica ausente da nota
            if entry.metrica and entry.metrica not in metricas:
                ausentes.add(entry.metrica)
        # Também checar métricas em expressões
        if entry.metrica and "(" in entry.metrica and entry.nota and "ausentes:" in entry.nota:
            # Extrair da nota "ausentes: ['x', 'y']"
            inner = entry.metrica.split("(", 1)[1].rstrip(")")
            for operand in inner.split(","):
                op_name = operand.strip()
                if op_name not in metricas:
                    ausentes.add(op_name)
    return sorted(ausentes)


def _verdict_to_tipo_dict(
    verdict: Verdict,
    metricas: dict[str, MetricValue],
) -> dict:
    """Converte um Verdict em dicionário tipoVeredito para o snapshot."""
    trilha = [_trail_entry_to_dict(e) for e in verdict.trilha]
    metricas_utilizadas = _extract_metricas_utilizadas(metricas, verdict.trilha)
    metricas_ausentes = _extract_metricas_ausentes(verdict.trilha, metricas)

    return {
        "estrato": verdict.estrato,
        "estado": verdict.estado,
        "trilha": trilha,
        "metricas_utilizadas": metricas_utilizadas,
        "metricas_ausentes": metricas_ausentes,
    }


def generate_snapshot(
    area_rules: dict,
    vehicles: dict[str, VehicleRecord],  # keyed by ISSN-L
    snapshot_date: str,  # ISO 8601 (YYYY-MM-DD)
    fontes_utilizadas: list[dict] | None = None,  # [{id, data_arquivo, registros}]
) -> dict:
    """Generates a snapshot for one area.

    Pre-calculates verdicts for all vehicles that have at least one relevant metric.

    Returns: dict conforming to schema/snapshot.schema.json
    """
    area_code = area_rules["area"]
    nome = area_rules["nome"]
    vigencia = area_rules["vigencia"]
    status = area_rules["status"]
    escala = area_rules["escala"]
    nao_automatizavel = area_rules.get("nao_automatizavel", [])

    # Inject data_extracao for classify to use
    area_rules_with_date = {**area_rules, "data_extracao": snapshot_date}

    # Build veiculos section
    veiculos_output: dict[str, dict] = {}
    item_types = list(area_rules.get("veiculos", {}).keys())

    for issn_l, vehicle in vehicles.items():
        tipos_output: dict[str, dict] = {}

        for item_type in item_types:
            verdict = classify(item_type, vehicle.metricas, area_rules_with_date)
            tipo_dict = _verdict_to_tipo_dict(verdict, vehicle.metricas)
            tipos_output[item_type] = tipo_dict

        # Include vehicle if it has at least one type with results
        if tipos_output:
            veiculos_output[issn_l] = {
                "titulo": vehicle.titulos[0] if vehicle.titulos else "",
                "issns": sorted(vehicle.issns),
                "tipos": tipos_output,
            }

    # Assemble snapshot
    snapshot: dict = {
        "area": area_code,
        "nome": nome,
        "vigencia": vigencia,
        "status": status,
        "escala": escala,
        "data_snapshot": snapshot_date,
        "fontes_utilizadas": fontes_utilizadas if fontes_utilizadas is not None else [],
        "nao_automatizavel": nao_automatizavel,
        "veiculos": veiculos_output,
    }

    # Validate against schema before returning
    schema = _load_snapshot_schema()
    jsonschema.validate(snapshot, schema)

    return snapshot


def snapshot_filename(area_code: int, snapshot_date: str) -> str:
    """Returns filename like 'area02-2026-07.json' (no day).

    Args:
        area_code: Numeric area code (e.g. 2, 27).
        snapshot_date: ISO 8601 date string (YYYY-MM-DD).

    Returns:
        Filename in format area{code:02d}-{YYYY-MM}.json
    """
    # Extract year-month from date (drop the day)
    date_no_day = snapshot_date[:7]  # "YYYY-MM"
    return f"area{area_code:02d}-{date_no_day}.json"
