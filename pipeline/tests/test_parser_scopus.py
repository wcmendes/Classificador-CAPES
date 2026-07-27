"""Testes para pipeline/parsers/parser_scopus.py.

Usa dados sintéticos escritos em XLSX temporários (nunca o arquivo real de 15 MB).
"""

from pathlib import Path

import pandas as pd
import pytest

from pipeline.parsers.parser_scopus import Parser, _format_issn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parser() -> Parser:
    return Parser()


@pytest.fixture
def scopus_xlsx_basic(tmp_path: Path) -> Path:
    """XLSX sintético com colunas da Source Title List (sem métricas CiteScore)."""
    data = {
        "Source Title": [
            "Journal of Testing",
            "Inactive Journal",
            "No ISSN Journal",
            "Only EISSN Journal",
        ],
        "ISSN": ["12345678", "00181390", "", ""],
        "EISSN": ["87654321", "", "", "23456789"],
        "Active or Inactive": ["Active", "Inactive", "Active", "Active"],
        "Source Type": ["Journal", "Journal", "Journal", "Journal"],
    }
    df = pd.DataFrame(data)
    path = tmp_path / "scopus_basic.xlsx"
    df.to_excel(path, index=False, sheet_name="Scopus Sources Jun. 2026")
    return path


@pytest.fixture
def scopus_xlsx_with_citescore(tmp_path: Path) -> Path:
    """XLSX sintético com colunas de CiteScore/Percentile/Quartile."""
    data = {
        "Source Title": [
            "Top Journal",
            "Mid Journal",
            "Low Journal",
            "No Metrics Journal",
            "Invalid Quartile",
        ],
        "Print-ISSN": ["1234-5678", "2345-6789", "3456-7890", "4567-8901", "5678-9012"],
        "E-ISSN": ["8765-4321", "", "7654-3210", "", ""],
        "CiteScore": ["15.2", "5.8", "1.3", "", "abc"],
        "Percentile": ["98", "72", "35", "", "invalid"],
        "CiteScore Quartile": ["Q1", "Q2", "Q3", "", "X5"],
    }
    df = pd.DataFrame(data)
    path = tmp_path / "scopus_citescore.xlsx"
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def scopus_xlsx_empty(tmp_path: Path) -> Path:
    """XLSX sintético vazio (apenas cabeçalho)."""
    data = {"Source Title": [], "ISSN": [], "EISSN": []}
    df = pd.DataFrame(data)
    path = tmp_path / "scopus_empty.xlsx"
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def scopus_xlsx_no_issn_columns(tmp_path: Path) -> Path:
    """XLSX sem nenhuma coluna de ISSN."""
    data = {"Title": ["Journal A"], "Publisher": ["Publisher X"]}
    df = pd.DataFrame(data)
    path = tmp_path / "scopus_no_issn.xlsx"
    df.to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Testes de _format_issn
# ---------------------------------------------------------------------------


class TestFormatIssn:
    def test_eight_digits_no_hyphen(self):
        assert _format_issn("12345678") == "1234-5678"

    def test_with_hyphen(self):
        assert _format_issn("1234-5678") == "1234-5678"

    def test_with_x_check_digit(self):
        assert _format_issn("1234567X") == "1234-567X"

    def test_lowercase_x(self):
        assert _format_issn("1234567x") == "1234-567X"

    def test_none(self):
        assert _format_issn(None) is None

    def test_empty_string(self):
        assert _format_issn("") is None

    def test_too_short(self):
        assert _format_issn("1234") is None

    def test_too_long(self):
        assert _format_issn("123456789") is None

    def test_non_digit_characters(self):
        assert _format_issn("ABCD1234") is None

    def test_spaces_stripped(self):
        assert _format_issn(" 12345678 ") == "1234-5678"


# ---------------------------------------------------------------------------
# Testes de propriedades do Parser
# ---------------------------------------------------------------------------


class TestParserProperties:
    def test_source_id(self, parser: Parser):
        assert parser.source_id == "scopus"

    def test_provides(self, parser: Parser):
        assert parser.provides == [
            "scopus_percentil",
            "scopus_quartil",
            "scopus_citescore",
        ]


# ---------------------------------------------------------------------------
# Testes de parse — formato Source Title List (sem CiteScore)
# ---------------------------------------------------------------------------


class TestParseBasicFormat:
    def test_parses_valid_issn(self, parser: Parser, scopus_xlsx_basic: Path):
        records = list(parser.parse(str(scopus_xlsx_basic)))
        # "No ISSN Journal" tem ISSN e EISSN vazios, então é pulo
        # Restam: "Journal of Testing" (issn+eissn), "Inactive Journal" (issn),
        #         "Only EISSN Journal" (eissn)
        assert len(records) == 3

    def test_issn_formatting(self, parser: Parser, scopus_xlsx_basic: Path):
        records = list(parser.parse(str(scopus_xlsx_basic)))
        first = records[0]
        assert first.issn == "1234-5678"
        assert first.issn_alt == "8765-4321"

    def test_title_extracted(self, parser: Parser, scopus_xlsx_basic: Path):
        records = list(parser.parse(str(scopus_xlsx_basic)))
        assert records[0].titulo == "Journal of Testing"

    def test_no_metrics_when_columns_absent(
        self, parser: Parser, scopus_xlsx_basic: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_basic)))
        for rec in records:
            assert rec.metricas == {}

    def test_only_eissn(self, parser: Parser, scopus_xlsx_basic: Path):
        records = list(parser.parse(str(scopus_xlsx_basic)))
        # "Only EISSN Journal" has no ISSN, only EISSN
        only_eissn = records[2]
        assert only_eissn.issn is None
        assert only_eissn.issn_alt == "2345-6789"

    def test_doi_always_none(self, parser: Parser, scopus_xlsx_basic: Path):
        records = list(parser.parse(str(scopus_xlsx_basic)))
        for rec in records:
            assert rec.doi is None


# ---------------------------------------------------------------------------
# Testes de parse — formato com CiteScore
# ---------------------------------------------------------------------------


class TestParseCiteScoreFormat:
    def test_parses_all_valid_rows(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        assert len(records) == 5

    def test_citescore_extracted(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        top = records[0]
        assert top.metricas["scopus_citescore"] == 15.2

    def test_percentile_extracted(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        top = records[0]
        assert top.metricas["scopus_percentil"] == 98.0

    def test_quartile_extracted(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        top = records[0]
        assert top.metricas["scopus_quartil"] == "Q1"

    def test_missing_metrics_skipped(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        # "No Metrics Journal" — empty metrics fields
        no_metrics = records[3]
        assert no_metrics.metricas == {}

    def test_invalid_metrics_skipped(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        # "Invalid Quartile" — invalid quartile "X5" and non-numeric values
        invalid = records[4]
        assert "scopus_quartil" not in invalid.metricas
        assert "scopus_percentil" not in invalid.metricas
        assert "scopus_citescore" not in invalid.metricas

    def test_issn_with_hyphen(
        self, parser: Parser, scopus_xlsx_with_citescore: Path
    ):
        records = list(parser.parse(str(scopus_xlsx_with_citescore)))
        # "Print-ISSN" column already has hyphens
        assert records[0].issn == "1234-5678"
        assert records[0].issn_alt == "8765-4321"


# ---------------------------------------------------------------------------
# Testes de borda
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_file(self, parser: Parser, scopus_xlsx_empty: Path):
        records = list(parser.parse(str(scopus_xlsx_empty)))
        assert records == []

    def test_file_not_found(self, parser: Parser, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            list(parser.parse(str(tmp_path / "nonexistent.xlsx")))

    def test_no_issn_columns_raises(
        self, parser: Parser, scopus_xlsx_no_issn_columns: Path
    ):
        with pytest.raises(ValueError, match="Nenhuma coluna de ISSN"):
            list(parser.parse(str(scopus_xlsx_no_issn_columns)))
