"""Testes para pipeline/coverage.py — relatório de cobertura por fonte."""

from pipeline.coverage import (
    CoverageReport,
    SourceCoverage,
    UnresolvedItem,
    generate_coverage_report,
)


class TestCoverageReport:
    """Testes para a dataclass CoverageReport e propriedades."""

    def test_empty_report(self):
        """Relatório vazio tem todos os totais zerados."""
        report = CoverageReport()
        assert report.total_processados == 0
        assert report.total_resolvidos == 0
        assert report.total_nao_resolvidos == 0
        assert report.nao_resolvidos == []

    def test_totals_sum_across_sources(self):
        """Totais são a soma de todas as fontes."""
        report = CoverageReport(
            por_fonte={
                "sjr": SourceCoverage(fonte_id="sjr", processados=100, resolvidos=90, nao_resolvidos=10),
                "scopus": SourceCoverage(fonte_id="scopus", processados=200, resolvidos=180, nao_resolvidos=20),
            }
        )
        assert report.total_processados == 300
        assert report.total_resolvidos == 270
        assert report.total_nao_resolvidos == 30


class TestGenerateCoverageReport:
    """Testes para generate_coverage_report."""

    def test_single_source_all_resolved(self):
        """Fonte com todos os registros resolvidos."""
        data = {
            "sjr": {
                "processados": 50,
                "resolvidos": 50,
                "nao_resolvidos": [],
            }
        }
        report = generate_coverage_report(data)

        assert "sjr" in report.por_fonte
        assert report.por_fonte["sjr"].processados == 50
        assert report.por_fonte["sjr"].resolvidos == 50
        assert report.por_fonte["sjr"].nao_resolvidos == 0
        assert report.nao_resolvidos == []

    def test_single_source_with_unresolved(self):
        """Fonte com itens não-resolvidos registra motivos detalhados."""
        data = {
            "abdc": {
                "processados": 100,
                "resolvidos": 95,
                "nao_resolvidos": [
                    {
                        "identificador_original": "10.9999/fake",
                        "estrategia_falha": "doi",
                        "motivo": "DOI não encontrado no Crossref nem OpenAlex",
                    },
                    {
                        "identificador_original": "Journal of Nothing",
                        "estrategia_falha": "titulo",
                        "motivo": "Título sem correspondência na tabela de veículos",
                    },
                ],
            }
        }
        report = generate_coverage_report(data)

        assert report.por_fonte["abdc"].processados == 100
        assert report.por_fonte["abdc"].resolvidos == 95
        assert report.por_fonte["abdc"].nao_resolvidos == 2
        assert len(report.nao_resolvidos) == 2
        assert report.nao_resolvidos[0].fonte == "abdc"
        assert report.nao_resolvidos[0].identificador_original == "10.9999/fake"
        assert report.nao_resolvidos[0].estrategia_falha == "doi"
        assert "Crossref" in report.nao_resolvidos[0].motivo

    def test_multiple_sources(self):
        """Múltiplas fontes são consolidadas corretamente."""
        data = {
            "sjr": {
                "processados": 30000,
                "resolvidos": 29500,
                "nao_resolvidos": [
                    {
                        "identificador_original": "0000-0000",
                        "estrategia_falha": "issn",
                        "motivo": "ISSN inválido (dígito verificador incorreto)",
                    },
                ],
            },
            "scopus": {
                "processados": 28000,
                "resolvidos": 28000,
                "nao_resolvidos": [],
            },
        }
        report = generate_coverage_report(data)

        assert report.total_processados == 58000
        assert report.total_resolvidos == 57500
        assert report.total_nao_resolvidos == 1
        assert len(report.nao_resolvidos) == 1

    def test_invariant_processados_equals_resolvidos_plus_nao_resolvidos(self):
        """Invariante: processados == resolvidos + nao_resolvidos por fonte."""
        data = {
            "spell": {
                "processados": 200,
                "resolvidos": 180,
                "nao_resolvidos": [
                    {"identificador_original": f"item_{i}", "estrategia_falha": "issn", "motivo": "ausente"}
                    for i in range(20)
                ],
            }
        }
        report = generate_coverage_report(data)

        for fonte_id, sc in report.por_fonte.items():
            assert sc.processados == sc.resolvidos + sc.nao_resolvidos, (
                f"Invariante violada para fonte '{fonte_id}': "
                f"{sc.processados} != {sc.resolvidos} + {sc.nao_resolvidos}"
            )

    def test_empty_sources(self):
        """Nenhuma fonte processada gera relatório vazio."""
        report = generate_coverage_report({})
        assert report.total_processados == 0
        assert report.total_resolvidos == 0
        assert report.total_nao_resolvidos == 0
