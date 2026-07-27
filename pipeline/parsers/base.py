"""Interface base para parsers de fontes bibliométricas."""

from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass
class ParsedRecord:
    """Registro produzido por um parser.

    Cada parser extrai dados brutos de uma fonte e produz instâncias desta classe.
    A normalização de ISSN é responsabilidade do pipeline, não do parser.
    """

    issn: str | None
    """ISSN original (com ou sem hífen), como aparece na fonte."""

    issn_alt: str | None
    """ISSN alternativo (impresso/eletrônico), se disponível."""

    doi: str | None
    """DOI para enriquecimento, se disponível na fonte."""

    titulo: str | None
    """Título do veículo (fallback de resolução quando ISSN e DOI falham)."""

    metricas: dict[str, str | int | float]
    """Métricas extraídas. Chaves = nomes canônicos (ex: 'sjr_quartil').
    Valores = valor extraído da fonte, no tipo declarado pelo schema."""


class SourceParser(Protocol):
    """Interface que todo parser de fonte deve cumprir.

    Parsers são geradores (yield). Isso permite processar arquivos grandes
    sem carregar tudo em memória e facilita testes.
    """

    @property
    def source_id(self) -> str:
        """Identificador da fonte conforme sources.yml (ex: 'sjr', 'scopus')."""
        ...

    @property
    def provides(self) -> list[str]:
        """Lista de nomes canônicos de métricas que esta fonte entrega."""
        ...

    def parse(self, path: str) -> Iterator[ParsedRecord]:
        """Extrai registros do arquivo da fonte.

        Yields:
            ParsedRecord para cada veículo encontrado.

        Notes:
            - Não faz normalização de ISSN — responsabilidade do pipeline.
            - Não faz merge — apenas extrai.
        """
        ...
