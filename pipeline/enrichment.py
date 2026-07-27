"""Enriquecimento de registros via DOI (Crossref/OpenAlex) e título.

Implementa:
- enrich_by_doi: busca ISSN via Crossref com fallback para OpenAlex
- enrich_by_title: busca por título normalizado contra veículos conhecidos
- UnresolvedReason: motivo detalhado de falha de resolução
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from pipeline.issn import normalize_title

logger = logging.getLogger(__name__)

# Constantes de API
CROSSREF_API_URL = "https://api.crossref.org/works"
OPENALEX_API_URL = "https://api.openalex.org/works/doi"


@dataclass
class UnresolvedReason:
    """Motivo detalhado de falha de resolução."""

    estrategia: str
    """Estratégia tentada: 'doi_crossref', 'doi_openalex', 'titulo'."""

    motivo: str
    """Descrição da falha."""


def enrich_by_doi(
    doi: str,
    timeout: float = 10.0,
    max_retries: int = 3,
) -> str | None:
    """Busca ISSN de um veículo via DOI usando Crossref com fallback para OpenAlex.

    Tenta primeiro o Crossref. Se falha (timeout, erro HTTP, ISSN ausente),
    tenta OpenAlex como fallback. Cada serviço é tentado até max_retries vezes.

    Args:
        doi: DOI do artigo (ex: "10.1145/1234567").
        timeout: Timeout em segundos por requisição (padrão: 10s).
        max_retries: Número máximo de tentativas por serviço (padrão: 3).

    Returns:
        ISSN encontrado (formato bruto da API) ou None se não resolvido.
    """
    # Tentar Crossref primeiro
    issn = _try_crossref(doi, timeout=timeout, max_retries=max_retries)
    if issn is not None:
        return issn

    # Fallback: OpenAlex
    issn = _try_openalex(doi, timeout=timeout, max_retries=max_retries)
    return issn


def _try_crossref(doi: str, timeout: float, max_retries: int) -> str | None:
    """Tenta buscar ISSN via Crossref API.

    Endpoint: GET https://api.crossref.org/works/{doi}
    Retorna o primeiro ISSN do campo 'ISSN' da resposta, se disponível.
    """
    url = f"{CROSSREF_API_URL}/{doi}"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                message = data.get("message", {})
                issns = message.get("ISSN", [])
                if issns:
                    return issns[0]
                # Resposta OK mas sem ISSN
                logger.debug(
                    "Crossref retornou resposta sem ISSN para DOI %s", doi
                )
                return None
            elif response.status_code == 404:
                # DOI não encontrado no Crossref
                logger.debug("DOI %s não encontrado no Crossref", doi)
                return None
            else:
                logger.warning(
                    "Crossref retornou status %d para DOI %s (tentativa %d/%d)",
                    response.status_code,
                    doi,
                    attempt + 1,
                    max_retries,
                )
        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout ao consultar Crossref para DOI %s (tentativa %d/%d)",
                doi,
                attempt + 1,
                max_retries,
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Erro de rede ao consultar Crossref para DOI %s: %s (tentativa %d/%d)",
                doi,
                e,
                attempt + 1,
                max_retries,
            )

    return None


def _try_openalex(doi: str, timeout: float, max_retries: int) -> str | None:
    """Tenta buscar ISSN via OpenAlex API.

    Endpoint: GET https://api.openalex.org/works/doi:{doi}
    Retorna o primeiro ISSN do campo 'primary_location.source.issn', se disponível.
    """
    url = f"{OPENALEX_API_URL}:{doi}"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                # OpenAlex retorna primary_location.source.issn como lista
                location = data.get("primary_location") or {}
                source = location.get("source") or {}
                issns = source.get("issn") or []
                if issns:
                    return issns[0]
                # Resposta OK mas sem ISSN
                logger.debug(
                    "OpenAlex retornou resposta sem ISSN para DOI %s", doi
                )
                return None
            elif response.status_code == 404:
                logger.debug("DOI %s não encontrado no OpenAlex", doi)
                return None
            else:
                logger.warning(
                    "OpenAlex retornou status %d para DOI %s (tentativa %d/%d)",
                    response.status_code,
                    doi,
                    attempt + 1,
                    max_retries,
                )
        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout ao consultar OpenAlex para DOI %s (tentativa %d/%d)",
                doi,
                attempt + 1,
                max_retries,
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Erro de rede ao consultar OpenAlex para DOI %s: %s (tentativa %d/%d)",
                doi,
                e,
                attempt + 1,
                max_retries,
            )

    return None


def enrich_by_title(title: str, vehicles: dict[str, str]) -> str | None:
    """Busca ISSN por título normalizado contra veículos conhecidos.

    Normaliza o título fornecido e compara contra o dicionário de veículos
    (título normalizado → ISSN-L).

    Args:
        title: Título do veículo a buscar.
        vehicles: Dicionário mapeando título normalizado → ISSN-L.

    Returns:
        ISSN-L do veículo encontrado ou None se sem correspondência.
    """
    if not title or not title.strip():
        return None

    normalized = normalize_title(title)
    if not normalized:
        return None

    return vehicles.get(normalized)
