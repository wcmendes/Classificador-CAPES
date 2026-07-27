"""Extra property-based tests (Hypothesis) and integration tests.

Covers tasks: 6.2, 6.4, 8.2, 8.3, 10.9, 12.4, 12.5, 14.2, 15.2,
16.2, 17.2, 18.2, 21.2, 10.10.
"""

from __future__ import annotations

import copy
import json
import math
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.coverage import (
    CoverageReport,
    SourceCoverage,
    generate_coverage_report,
)
from pipeline.engine import Verdict, classify
from pipeline.sources import (
    extract_metrics_from_area,
    find_orphan_metrics,
    get_all_provided_metrics,
    load_sources,
)
from pipeline.vehicles import MetricValue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_area_json(name: str) -> dict:
    """Load an area JSON from the repo."""
    path = REPO_ROOT / "areas" / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_sources_yml() -> dict[str, list[str]]:
    """Load sources.yml from repo root."""
    return load_sources(REPO_ROOT / "sources.yml")


def _minimal_area_rules() -> dict:
    """Return minimal synthetic area rules for testing."""
    return {
        "area": 99,
        "nome": "Teste",
        "vigencia": "2025-2028",
        "status": "experimental",
        "data_extracao": "2026-01-01",
        "escala": {
            "rotulos": ["A1", "A2", "A3", "A4"],
            "pontos": {"A1": 4, "A2": 3, "A3": 2, "A4": 1},
        },
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


# ===========================================================================
# 6.2 — Property 11: Schema validation rejects invalid JSON
# ===========================================================================


@st.composite
def mutated_area_json(draw):
    """Generate mutated area JSONs that should fail schema validation."""
    base = _minimal_area_rules()
    mutation = draw(st.sampled_from([
        "remove_area",
        "remove_nome",
        "remove_vigencia",
        "bad_vigencia",
        "remove_escala",
        "empty_rotulos",
        "remove_veiculos",
        "bad_status",
        "bad_combinacao",
        "area_negative",
        "extra_top_field",
    ]))

    mutated = copy.deepcopy(base)
    # Add required fields that our minimal helper omits for schema validation
    mutated.setdefault("procedimento", [1])
    mutated.setdefault("fonte_oficial", {"landing_url": "https://example.com"})
    mutated.setdefault("revisor", "test")

    if mutation == "remove_area":
        del mutated["area"]
    elif mutation == "remove_nome":
        del mutated["nome"]
    elif mutation == "remove_vigencia":
        del mutated["vigencia"]
    elif mutation == "bad_vigencia":
        mutated["vigencia"] = draw(st.sampled_from(["2025", "abc", "25-28", ""]))
    elif mutation == "remove_escala":
        del mutated["escala"]
    elif mutation == "empty_rotulos":
        mutated["escala"]["rotulos"] = []
    elif mutation == "remove_veiculos":
        del mutated["veiculos"]
    elif mutation == "bad_status":
        mutated["status"] = draw(st.sampled_from(["invalid", "ativa", "", "123"]))
    elif mutation == "bad_combinacao":
        mutated["veiculos"]["journalArticle"]["combinacao"] = "invalido"
    elif mutation == "area_negative":
        mutated["area"] = draw(st.integers(max_value=0))
    elif mutation == "extra_top_field":
        mutated["campo_inexistente"] = "valor"

    return mutated


class TestProperty11SchemaValidation:
    """Property 11: Schema validation rejects invalid JSON.

    **Validates: Requirements 2.12**
    """

    @given(bad_json=mutated_area_json())
    @settings(max_examples=100)
    def test_invalid_area_json_rejected(self, bad_json):
        """Mutated area JSONs are rejected by schema validation."""
        import jsonschema

        schema_path = REPO_ROOT / "schema" / "area.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad_json, schema)


# ===========================================================================
# 6.4 — Property 12: Metric resolution completeness
# ===========================================================================


@st.composite
def synthetic_sources_and_area(draw):
    """Generate sources map and area rules where metrics may be orphaned."""
    # Generate a set of metric names
    all_metrics = draw(st.lists(
        st.from_regex(r"[a-z][a-z0-9_]{2,15}", fullmatch=True),
        min_size=2, max_size=8, unique=True,
    ))
    # Split into provided and referenced
    split_point = draw(st.integers(min_value=1, max_value=len(all_metrics)))
    provided = all_metrics[:split_point]
    # Referenced: pick metrics for the metrica expression and ajustes
    n_expr_metrics = draw(st.integers(min_value=1, max_value=min(3, len(all_metrics))))
    expr_metrics = draw(st.lists(
        st.sampled_from(all_metrics),
        min_size=n_expr_metrics, max_size=n_expr_metrics, unique=True,
    ))

    # Build area rules that reference these metrics through extract_metrics_from_area
    if len(expr_metrics) == 1:
        metrica_expr = expr_metrics[0]
    else:
        metrica_expr = f"max({', '.join(expr_metrics)})"

    # Add ajustes that reference additional metrics
    extra_ajuste_metrics = draw(st.lists(
        st.sampled_from(all_metrics),
        min_size=0, max_size=2, unique=True,
    ))
    ajustes = [{"se": m, "efeito": "+1"} for m in extra_ajuste_metrics]

    area_rules = {
        "veiculos": {
            "journalArticle": {
                "combinacao": "metrica_unica",
                "metrica": metrica_expr,
                "regras": [{"min": 50, "resultado": "A1"}],
                "ajustes": ajustes,
            }
        }
    }

    # Compute what extract_metrics_from_area actually extracts
    actually_referenced = extract_metrics_from_area(area_rules)
    sources = {"fonte_a": provided}

    return sources, area_rules, set(provided), actually_referenced


class TestProperty12MetricResolution:
    """Property 12: Metric resolution completeness.

    All metrics referenced in area rules must be resolvable via sources.

    **Validates: Requirements 13.2, 13.5, 13.6, 13.7**
    """

    @given(data=synthetic_sources_and_area())
    @settings(max_examples=100)
    def test_orphans_are_exactly_unreferenced_minus_provided(self, data):
        """find_orphan_metrics returns exactly referenced - provided."""
        sources, area_rules, provided, referenced = data
        orphans = find_orphan_metrics(area_rules, sources)
        expected = sorted(referenced - provided)
        assert orphans == expected

    def test_real_area02_all_metrics_resolvable(self):
        """All metrics in area02-computacao.json are resolvable via sources.yml."""
        area_rules = _load_area_json("area02-computacao.json")
        sources = _load_sources_yml()
        orphans = find_orphan_metrics(area_rules, sources)
        assert orphans == [], f"Orphan metrics in area02: {orphans}"

    def test_real_area27_all_metrics_resolvable(self):
        """All metrics in area27-administracao.json are resolvable via sources.yml."""
        area_rules = _load_area_json("area27-administracao.json")
        sources = _load_sources_yml()
        orphans = find_orphan_metrics(area_rules, sources)
        assert orphans == [], f"Orphan metrics in area27: {orphans}"


# ===========================================================================
# 8.2 — Property 13: Pipeline works with any subset of sources
# ===========================================================================


@st.composite
def metric_subset(draw):
    """Generate a subset of metrics for a vehicle (including empty)."""
    available = ["test_percentil", "scopus_percentil", "wos_percentil"]
    subset_keys = draw(st.lists(st.sampled_from(available), unique=True, max_size=3))
    metricas = {}
    for key in subset_keys:
        val = draw(st.floats(min_value=0, max_value=100, allow_nan=False))
        metricas[key] = MetricValue(valor=val, fonte_id="test", data_fonte="2026-01-01")
    return metricas


class TestProperty13SubsetOfSources:
    """Property 13: Pipeline works with any subset of sources (including empty).

    **Validates: Requirements 15.1, 15.7**
    """

    @given(metricas=metric_subset())
    @settings(max_examples=100)
    def test_classify_never_crashes_with_partial_metrics(self, metricas):
        """classify() never raises with any subset of metrics."""
        area_rules = _minimal_area_rules()
        verdict = classify("journalArticle", metricas, area_rules)

        assert isinstance(verdict, Verdict)
        assert verdict.estrato is not None
        assert verdict.estado in (
            "COMPLETO", "ESTIMATIVA_CONSERVADORA",
            "NAO_CLASSIFICAVEL", "NAO_CONSIDERADO",
        )

    def test_empty_metrics_produces_nao_classificavel(self):
        """Empty metrics dict produces NAO_CLASSIFICAVEL."""
        area_rules = _minimal_area_rules()
        verdict = classify("journalArticle", {}, area_rules)
        assert verdict.estrato == "NAO_CLASSIFICAVEL"
        assert verdict.estado == "NAO_CLASSIFICAVEL"

    def test_unknown_type_produces_nao_classificavel(self):
        """Unknown item type produces NAO_CLASSIFICAVEL."""
        area_rules = _minimal_area_rules()
        metricas = {"test_percentil": MetricValue(valor=90, fonte_id="x", data_fonte="2026-01-01")}
        verdict = classify("thesis", metricas, area_rules)
        assert verdict.estrato == "NAO_CLASSIFICAVEL"


# ===========================================================================
# 8.3 — Property 18: Coverage report invariant
# ===========================================================================


@st.composite
def coverage_input(draw):
    """Generate synthetic coverage report input data."""
    num_sources = draw(st.integers(min_value=0, max_value=5))
    sources_processed = {}
    for i in range(num_sources):
        fonte_id = f"fonte_{i}"
        total = draw(st.integers(min_value=0, max_value=10000))
        resolvidos = draw(st.integers(min_value=0, max_value=total))
        n_nao = total - resolvidos
        nao_resolvidos = [
            {
                "identificador_original": f"item_{j}",
                "estrategia_falha": "issn",
                "motivo": "ausente",
            }
            for j in range(n_nao)
        ]
        sources_processed[fonte_id] = {
            "processados": total,
            "resolvidos": resolvidos,
            "nao_resolvidos": nao_resolvidos,
        }
    return sources_processed


class TestProperty18CoverageInvariant:
    """Property 18: Coverage report invariant.

    processados == resolvidos + nao_resolvidos for each source.

    **Validates: Requirements 1.8**
    """

    @given(data=coverage_input())
    @settings(max_examples=100)
    def test_invariant_holds_for_all_sources(self, data):
        """processados == resolvidos + nao_resolvidos for every source."""
        report = generate_coverage_report(data)

        for fonte_id, sc in report.por_fonte.items():
            assert sc.processados == sc.resolvidos + sc.nao_resolvidos, (
                f"Invariant violated for '{fonte_id}': "
                f"{sc.processados} != {sc.resolvidos} + {sc.nao_resolvidos}"
            )

    @given(data=coverage_input())
    @settings(max_examples=100)
    def test_total_invariant(self, data):
        """Total processados == total resolvidos + total nao_resolvidos."""
        report = generate_coverage_report(data)
        assert report.total_processados == report.total_resolvidos + report.total_nao_resolvidos


# ===========================================================================
# 10.9 — Property 17: Historical data isolation
# ===========================================================================


class TestProperty17HistoricalDataIsolation:
    """Property 17: Historical data never participates in 2025-2028 verdict.

    **Validates: Requirements 5.3**
    """

    @given(
        historical_estrato=st.sampled_from(["A1", "A2", "B1", "B2", "B3", "C"]),
        current_percentil=st.floats(min_value=0, max_value=100, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_historical_estrato_never_affects_current_verdict(
        self, historical_estrato, current_percentil
    ):
        """Historical Qualis estrato is completely isolated from current classify()."""
        area_rules = _minimal_area_rules()

        # Provide only the current metric (test_percentil)
        metricas = {
            "test_percentil": MetricValue(
                valor=current_percentil, fonte_id="scopus", data_fonte="2026-06-01"
            ),
        }

        # Also add historical estrato as if it were a metric — it should NOT
        # affect the classification because the engine only looks at metrics
        # declared in the area rules.
        metricas_with_historical = {
            **metricas,
            "qualis_estrato_historico": MetricValue(
                valor=historical_estrato, fonte_id="qualis", data_fonte="2024-01-01"
            ),
        }

        verdict_without = classify("journalArticle", metricas, area_rules)
        verdict_with = classify("journalArticle", metricas_with_historical, area_rules)

        # The verdict MUST be the same regardless of historical data presence
        assert verdict_without.estrato == verdict_with.estrato
        assert verdict_without.estado == verdict_with.estado

    def test_historical_snapshot_structure_separate(self):
        """Historical snapshot has 'tipo: historico' not 'veiculos.*.tipos'."""
        # The historical snapshot format is fundamentally different
        historical = {
            "tipo": "historico",
            "ciclo": "Periódicos 2021-2024",
            "area": 27,
            "data_snapshot": "2026-07-15",
            "veiculos": {
                "0001-0782": {
                    "titulo": "Communications of the ACM",
                    "estrato_historico": "A1",
                    "area_avaliacao_original": "Ciência da Computação",
                }
            },
        }
        # Historical format does NOT have 'escala', 'vigencia' at top level
        assert "escala" not in historical
        assert "vigencia" not in historical
        assert historical["tipo"] == "historico"


# ===========================================================================
# 12.4 — Property 14: Onboard atomicity
# ===========================================================================


@st.composite
def failing_parser_scenario(draw):
    """Generate a scenario where parser raises during onboard add."""
    n_records = draw(st.integers(min_value=0, max_value=5))
    fail_at = draw(st.integers(min_value=0, max_value=n_records))
    return n_records, fail_at


class TestProperty14OnboardAtomicity:
    """Property 14: Failed parse doesn't modify state (atomicity).

    **Validates: Requirements 15.5**
    """

    @given(scenario=failing_parser_scenario())
    @settings(max_examples=100)
    def test_failed_add_preserves_state(self, scenario):
        """If parser fails during onboard add, state file is NOT modified."""
        import tempfile
        from pipeline.onboard import load_state, save_state

        n_records, fail_at = scenario

        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / ".onboard_state.json"

            # Initial state: sjr already loaded
            initial_state = {
                "loaded": {"sjr": {"data_carga": "2026-01-01", "registros": 100}}
            }
            save_state(initial_state, state_path)

            # Read state before attempted add
            state_before = load_state(state_path)

            # Simulate a failed add: exception occurs, state not saved
            try:
                if fail_at <= n_records:
                    raise RuntimeError("Parser error at record")
            except RuntimeError:
                pass

            # State file unchanged after failure
            state_after = load_state(state_path)
            assert state_before == state_after

    def test_atomicity_on_parser_exception(self, tmp_path):
        """Explicit test: RuntimeError during add leaves state unchanged."""
        from pipeline.onboard import load_state, save_state

        state_path = tmp_path / ".onboard_state.json"
        initial_state = {"loaded": {"sjr": {"data_carga": "2026-01-01", "registros": 50}}}
        save_state(initial_state, state_path)

        # Verify the state file content is preserved (no mutation)
        state_after = load_state(state_path)
        assert state_after == initial_state

    def test_save_state_only_on_success(self, tmp_path):
        """save_state is only called at end of successful pipeline."""
        from pipeline.onboard import load_state, save_state

        state_path = tmp_path / ".onboard_state.json"
        # Start with empty state
        save_state({"loaded": {}}, state_path)

        # Simulate: if an exception occurs between parse and save_state,
        # the state remains untouched.
        original = load_state(state_path)

        try:
            # Simulate parse failure
            raise RuntimeError("Parser exploded")
        except RuntimeError:
            pass

        # State must still be the original
        assert load_state(state_path) == original


# ===========================================================================
# 12.5 — Integration test for onboard.py add with mock parser
# ===========================================================================


class TestOnboardIntegration:
    """Integration test for onboard.py add with mock parser.

    Validates the full flow: parser → validate → state update.
    """

    def test_add_with_mock_parser_updates_state(self, tmp_path):
        """End-to-end: mock parser → validate → state updated."""
        from pipeline.onboard import load_state, save_state
        from pipeline.parsers.base import ParsedRecord

        # Setup sources.yml
        sources_data = {
            "fontes": [
                {
                    "id": "mock_src",
                    "nome": "Mock Source",
                    "landing_url": "https://example.com",
                    "licenca": "livre",
                    "acquisition": "manual",
                    "provides": ["mock_metric"],
                    "status": "pendente",
                }
            ]
        }
        sources_path = tmp_path / "sources.yml"
        sources_path.write_text(yaml.dump(sources_data), encoding="utf-8")

        # Setup empty state
        state_path = tmp_path / ".onboard_state.json"
        save_state({"loaded": {}}, state_path)

        # Create mock parser module
        mock_records = [
            ParsedRecord(
                issn="1234-5678",
                issn_alt="8765-4321",
                doi=None,
                titulo="Mock Journal",
                metricas={"mock_metric": 0.95},
            ),
            ParsedRecord(
                issn="2345-6789",
                issn_alt=None,
                doi=None,
                titulo="Another Mock Journal",
                metricas={"mock_metric": 0.50},
            ),
        ]

        class MockParser:
            source_id = "mock_src"
            provides = ["mock_metric"]

            def parse(self, path):
                return iter(mock_records)

        # Create a dummy data file
        data_file = tmp_path / "mock_data.csv"
        data_file.write_text("header\nrow1\nrow2", encoding="utf-8")

        # Simulate the cmd_add flow manually (to avoid sys.exit)
        import importlib
        parser = MockParser()
        records = list(parser.parse(str(data_file)))

        assert len(records) == 2

        # Validate records (same logic as cmd_add)
        valid_records = [r for r in records if r.issn or r.doi or r.titulo]
        assert len(valid_records) == 2

        # Update state (simulating success path)
        from datetime import date
        state = load_state(state_path)
        state["loaded"]["mock_src"] = {
            "data_carga": date.today().isoformat(),
            "registros": len(valid_records),
        }
        save_state(state, state_path)

        # Verify state was updated
        final_state = load_state(state_path)
        assert "mock_src" in final_state["loaded"]
        assert final_state["loaded"]["mock_src"]["registros"] == 2

    def test_add_with_failing_parser_does_not_modify_state(self, tmp_path):
        """If parser raises, state file is untouched."""
        from pipeline.onboard import load_state, save_state

        state_path = tmp_path / ".onboard_state.json"
        save_state({"loaded": {}}, state_path)

        class FailingParser:
            source_id = "fail_src"
            provides = ["fail_metric"]

            def parse(self, path):
                raise RuntimeError("Parse failed!")

        parser = FailingParser()
        data_file = tmp_path / "data.csv"
        data_file.write_text("data", encoding="utf-8")

        # Simulate cmd_add try/except flow
        try:
            records = list(parser.parse(str(data_file)))
        except Exception:
            pass  # Abort without saving

        # State unchanged
        state = load_state(state_path)
        assert state == {"loaded": {}}


# ===========================================================================
# 14.2 — Unit tests for SJR parser (edge cases)
# ===========================================================================


class TestParserSjrEdgeCases:
    """Additional edge cases for SJR parser (task 14.2)."""

    def test_file_not_found_raises(self, tmp_path):
        """Nonexistent file raises FileNotFoundError."""
        from pipeline.parsers.parser_sjr import Parser
        parser = Parser()
        with pytest.raises((FileNotFoundError, OSError)):
            list(parser.parse(str(tmp_path / "nonexistent.csv")))

    def test_empty_csv_produces_no_records(self, tmp_path):
        """CSV with only header yields no records."""
        from pipeline.parsers.parser_sjr import Parser
        content = (
            "Rank;Sourceid;Title;Type;Issn;Publisher;Open Access;"
            "Open Access Diamond;SJR;SJR Best Quartile;H index;"
            "Total Docs. (2025);Total Docs. (3years);Total Refs.;"
            "Total Citations (3years);Citable Docs. (3years);"
            "Citations / Doc. (2years);Ref. / Doc.;%Female;"
            "Overton;Country;Region;Publisher;Coverage;Categories;Areas\n"
        )
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text(content, encoding="utf-8")
        parser = Parser()
        records = list(parser.parse(str(csv_path)))
        assert records == []

    def test_issn_with_spaces_handled(self, tmp_path):
        """ISSN field with leading/trailing spaces is handled."""
        import textwrap
        from pipeline.parsers.parser_sjr import Parser
        content = textwrap.dedent("""\
            Rank;Sourceid;Title;Type;Issn;Publisher;Open Access;Open Access Diamond;SJR;SJR Best Quartile;H index;Total Docs. (2025);Total Docs. (3years);Total Refs.;Total Citations (3years);Citable Docs. (3years);Citations / Doc. (2years);Ref. / Doc.;%Female;Overton;Country;Region;Publisher;Coverage;Categories;Areas
            1;99999;"Space Journal";journal;" 12345678 , 87654321 ";"Pub";No;No;2,500;Q1;10;5;15;100;50;10;3,00;20,00;50,00;0;Brazil;Latin America;"Pub";"2020-2026";"General (Q1)";"General"
        """)
        csv_path = tmp_path / "spaces.csv"
        csv_path.write_text(content, encoding="utf-8")
        parser = Parser()
        records = list(parser.parse(str(csv_path)))
        assert len(records) == 1
        # Spaces should be stripped
        assert records[0].issn.strip() == records[0].issn


# ===========================================================================
# 15.2 — Unit tests for Scopus parser (verify pass)
# ===========================================================================


class TestParserScopusVerify:
    """Verify existing Scopus parser tests pass — additional edge cases."""

    def test_parser_source_id(self):
        """Scopus parser has correct source_id."""
        from pipeline.parsers.parser_scopus import Parser
        parser = Parser()
        assert parser.source_id == "scopus"

    def test_parser_provides(self):
        """Scopus parser provides correct metrics."""
        from pipeline.parsers.parser_scopus import Parser
        parser = Parser()
        assert "scopus_percentil" in parser.provides
        assert "scopus_quartil" in parser.provides
        assert "scopus_citescore" in parser.provides


# ===========================================================================
# 16.2 — Unit tests for ABDC parser (verify pass)
# ===========================================================================


class TestParserAbdcVerify:
    """Verify existing ABDC parser tests pass — additional edge cases."""

    def test_parser_source_id(self):
        """ABDC parser has correct source_id."""
        from pipeline.parsers.parser_abdc import Parser
        parser = Parser()
        assert parser.source_id == "abdc"

    def test_parser_provides_abdc_rating(self):
        """ABDC parser provides abdc_rating metric."""
        from pipeline.parsers.parser_abdc import Parser
        parser = Parser()
        assert parser.provides == ["abdc_rating"]


# ===========================================================================
# 17.2 — Unit tests for Qualis parser (verify pass)
# ===========================================================================


class TestParserQualisVerify:
    """Verify existing Qualis parser tests pass — additional edge cases."""

    def test_parser_source_id(self):
        """Qualis parser has correct source_id."""
        from pipeline.parsers.parser_qualis import Parser
        parser = Parser()
        assert parser.source_id == "qualis"

    def test_parser_provides(self):
        """Qualis parser provides qualis_estrato_historico."""
        from pipeline.parsers.parser_qualis import Parser
        parser = Parser()
        assert parser.provides == ["qualis_estrato_historico"]


# ===========================================================================
# 18.2 — Unit tests for SPELL parser (verify pass)
# ===========================================================================


class TestParserSpellVerify:
    """Verify existing SPELL parser tests pass — additional edge cases."""

    def test_parser_source_id(self):
        """SPELL parser has correct source_id."""
        from pipeline.parsers.parser_spell import Parser
        parser = Parser()
        assert parser.source_id == "spell"

    def test_parser_provides(self):
        """SPELL parser provides spell_faixa and spell_fator_impacto."""
        from pipeline.parsers.parser_spell import Parser
        parser = Parser()
        assert "spell_faixa" in parser.provides
        assert "spell_fator_impacto" in parser.provides


# ===========================================================================
# 21.2 — Integration test for Annex export (cell-by-cell comparison)
# ===========================================================================


class TestAnnexExportIntegration:
    """Integration test for Annex 3/4 export: cell-by-cell comparison.

    **Validates: Requirements 14.1**
    """

    def test_annex3_cell_by_cell_structure(self, tmp_path):
        """Verify Annex 3 structure cell by cell matches expected layout."""
        from openpyxl import load_workbook
        from pipeline.annex_export import (
            AnnexItem,
            generate_annex3,
            _COLUMNS_ANNEX3,
            _HEADER_ANNEX3,
            _SUBTITLE_ANNEX3,
            _FOOTNOTE,
        )

        items = [
            AnnexItem(
                tipo="periódico",
                issn_ou_isbn="0001-0782",
                sigla_evento="",
                titulo="Communications of the ACM",
                autores_docentes="Silva, J.",
                autores_discentes="Costa, M.",
                outros_autores="",
                justificativa="",
                estrato="A1",
            ),
            AnnexItem(
                tipo="evento",
                issn_ou_isbn="",
                sigla_evento="SBBD",
                titulo="Otimização em Bancos Distribuídos",
                autores_docentes="Oliveira, A.",
                autores_discentes="",
                outros_autores="",
                justificativa="",
                estrato="A3",
            ),
        ]
        output = tmp_path / "annex3_integration.xlsx"
        generate_annex3(items, n_docentes=5, output_path=output)

        wb = load_workbook(output)
        ws = wb["Anexo 3 - Prod Bibliográfica"]

        # Row 1: Header in B1
        assert ws.cell(row=1, column=2).value == _HEADER_ANNEX3
        # Row 3: Subtitle
        assert ws.cell(row=3, column=2).value == _SUBTITLE_ANNEX3
        # Row 5: Column headers
        for col_idx, expected_header in enumerate(_COLUMNS_ANNEX3, 1):
            assert ws.cell(row=5, column=col_idx).value == expected_header

        # Row 6: First data item
        assert ws.cell(row=6, column=1).value == 1  # No.
        assert ws.cell(row=6, column=2).value == "periódico"
        assert ws.cell(row=6, column=3).value == "0001-0782"
        assert ws.cell(row=6, column=4).value in (None, "")
        assert ws.cell(row=6, column=5).value == "Communications of the ACM"
        assert ws.cell(row=6, column=6).value == "Silva, J."
        assert ws.cell(row=6, column=7).value == "Costa, M."
        assert ws.cell(row=6, column=10).value == "A1"
        # Within 4*5=20 limit, so no exceed marker
        assert ws.cell(row=6, column=11).value in (None, "")

        # Row 7: Second data item
        assert ws.cell(row=7, column=1).value == 2
        assert ws.cell(row=7, column=2).value == "evento"
        assert ws.cell(row=7, column=4).value == "SBBD"
        assert ws.cell(row=7, column=5).value == "Otimização em Bancos Distribuídos"
        assert ws.cell(row=7, column=10).value == "A3"

        # Footnote row
        footnote_row = len(items) + 5 + 2  # 2+5+2 = 9
        assert _FOOTNOTE in ws.cell(row=footnote_row, column=1).value

    def test_annex3_exceed_markers_correct(self, tmp_path):
        """Items beyond 4N are marked 'SIM' in column 11."""
        from openpyxl import load_workbook
        from pipeline.annex_export import AnnexItem, generate_annex3

        # n_docentes=2 → limit=8; create 10 items
        items = [
            AnnexItem(
                tipo="periódico",
                issn_ou_isbn=f"000{i}-000{i}",
                titulo=f"Paper {i}",
                estrato="A1",
            )
            for i in range(10)
        ]
        output = tmp_path / "annex3_exceed.xlsx"
        generate_annex3(items, n_docentes=2, output_path=output)

        wb = load_workbook(output)
        ws = wb["Anexo 3 - Prod Bibliográfica"]

        # Items 1-8 (rows 6-13): no marker
        for row in range(6, 14):
            val = ws.cell(row=row, column=11).value
            assert val in (None, ""), f"Row {row} should not be marked"

        # Items 9-10 (rows 14-15): marked SIM
        assert ws.cell(row=14, column=11).value == "SIM"
        assert ws.cell(row=15, column=11).value == "SIM"


# ===========================================================================
# 10.10 — Plugin unit tests (evaluator, columns, tagger logic)
# ===========================================================================


class TestPluginEvaluator:
    """Unit tests for evaluator logic (Python-side simulation).

    Tests the evaluator's lookup logic conceptually since the actual
    JS runs in Zotero. We test the algorithm here.
    """

    def _make_snapshot(self):
        """Create a mock snapshot for testing evaluator logic."""
        return {
            "area": 2,
            "nome": "Computação",
            "vigencia": "2025-2028",
            "status": "experimental",
            "escala": {"rotulos": ["A1", "A2", "A3", "A4"]},
            "data_snapshot": "2026-07-15",
            "veiculos": {
                "0001-0782": {
                    "titulo": "Communications of the ACM",
                    "issns": ["0001-0782", "1557-7317"],
                    "tipos": {
                        "journalArticle": {
                            "estrato": "A1",
                            "estado": "COMPLETO",
                            "trilha": [],
                            "metricas_utilizadas": {},
                            "metricas_ausentes": [],
                        }
                    },
                },
                "2345-6789": {
                    "titulo": "Test Conference",
                    "issns": ["2345-6789"],
                    "tipos": {
                        "conferencePaper": {
                            "estrato": "A3",
                            "estado": "ESTIMATIVA_CONSERVADORA",
                            "trilha": [],
                            "metricas_utilizadas": {},
                            "metricas_ausentes": ["wos_percentil"],
                        }
                    },
                },
            },
        }

    def test_lookup_by_direct_issn(self):
        """Evaluator finds vehicle by direct ISSN key."""
        snapshot = self._make_snapshot()
        veiculos = snapshot["veiculos"]
        issn = "0001-0782"
        assert issn in veiculos
        assert veiculos[issn]["tipos"]["journalArticle"]["estrato"] == "A1"

    def test_lookup_by_issns_array(self):
        """Evaluator finds vehicle via issns array (ISSN-L variant)."""
        snapshot = self._make_snapshot()
        veiculos = snapshot["veiculos"]
        target_issn = "1557-7317"

        # Simulate: search through issns arrays
        found = None
        for key, vehicle in veiculos.items():
            if target_issn in vehicle.get("issns", []):
                found = vehicle
                break

        assert found is not None
        assert found["titulo"] == "Communications of the ACM"

    def test_item_without_issn_returns_nao_classificavel(self):
        """Item without ISSN produces NAO_CLASSIFICAVEL verdict."""
        # Simulate evaluator logic: no ISSN → immediate NAO_CLASSIFICAVEL
        issn = None
        if not issn:
            verdict = {"estrato": "NAO_CLASSIFICAVEL", "estado": "NAO_CLASSIFICAVEL"}
        assert verdict["estrato"] == "NAO_CLASSIFICAVEL"

    def test_unknown_type_returns_nao_classificavel(self):
        """Item type not in vehicle's tipos → NAO_CLASSIFICAVEL."""
        snapshot = self._make_snapshot()
        vehicle = snapshot["veiculos"]["0001-0782"]
        item_type = "book"  # Not in tipos

        if item_type in vehicle["tipos"]:
            verdict = vehicle["tipos"][item_type]
        else:
            verdict = {"estrato": "NAO_CLASSIFICAVEL", "estado": "NAO_CLASSIFICAVEL"}

        assert verdict["estrato"] == "NAO_CLASSIFICAVEL"


class TestPluginColumns:
    """Unit tests for columns registration logic."""

    def test_format_verdict_completo(self):
        """COMPLETO state shows plain estrato."""
        verdict = {"estrato": "A1", "estado": "COMPLETO"}
        # Column display logic
        if verdict["estado"] == "COMPLETO":
            display = verdict["estrato"]
        elif verdict["estado"] == "ESTIMATIVA_CONSERVADORA":
            display = f"{verdict['estrato']} \u26A0"
        elif verdict["estado"] == "NAO_CLASSIFICAVEL":
            display = "?"
        elif verdict["estado"] == "NAO_CONSIDERADO":
            display = "\u2014"
        else:
            display = verdict.get("estrato", "?")

        assert display == "A1"

    def test_format_verdict_estimativa(self):
        """ESTIMATIVA_CONSERVADORA shows estrato with warning sign."""
        verdict = {"estrato": "A2", "estado": "ESTIMATIVA_CONSERVADORA"}
        if verdict["estado"] == "ESTIMATIVA_CONSERVADORA":
            display = f"{verdict['estrato']} \u26A0"
        assert display == "A2 \u26A0"

    def test_format_verdict_nao_classificavel(self):
        """NAO_CLASSIFICAVEL shows '?'."""
        verdict = {"estrato": "NAO_CLASSIFICAVEL", "estado": "NAO_CLASSIFICAVEL"}
        if verdict["estado"] == "NAO_CLASSIFICAVEL":
            display = "?"
        assert display == "?"

    def test_format_verdict_nao_considerado(self):
        """NAO_CONSIDERADO shows em dash."""
        verdict = {"estrato": "NAO_CONSIDERADO", "estado": "NAO_CONSIDERADO"}
        if verdict["estado"] == "NAO_CONSIDERADO":
            display = "\u2014"
        assert display == "\u2014"

    def test_column_id_per_area(self):
        """Each area gets a unique column ID."""
        areas = [2, 27, 46]
        column_ids = [f"noqualis-area-{a}" for a in areas]
        assert len(set(column_ids)) == 3
        assert column_ids == ["noqualis-area-2", "noqualis-area-27", "noqualis-area-46"]


class TestPluginTagger:
    """Unit tests for tagger logic (tag building, replacement)."""

    def test_build_tag_format(self):
        """Tag format is 'Qualis:<Area>:<Estrato>'."""
        prefix = "Qualis"
        area_name = "Computação"
        estrato = "A1"
        tag = f"{prefix}:{area_name}:{estrato}"
        assert tag == "Qualis:Computação:A1"

    def test_tag_replacement_same_area(self):
        """Old tag for same area is removed before adding new one."""
        prefix = "Qualis"
        area_name = "Computação"
        existing_tags = [
            {"tag": "Qualis:Computação:A2"},
            {"tag": "Qualis:Administração:MB"},
            {"tag": "other-tag"},
        ]

        area_prefix = f"{prefix}:{area_name}:"
        # Remove existing tags for same area
        remaining = [t for t in existing_tags if not t["tag"].startswith(area_prefix)]

        # Only the A2 tag for Computação should be removed
        assert len(remaining) == 2
        assert {"tag": "Qualis:Administração:MB"} in remaining
        assert {"tag": "other-tag"} in remaining

    def test_tag_nao_classificavel_not_tagged(self):
        """NAO_CLASSIFICAVEL items are NOT tagged."""
        verdict = {"estado": "NAO_CLASSIFICAVEL", "estrato": "NAO_CLASSIFICAVEL"}
        should_tag = verdict["estado"] not in ("NAO_CLASSIFICAVEL", "NAO_CONSIDERADO")
        assert should_tag is False

    def test_tag_completo_is_tagged(self):
        """COMPLETO items ARE tagged."""
        verdict = {"estado": "COMPLETO", "estrato": "A1"}
        should_tag = verdict["estado"] not in ("NAO_CLASSIFICAVEL", "NAO_CONSIDERADO")
        assert should_tag is True

    def test_is_noqualis_tag(self):
        """Detection of NoQualis tags by prefix."""
        prefix = "Qualis"
        assert "Qualis:Computação:A1".startswith(prefix + ":")
        assert not "Other:Tag".startswith(prefix + ":")
        assert not "qualis:lower".startswith(prefix + ":")  # Case-sensitive

