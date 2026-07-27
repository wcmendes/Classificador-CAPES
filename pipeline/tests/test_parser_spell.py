"""Testes para o parser SPELL."""

import math
import tempfile
from pathlib import Path

import pytest

from pipeline.parsers.parser_spell import (
    Parser,
    _calcular_faixa,
    _parse_decimal_br,
)


# --- Fixtures: XML Spreadsheet sintético ---


def _make_spell_xml(rows: list[tuple[int, str, str]]) -> str:
    """Gera um XML Spreadsheet sintético no formato SPELL.

    Args:
        rows: lista de (posicao, titulo, impacto_5_anos_str).
              O impacto_5_anos_str usa vírgula decimal (ex: "0,84530").
    """
    header = (
        '<Row>'
        '<Cell><Data ss:Type="String"></Data></Cell>'
        '<Cell><Data ss:Type="String">Periódico</Data></Cell>'
        '<Cell><Data ss:Type="String">Impacto 5 anos s/autocitação</Data></Cell>'
        '<Cell><Data ss:Type="String">Impacto 2 anos s/autocitação</Data></Cell>'
        '<Cell><Data ss:Type="String">Impacto 5 Anos</Data></Cell>'
        '<Cell><Data ss:Type="String">Impacto 2 Anos</Data></Cell>'
        '<Cell><Data ss:Type="String">Imediatismo</Data></Cell>'
        '<Cell><Data ss:Type="String">Taxa de Autocitação (%)</Data></Cell>'
        '<Cell><Data ss:Type="String">Meia Vida</Data></Cell>'
        '<Cell><Data ss:Type="String">Ref./Doc.</Data></Cell>'
        '</Row>'
    )

    data_rows = []
    for pos, titulo, impacto in rows:
        data_rows.append(
            f'<Row>'
            f'<Cell><Data ss:Type="Number">{pos}</Data></Cell>'
            f'<Cell><Data ss:Type="String">{titulo}</Data></Cell>'
            f'<Cell><Data ss:Type="String">0,50000</Data></Cell>'
            f'<Cell><Data ss:Type="String">0,40000</Data></Cell>'
            f'<Cell><Data ss:Type="String">{impacto}</Data></Cell>'
            f'<Cell><Data ss:Type="String">0,30000</Data></Cell>'
            f'<Cell><Data ss:Type="String">0,01000</Data></Cell>'
            f'<Cell><Data ss:Type="String">5,00%</Data></Cell>'
            f'<Cell><Data ss:Type="String">7 anos(s)</Data></Cell>'
            f'<Cell><Data ss:Type="String">40,00</Data></Cell>'
            f'</Row>'
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<?mso-application progid="Excel.Sheet"?>'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        '<Worksheet ss:Name="Impacto Periódicos Spell">'
        f'<Table>{header}{"".join(data_rows)}</Table>'
        '</Worksheet>'
        '</Workbook>'
    )
    return xml


@pytest.fixture
def spell_file_10(tmp_path: Path) -> Path:
    """Gera arquivo SPELL sintético com 10 periódicos."""
    rows = [
        (i, f"Revista Sintética {i}", f"{1.0 - i * 0.08:.5f}".replace(".", ","))
        for i in range(1, 11)
    ]
    path = tmp_path / "spell-test.xls"
    path.write_text(_make_spell_xml(rows), encoding="utf-8")
    return path


@pytest.fixture
def spell_file_100(tmp_path: Path) -> Path:
    """Gera arquivo SPELL sintético com 100 periódicos."""
    rows = [
        (i, f"Periódico Teste {i}", f"{2.0 - i * 0.015:.5f}".replace(".", ","))
        for i in range(1, 101)
    ]
    path = tmp_path / "spell-test-100.xls"
    path.write_text(_make_spell_xml(rows), encoding="utf-8")
    return path


# --- Testes de _calcular_faixa ---


class TestCalcularFaixa:
    """Testes para a função de cálculo de faixa."""

    def test_decil_superior_10_items(self):
        """Com 10 itens, ceil(10*0.1)=1, posição 1 é decil_superior."""
        assert _calcular_faixa(1, 10) == "decil_superior"

    def test_faixa_10_a_40_10_items(self):
        """Com 10 itens, posições 2-4 são 10_a_40."""
        assert _calcular_faixa(2, 10) == "10_a_40"
        assert _calcular_faixa(4, 10) == "10_a_40"

    def test_faixa_40_a_70_10_items(self):
        """Com 10 itens, posições 5-7 são 40_a_70."""
        assert _calcular_faixa(5, 10) == "40_a_70"
        assert _calcular_faixa(7, 10) == "40_a_70"

    def test_abaixo_70_10_items(self):
        """Com 10 itens, posições 8-10 são abaixo_70."""
        assert _calcular_faixa(8, 10) == "abaixo_70"
        assert _calcular_faixa(10, 10) == "abaixo_70"

    def test_111_items_decil_superior(self):
        """Com 111 itens (caso real SPELL), ceil(111*0.1)=12."""
        corte = math.ceil(111 * 0.10)
        assert corte == 12
        assert _calcular_faixa(1, 111) == "decil_superior"
        assert _calcular_faixa(12, 111) == "decil_superior"
        assert _calcular_faixa(13, 111) == "10_a_40"

    def test_111_items_boundaries(self):
        """Verifica limites com 111 itens."""
        # 10% = 12, 40% = 45, 70% = 78
        assert _calcular_faixa(45, 111) == "10_a_40"
        assert _calcular_faixa(46, 111) == "40_a_70"
        assert _calcular_faixa(78, 111) == "40_a_70"
        assert _calcular_faixa(79, 111) == "abaixo_70"

    def test_total_zero(self):
        """Total zero retorna abaixo_70 (fallback seguro)."""
        assert _calcular_faixa(1, 0) == "abaixo_70"

    def test_single_item(self):
        """Com 1 item, posição 1 é decil_superior."""
        assert _calcular_faixa(1, 1) == "decil_superior"


# --- Testes de _parse_decimal_br ---


class TestParseDecimalBr:
    """Testes para parsing de decimais em formato brasileiro."""

    def test_normal(self):
        assert _parse_decimal_br("0,84530") == pytest.approx(0.84530)

    def test_integer(self):
        assert _parse_decimal_br("1,00000") == pytest.approx(1.0)

    def test_zero(self):
        assert _parse_decimal_br("0,00000") == pytest.approx(0.0)

    def test_empty(self):
        assert _parse_decimal_br("") is None

    def test_whitespace(self):
        assert _parse_decimal_br("  ") is None

    def test_none_value(self):
        assert _parse_decimal_br(None) is None

    def test_with_spaces(self):
        assert _parse_decimal_br(" 0,50000 ") == pytest.approx(0.5)


# --- Testes do Parser ---


class TestParserSpell:
    """Testes para o Parser SPELL."""

    def test_source_id(self):
        parser = Parser()
        assert parser.source_id == "spell"

    def test_provides(self):
        parser = Parser()
        assert parser.provides == ["spell_faixa", "spell_fator_impacto"]

    def test_parse_yields_correct_count(self, spell_file_10: Path):
        parser = Parser()
        records = list(parser.parse(str(spell_file_10)))
        assert len(records) == 10

    def test_parse_no_issn(self, spell_file_10: Path):
        """SPELL não tem ISSN — todos os registros devem ter issn=None."""
        parser = Parser()
        records = list(parser.parse(str(spell_file_10)))
        for r in records:
            assert r.issn is None
            assert r.issn_alt is None
            assert r.doi is None

    def test_parse_titulo_present(self, spell_file_10: Path):
        parser = Parser()
        records = list(parser.parse(str(spell_file_10)))
        assert records[0].titulo == "Revista Sintética 1"
        assert records[9].titulo == "Revista Sintética 10"

    def test_parse_faixa_assignment(self, spell_file_10: Path):
        """Com 10 itens: pos 1 → decil_superior, pos 2-4 → 10_a_40, etc."""
        parser = Parser()
        records = list(parser.parse(str(spell_file_10)))
        assert records[0].metricas["spell_faixa"] == "decil_superior"
        assert records[1].metricas["spell_faixa"] == "10_a_40"
        assert records[4].metricas["spell_faixa"] == "40_a_70"
        assert records[7].metricas["spell_faixa"] == "abaixo_70"

    def test_parse_fator_impacto(self, spell_file_10: Path):
        """Verifica extração do fator de impacto."""
        parser = Parser()
        records = list(parser.parse(str(spell_file_10)))
        # Primeiro item: 1.0 - 1*0.08 = 0.92
        assert records[0].metricas["spell_fator_impacto"] == pytest.approx(0.92, abs=0.001)

    def test_parse_100_items_distribution(self, spell_file_100: Path):
        """Verifica distribuição de faixas para 100 itens."""
        parser = Parser()
        records = list(parser.parse(str(spell_file_100)))

        faixas = [r.metricas["spell_faixa"] for r in records]
        # ceil(100*0.1) = 10 → decil_superior
        assert faixas.count("decil_superior") == 10
        # ceil(100*0.4) = 40 → 40-10 = 30 in 10_a_40
        assert faixas.count("10_a_40") == 30
        # ceil(100*0.7) = 70 → 70-40 = 30 in 40_a_70
        assert faixas.count("40_a_70") == 30
        # 100-70 = 30 in abaixo_70
        assert faixas.count("abaixo_70") == 30

    def test_parse_empty_file(self, tmp_path: Path):
        """Arquivo sem linhas de dados não gera registros."""
        xml = _make_spell_xml([])
        path = tmp_path / "empty.xls"
        path.write_text(xml, encoding="utf-8")

        parser = Parser()
        records = list(parser.parse(str(path)))
        assert records == []

    def test_parse_real_file_structure(self, tmp_path: Path):
        """Testa com formato mais próximo do real (com HRef no cell)."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<?mso-application progid="Excel.Sheet"?>'
            '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
            'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
            '<Worksheet ss:Name="Impacto Periódicos Spell"><Table>'
            '<Row>'
            '<Cell><Data ss:Type="String"></Data></Cell>'
            '<Cell><Data ss:Type="String">Periódico</Data></Cell>'
            '<Cell><Data ss:Type="String">Impacto 5 anos s/autocitação</Data></Cell>'
            '<Cell><Data ss:Type="String">Impacto 2 anos s/autocitação</Data></Cell>'
            '<Cell><Data ss:Type="String">Impacto 5 Anos</Data></Cell>'
            '<Cell><Data ss:Type="String">Impacto 2 Anos</Data></Cell>'
            '<Cell><Data ss:Type="String">Imediatismo</Data></Cell>'
            '<Cell><Data ss:Type="String">Taxa de Autocitação (%)</Data></Cell>'
            '<Cell><Data ss:Type="String">Meia Vida</Data></Cell>'
            '<Cell><Data ss:Type="String">Ref./Doc.</Data></Cell>'
            '</Row>'
            '<Row>'
            '<Cell><Data ss:Type="Number">1</Data></Cell>'
            '<Cell ss:StyleID="s69" ss:HRef="https://www.spell.org.br/impacto/periodico/revista-de-administracao-contemporanea/id/11">'
            '<Data ss:Type="String">Revista de Administração Contemporânea</Data></Cell>'
            '<Cell><Data ss:Type="String">0,84530</Data></Cell>'
            '<Cell><Data ss:Type="String">0,68750</Data></Cell>'
            '<Cell><Data ss:Type="String">0,94475</Data></Cell>'
            '<Cell><Data ss:Type="String">0,82500</Data></Cell>'
            '<Cell><Data ss:Type="String">0,02703</Data></Cell>'
            '<Cell><Data ss:Type="String">6,21%</Data></Cell>'
            '<Cell><Data ss:Type="String">9 anos(s)</Data></Cell>'
            '<Cell><Data ss:Type="String">54,00</Data></Cell>'
            '</Row>'
            '</Table></Worksheet></Workbook>'
        )
        path = tmp_path / "spell-real.xls"
        path.write_text(xml, encoding="utf-8")

        parser = Parser()
        records = list(parser.parse(str(path)))
        assert len(records) == 1
        assert records[0].titulo == "Revista de Administração Contemporânea"
        assert records[0].metricas["spell_fator_impacto"] == pytest.approx(0.94475)
        assert records[0].metricas["spell_faixa"] == "decil_superior"
