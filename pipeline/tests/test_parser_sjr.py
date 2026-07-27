"""Testes unitários para o parser SJR."""

import textwrap
from pathlib import Path

import pytest

from pipeline.parsers.base import ParsedRecord, SourceParser
from pipeline.parsers.parser_sjr import Parser


@pytest.fixture
def sjr_csv(tmp_path: Path) -> Path:
    """Cria um CSV sintético no formato SciMago."""
    content = textwrap.dedent("""\
        Rank;Sourceid;Title;Type;Issn;Publisher;Open Access;Open Access Diamond;SJR;SJR Best Quartile;H index;Total Docs. (2025);Total Docs. (3years);Total Refs.;Total Citations (3years);Citable Docs. (3years);Citations / Doc. (2years);Ref. / Doc.;%Female;Overton;Country;Region;Publisher;Coverage;Categories;Areas
        1;28773;"Ca-A Cancer Journal for Clinicians";journal;"15424863, 00079235";"John Wiley and Sons Inc";No;No;104,065;Q1;236;48;127;4331;29333;76;285,55;90,23;46,34;2;United States;Northern America;"John Wiley and Sons Inc";"1950-2026";"Hematology (Q1); Oncology (Q1)";"Medicine"
        2;20315;"Nature Reviews Molecular Cell Biology";journal;"14710072, 14710080";"Nature Research";No;No;35,568;Q1;553;122;350;12007;16938;176;45,22;98,42;34,87;0;United Kingdom;Western Europe;"Nature Research";"2000-2026";"Cell Biology (Q1); Molecular Biology (Q1)";"Biochemistry, Genetics and Molecular Biology"
        3;99999;"Single ISSN Journal";journal;"12345678";"Test Publisher";No;No;1,234;Q3;10;5;15;100;50;10;3,00;20,00;50,00;0;Brazil;Latin America;"Test Publisher";"2010-2026";"General (Q3)";"General"
        4;88888;"No SJR Value";journal;"87654321, 11112222";"Test Publisher";No;No;;Q4;5;2;8;50;20;5;2,00;25,00;40,00;0;Brazil;Latin America;"Test Publisher";"2015-2026";"General (Q4)";"General"
    """)
    csv_path = tmp_path / "sjr_test.csv"
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


class TestParserInterface:
    """Verifica que o parser cumpre a interface SourceParser."""

    def test_source_id(self):
        parser = Parser()
        assert parser.source_id == "sjr"

    def test_provides(self):
        parser = Parser()
        assert parser.provides == ["sjr_quartil", "sjr_valor"]

    def test_implements_protocol(self):
        """Verifica conformidade com SourceParser Protocol."""
        parser = Parser()
        # Checagem estrutural — se as propriedades e método existem
        assert hasattr(parser, "source_id")
        assert hasattr(parser, "provides")
        assert hasattr(parser, "parse")


class TestIssnExtraction:
    """Verifica extração de ISSN do campo multi-ISSN."""

    def test_multi_issn_extracts_both(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        # Primeiro registro: "15424863, 00079235"
        rec = records[0]
        assert rec.issn == "15424863"
        assert rec.issn_alt == "00079235"

    def test_single_issn_no_alt(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        # Terceiro registro: "12345678" (único)
        rec = records[2]
        assert rec.issn == "12345678"
        assert rec.issn_alt is None

    def test_second_record_issns(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        rec = records[1]
        assert rec.issn == "14710072"
        assert rec.issn_alt == "14710080"


class TestQuartileMapping:
    """Verifica extração de quartil."""

    def test_q1_extracted(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        assert records[0].metricas["sjr_quartil"] == "Q1"

    def test_q3_extracted(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        assert records[2].metricas["sjr_quartil"] == "Q3"

    def test_q4_extracted(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        assert records[3].metricas["sjr_quartil"] == "Q4"


class TestSjrValueConversion:
    """Verifica conversão de vírgula decimal para float."""

    def test_large_value_comma_decimal(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        # "104,065" → 104.065
        assert records[0].metricas["sjr_valor"] == pytest.approx(104.065)

    def test_normal_value_comma_decimal(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        # "35,568" → 35.568
        assert records[1].metricas["sjr_valor"] == pytest.approx(35.568)

    def test_small_value_comma_decimal(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        # "1,234" → 1.234
        assert records[2].metricas["sjr_valor"] == pytest.approx(1.234)

    def test_empty_sjr_value_not_in_metricas(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        # Quarto registro tem SJR vazio
        assert "sjr_valor" not in records[3].metricas


class TestParsedRecordType:
    """Verifica que o parser produz instâncias de ParsedRecord."""

    def test_yields_parsed_record_instances(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        assert len(records) == 4
        for rec in records:
            assert isinstance(rec, ParsedRecord)

    def test_titulo_extracted(self, sjr_csv: Path):
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        assert records[0].titulo == "Ca-A Cancer Journal for Clinicians"
        assert records[1].titulo == "Nature Reviews Molecular Cell Biology"

    def test_doi_is_none(self, sjr_csv: Path):
        """SJR não fornece DOI."""
        parser = Parser()
        records = list(parser.parse(str(sjr_csv)))
        for rec in records:
            assert rec.doi is None


class TestDecimalParser:
    """Testes unitários diretos do método _parse_decimal."""

    def test_comma_to_float(self):
        assert Parser._parse_decimal("3,14") == pytest.approx(3.14)

    def test_integer_value(self):
        assert Parser._parse_decimal("42") == pytest.approx(42.0)

    def test_empty_string_returns_none(self):
        assert Parser._parse_decimal("") is None

    def test_invalid_returns_none(self):
        assert Parser._parse_decimal("abc") is None

    def test_zero(self):
        assert Parser._parse_decimal("0,000") == pytest.approx(0.0)
