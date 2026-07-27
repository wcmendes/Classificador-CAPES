"""Testes unitários para pipeline/issn.py.

Valida as quatro funções de normalização e validação de ISSN:
- normalize_issn
- validate_check_digit
- resolve_issn_l
- normalize_title
"""

import pytest

from pipeline.issn import (
    normalize_issn,
    normalize_title,
    resolve_issn_l,
    validate_check_digit,
)


# ---------------------------------------------------------------------------
# validate_check_digit
# ---------------------------------------------------------------------------


class TestValidateCheckDigit:
    """Testes para validação do dígito verificador ISSN (mod 11)."""

    def test_valid_issn_numeric_check(self) -> None:
        """ISSN com dígito verificador numérico válido."""
        assert validate_check_digit("0317-8471") is True

    def test_valid_issn_x_check(self) -> None:
        """ISSN com dígito verificador X (equivale a 10)."""
        assert validate_check_digit("0020-000X") is True

    def test_valid_issn_lowercase_x(self) -> None:
        """ISSN com 'x' minúsculo também é aceito."""
        assert validate_check_digit("0020-000x") is True

    def test_invalid_check_digit(self) -> None:
        """ISSN com dígito verificador incorreto."""
        assert validate_check_digit("1234-5678") is False

    def test_valid_without_hyphen(self) -> None:
        """ISSN sem hífen é aceito pela validação."""
        assert validate_check_digit("03178471") is True

    def test_too_short(self) -> None:
        """ISSN com menos de 8 caracteres."""
        assert validate_check_digit("1234") is False

    def test_too_long(self) -> None:
        """ISSN com mais de 8 caracteres (excluindo hífen)."""
        assert validate_check_digit("1234-56789") is False

    def test_non_digit_in_body(self) -> None:
        """ISSN com caractere não-numérico no corpo."""
        assert validate_check_digit("012A-4567") is False

    def test_check_digit_zero(self) -> None:
        """ISSN onde o dígito verificador é 0 (remainder == 0)."""
        # 0000-0000: sum = 8*0+7*0+...+2*0 = 0, remainder=0, check=0
        assert validate_check_digit("0000-0000") is True


# ---------------------------------------------------------------------------
# normalize_issn
# ---------------------------------------------------------------------------


class TestNormalizeIssn:
    """Testes para normalização de ISSN."""

    def test_already_formatted(self) -> None:
        """ISSN já no formato correto."""
        assert normalize_issn("0317-8471") == "0317-8471"

    def test_without_hyphen(self) -> None:
        """ISSN sem hífen é normalizado."""
        assert normalize_issn("03178471") == "0317-8471"

    def test_with_spaces(self) -> None:
        """ISSN com espaços extras."""
        assert normalize_issn("  0317 8471  ") == "0317-8471"

    def test_x_check_digit_uppercase(self) -> None:
        """ISSN com X maiúsculo no check digit."""
        assert normalize_issn("0020-000X") == "0020-000X"

    def test_x_check_digit_lowercase(self) -> None:
        """ISSN com x minúsculo é normalizado para X maiúsculo."""
        assert normalize_issn("0020-000x") == "0020-000X"

    def test_invalid_check_digit_returns_none(self) -> None:
        """ISSN com dígito verificador incorreto retorna None."""
        assert normalize_issn("1234-5678") is None

    def test_too_short_returns_none(self) -> None:
        """ISSN muito curto retorna None."""
        assert normalize_issn("1234") is None

    def test_too_long_returns_none(self) -> None:
        """ISSN muito longo retorna None."""
        assert normalize_issn("1234-56789") is None

    def test_empty_returns_none(self) -> None:
        """String vazia retorna None."""
        assert normalize_issn("") is None

    def test_non_digit_returns_none(self) -> None:
        """Caracteres não numéricos no corpo retorna None."""
        assert normalize_issn("ABCD-EFGH") is None


# ---------------------------------------------------------------------------
# resolve_issn_l
# ---------------------------------------------------------------------------


class TestResolveIssnL:
    """Testes para resolução ISSN → ISSN-L."""

    def test_found_in_table(self) -> None:
        """ISSN encontrado na tabela retorna ISSN-L correspondente."""
        table = {"1557-7317": "0001-0782", "0001-0782": "0001-0782"}
        assert resolve_issn_l("1557-7317", table) == "0001-0782"

    def test_not_found_returns_self(self) -> None:
        """ISSN não encontrado retorna o próprio ISSN como fallback."""
        table = {"1557-7317": "0001-0782"}
        assert resolve_issn_l("9999-9994", table) == "9999-9994"

    def test_empty_table(self) -> None:
        """Tabela vazia sempre retorna o próprio ISSN."""
        assert resolve_issn_l("0317-8471", {}) == "0317-8471"

    def test_issn_l_maps_to_self(self) -> None:
        """ISSN-L mapeia para si mesmo na tabela."""
        table = {"0001-0782": "0001-0782"}
        assert resolve_issn_l("0001-0782", table) == "0001-0782"


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------


class TestNormalizeTitle:
    """Testes para normalização de título."""

    def test_lowercase(self) -> None:
        """Converte para minúsculas."""
        assert normalize_title("HELLO WORLD") == "hello world"

    def test_remove_accents(self) -> None:
        """Remove acentos via NFD + strip combining."""
        assert normalize_title("Ciência") == "ciencia"

    def test_remove_punctuation(self) -> None:
        """Remove pontuação mantendo alfanuméricos e espaços."""
        assert normalize_title("Hello, World!") == "hello world"

    def test_collapse_spaces(self) -> None:
        """Colapsa múltiplos espaços em um só."""
        assert normalize_title("hello   world") == "hello world"

    def test_strip_edges(self) -> None:
        """Remove espaços nas bordas."""
        assert normalize_title("  hello  ") == "hello"

    def test_complex_title(self) -> None:
        """Título complexo com acentos, pontuação e espaços."""
        result = normalize_title("São Paulo: Análise & Discussão")
        assert result == "sao paulo analise discussao"

    def test_empty_string(self) -> None:
        """String vazia retorna string vazia."""
        assert normalize_title("") == ""

    def test_numbers_preserved(self) -> None:
        """Números são preservados."""
        assert normalize_title("Volume 42 - Issue 3") == "volume 42 issue 3"

    def test_mixed_unicode(self) -> None:
        """Caracteres unicode variados são normalizados."""
        result = normalize_title("Réseaux & Télécommunications")
        assert result == "reseaux telecommunications"
