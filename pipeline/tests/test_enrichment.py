"""Testes para pipeline/enrichment.py — enriquecimento por DOI e título."""

from unittest.mock import MagicMock, patch

import requests

from pipeline.enrichment import enrich_by_doi, enrich_by_title


class TestEnrichByDoi:
    """Testes para enrich_by_doi com mocks de HTTP."""

    @patch("pipeline.enrichment.requests.get")
    def test_crossref_returns_issn(self, mock_get):
        """Crossref retorna ISSN com sucesso na primeira tentativa."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "ISSN": ["0001-0782", "1557-7317"],
                "title": ["Communications of the ACM"],
            }
        }
        mock_get.return_value = mock_response

        result = enrich_by_doi("10.1145/1234567")

        assert result == "0001-0782"
        mock_get.assert_called_once_with(
            "https://api.crossref.org/works/10.1145/1234567",
            timeout=10.0,
        )

    @patch("pipeline.enrichment.requests.get")
    def test_crossref_404_falls_back_to_openalex(self, mock_get):
        """Crossref 404 → fallback para OpenAlex que retorna ISSN."""
        crossref_response = MagicMock()
        crossref_response.status_code = 404

        openalex_response = MagicMock()
        openalex_response.status_code = 200
        openalex_response.json.return_value = {
            "primary_location": {
                "source": {
                    "issn": ["2345-6789"],
                    "display_name": "Some Journal",
                }
            }
        }

        mock_get.side_effect = [crossref_response, openalex_response]

        result = enrich_by_doi("10.1000/xyz123")

        assert result == "2345-6789"
        assert mock_get.call_count == 2

    @patch("pipeline.enrichment.requests.get")
    def test_crossref_no_issn_field_falls_back_to_openalex(self, mock_get):
        """Crossref retorna 200 mas sem campo ISSN → fallback para OpenAlex."""
        crossref_response = MagicMock()
        crossref_response.status_code = 200
        crossref_response.json.return_value = {
            "message": {"title": ["Some Article"], "DOI": "10.1000/xyz"}
        }

        openalex_response = MagicMock()
        openalex_response.status_code = 200
        openalex_response.json.return_value = {
            "primary_location": {
                "source": {
                    "issn": ["1111-2222"],
                }
            }
        }

        mock_get.side_effect = [crossref_response, openalex_response]

        result = enrich_by_doi("10.1000/xyz")
        assert result == "1111-2222"

    @patch("pipeline.enrichment.requests.get")
    def test_both_services_fail_returns_none(self, mock_get):
        """Ambos Crossref e OpenAlex falham → retorna None."""
        crossref_response = MagicMock()
        crossref_response.status_code = 404

        openalex_response = MagicMock()
        openalex_response.status_code = 404

        mock_get.side_effect = [crossref_response, openalex_response]

        result = enrich_by_doi("10.9999/nonexistent")
        assert result is None

    @patch("pipeline.enrichment.requests.get")
    def test_crossref_timeout_retries(self, mock_get):
        """Timeout no Crossref causa retry até max_retries."""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        result = enrich_by_doi("10.1145/1234567", timeout=10.0, max_retries=3)

        assert result is None
        # 3 retries Crossref + 3 retries OpenAlex = 6 calls
        assert mock_get.call_count == 6

    @patch("pipeline.enrichment.requests.get")
    def test_crossref_timeout_then_openalex_success(self, mock_get):
        """Crossref timeout em todas as tentativas, OpenAlex resolve."""
        openalex_response = MagicMock()
        openalex_response.status_code = 200
        openalex_response.json.return_value = {
            "primary_location": {
                "source": {"issn": ["9999-0000"]}
            }
        }

        # 3 timeouts for Crossref, then OpenAlex success
        mock_get.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.Timeout("Timeout"),
            openalex_response,
        ]

        result = enrich_by_doi("10.1145/1234567", max_retries=3)
        assert result == "9999-0000"

    @patch("pipeline.enrichment.requests.get")
    def test_custom_timeout_and_retries(self, mock_get):
        """Parâmetros customizados de timeout e max_retries são respeitados."""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        result = enrich_by_doi("10.1145/test", timeout=5.0, max_retries=2)

        assert result is None
        # 2 retries Crossref + 2 retries OpenAlex = 4 calls
        assert mock_get.call_count == 4
        # Verify timeout parameter was passed
        for call in mock_get.call_args_list:
            assert call.kwargs["timeout"] == 5.0

    @patch("pipeline.enrichment.requests.get")
    def test_crossref_server_error_retries(self, mock_get):
        """Erro 500 no Crossref causa retry."""
        error_response = MagicMock()
        error_response.status_code = 500

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "message": {"ISSN": ["3333-4444"]}
        }

        mock_get.side_effect = [error_response, success_response]

        result = enrich_by_doi("10.1145/retry", max_retries=3)
        assert result == "3333-4444"

    @patch("pipeline.enrichment.requests.get")
    def test_openalex_no_primary_location(self, mock_get):
        """OpenAlex retorna 200 mas sem primary_location → None."""
        crossref_response = MagicMock()
        crossref_response.status_code = 404

        openalex_response = MagicMock()
        openalex_response.status_code = 200
        openalex_response.json.return_value = {
            "id": "W123",
            "primary_location": None,
        }

        mock_get.side_effect = [crossref_response, openalex_response]

        result = enrich_by_doi("10.1000/no-source")
        assert result is None

    @patch("pipeline.enrichment.requests.get")
    def test_network_error_retries(self, mock_get):
        """ConnectionError causa retry."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        result = enrich_by_doi("10.1145/network-fail", max_retries=2)
        assert result is None
        # 2 retries Crossref + 2 retries OpenAlex = 4 calls
        assert mock_get.call_count == 4


class TestEnrichByTitle:
    """Testes para enrich_by_title."""

    def test_exact_match(self):
        """Título normalizado encontra correspondência exata."""
        vehicles = {
            "communications of the acm": "0001-0782",
            "journal of machine learning research": "1532-4435",
        }
        result = enrich_by_title("Communications of the ACM", vehicles)
        assert result == "0001-0782"

    def test_title_with_accents(self):
        """Título com acentos é normalizado antes da busca."""
        vehicles = {
            "revista brasileira de ciencias sociais": "0102-6909",
        }
        result = enrich_by_title("Revista Brasileira de Ciências Sociais", vehicles)
        assert result == "0102-6909"

    def test_title_with_punctuation(self):
        """Título com pontuação é normalizado antes da busca."""
        vehicles = {
            "plos one": "1932-6203",
        }
        result = enrich_by_title("PLoS ONE!", vehicles)
        assert result == "1932-6203"

    def test_title_not_found(self):
        """Título sem correspondência retorna None."""
        vehicles = {
            "communications of the acm": "0001-0782",
        }
        result = enrich_by_title("Journal of Nothing", vehicles)
        assert result is None

    def test_empty_title(self):
        """Título vazio retorna None."""
        vehicles = {"some journal": "1234-5678"}
        result = enrich_by_title("", vehicles)
        assert result is None

    def test_whitespace_title(self):
        """Título apenas com espaços retorna None."""
        vehicles = {"some journal": "1234-5678"}
        result = enrich_by_title("   ", vehicles)
        assert result is None

    def test_empty_vehicles_dict(self):
        """Dicionário de veículos vazio retorna None."""
        result = enrich_by_title("Any Journal", {})
        assert result is None

    def test_title_with_extra_spaces(self):
        """Título com espaços extras é normalizado."""
        vehicles = {
            "journal of artificial intelligence": "0000-1111",
        }
        result = enrich_by_title("Journal   of   Artificial   Intelligence", vehicles)
        assert result == "0000-1111"
