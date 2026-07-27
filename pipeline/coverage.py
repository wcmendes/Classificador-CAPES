"""Relatório de cobertura por fonte.

Implementa:
- CoverageReport: dataclass com contagens por fonte e itens não-resolvidos
- generate_coverage_report: gera relatório a partir do processamento de fontes
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UnresolvedItem:
    """Item que não pôde ser resolvido durante o processamento."""

    fonte: str
    """Identificador da fonte de origem."""

    identificador_original: str
    """Identificador tentado (ISSN, DOI ou título)."""

    estrategia_falha: str
    """Estratégia que falhou: 'issn', 'doi', 'titulo' ou combinação."""

    motivo: str
    """Razão detalhada da falha (ex: 'ISSN ausente', 'DOI não encontrado no Crossref')."""


@dataclass
class SourceCoverage:
    """Contagens de cobertura para uma fonte individual."""

    fonte_id: str
    processados: int = 0
    resolvidos: int = 0
    nao_resolvidos: int = 0


@dataclass
class CoverageReport:
    """Relatório completo de cobertura do processamento do pipeline."""

    por_fonte: dict[str, SourceCoverage] = field(default_factory=dict)
    """Contagens por fonte (chave = fonte_id)."""

    nao_resolvidos: list[UnresolvedItem] = field(default_factory=list)
    """Lista de todos os itens não-resolvidos com motivos detalhados."""

    @property
    def total_processados(self) -> int:
        """Total de registros processados em todas as fontes."""
        return sum(sc.processados for sc in self.por_fonte.values())

    @property
    def total_resolvidos(self) -> int:
        """Total de registros resolvidos em todas as fontes."""
        return sum(sc.resolvidos for sc in self.por_fonte.values())

    @property
    def total_nao_resolvidos(self) -> int:
        """Total de registros não-resolvidos em todas as fontes."""
        return sum(sc.nao_resolvidos for sc in self.por_fonte.values())


def generate_coverage_report(
    sources_processed: dict[str, dict],
) -> CoverageReport:
    """Gera relatório de cobertura a partir dos resultados do processamento.

    Args:
        sources_processed: Dicionário onde cada chave é o fonte_id e o valor
            contém:
            - "processados": int — total de registros processados
            - "resolvidos": int — total de registros resolvidos
            - "nao_resolvidos": list[dict] — lista de itens não-resolvidos,
              cada um com campos: "identificador_original", "estrategia_falha", "motivo"

    Returns:
        CoverageReport com contagens por fonte e lista consolidada de
        itens não-resolvidos.

    Invariante: para cada fonte, processados == resolvidos + nao_resolvidos.
    """
    report = CoverageReport()

    for fonte_id, dados in sources_processed.items():
        processados = dados.get("processados", 0)
        resolvidos = dados.get("resolvidos", 0)
        itens_nao_resolvidos = dados.get("nao_resolvidos", [])

        report.por_fonte[fonte_id] = SourceCoverage(
            fonte_id=fonte_id,
            processados=processados,
            resolvidos=resolvidos,
            nao_resolvidos=len(itens_nao_resolvidos),
        )

        for item in itens_nao_resolvidos:
            report.nao_resolvidos.append(
                UnresolvedItem(
                    fonte=fonte_id,
                    identificador_original=item.get("identificador_original", ""),
                    estrategia_falha=item.get("estrategia_falha", ""),
                    motivo=item.get("motivo", ""),
                )
            )

    return report
