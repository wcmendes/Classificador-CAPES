"""Exportação dos Anexos 3 e 4 da Área 02 em formato XLSX.

Gera planilhas com estrutura de colunas, cabeçalhos e ordenação
idênticos ao template oficial (docs/anexos-computacao.xlsx).

Requisitos implementados: 14.1–14.5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# Dataclasses de entrada
# ---------------------------------------------------------------------------

ItemType = Literal["evento", "periódico", "livro", "capítulo de livro"]


@dataclass
class AnnexItem:
    """Item de produção bibliográfica para o Anexo 3.

    Campos correspondem às colunas do template oficial.
    """

    tipo: ItemType
    issn_ou_isbn: str = ""
    sigla_evento: str = ""
    titulo: str = ""  # Literal — sem normalização (Req 14.2)
    autores_docentes: str = ""  # separados por ponto-e-vírgula
    autores_discentes: str = ""
    outros_autores: str = ""
    justificativa: str = ""
    estrato: str = ""  # Pode ser "NAO_CLASSIFICAVEL" ou "NAO_CONSIDERADO" (Req 14.5)


@dataclass
class AnnexTechItem:
    """Item de produção técnica para o Anexo 4."""

    tipo: str = ""
    titulo: str = ""  # Literal — sem normalização (Req 14.2)
    autores_docentes: str = ""
    autores_discentes: str = ""
    outros_autores: str = ""
    parceiro_institucional: str = ""
    justificativa: str = ""
    produto_bibliografico: str = ""
    estrato: str = ""


# ---------------------------------------------------------------------------
# Constantes do template oficial
# ---------------------------------------------------------------------------

_HEADER_ANNEX3 = (
    "Ministério da Educação\n"
    "Coordenação de Aperfeiçoamento de Pessoal de Nível Superior\n"
    "Diretoria de Avaliação – DAV\n"
    "Avaliação Quadrienal 2025-2028\n"
    "Área de Computação"
)

_SUBTITLE_ANNEX3 = (
    "ANEXO 3 - 4N produções bibliográficas do quadriênio consideradas "
    "mais importantes pelo programa, onde N é o número médio de "
    "professores permanentes do programa na quadrienal."
)

_HEADER_ANNEX4 = _HEADER_ANNEX3  # Same ministry header

_SUBTITLE_ANNEX4 = (
    "ANEXO 4 - M produções técnicas mais relevantes, onde M é o maior "
    "valor entre 10 e N/4, e N é o número médio de professores "
    "permanentes do programa no quadriênio."
)

_FOOTNOTE = (
    "NOTA: Itens com múltiplos autores vinculados ao mesmo programa "
    "podem requerer separação de autoria para fins de contagem individual."
)

# Column headers for Annex 3 (matching template row 5 exactly)
_COLUMNS_ANNEX3 = [
    "No.",
    "Tipo",
    "ISSN ou ISBN",
    "Sigla Evento",
    "Título do trabalho conforme inserido na Sucupira",
    "Autores docentes",
    "Autores discentes",
    "Outros autores",
    "Justificativa",
    "Estrato estimado",
    "Excede 4N",
]

# Column headers for Annex 4 (matching template row 5 exactly)
_COLUMNS_ANNEX4 = [
    "No.",
    "Tipo",
    "Título do trabalho conforme inserido na Sucupira",
    "Autores docentes",
    "Autores discentes",
    "Outros autores",
    "Parceiro Institucional",
    "Justificativa",
    "Estrato estimado",
    "Excede 4N",
    "Produto Bibliográfico",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_annex3(
    items: list[AnnexItem],
    n_docentes: int,
    output_path: str | Path,
) -> Path:
    """Gera o Anexo 3 (Produção Bibliográfica) em formato XLSX.

    Args:
        items: Lista de itens de produção bibliográfica. Títulos são
               exportados literalmente (Req 14.2), sem normalização.
        n_docentes: Número de docentes permanentes do programa.
                    Usado para calcular limite 4N.
        output_path: Caminho do arquivo XLSX de saída.

    Returns:
        Path do arquivo gerado.

    Notes:
        - Itens excedentes de 4N são marcados mas NÃO descartados (Req 14.3).
        - NAO_CLASSIFICAVEL/NAO_CONSIDERADO aparecem no campo estrato (Req 14.5).
        - Nota de rodapé sobre autoria múltipla incluída (Req 14.4).
    """
    output_path = Path(output_path)
    limit_4n = 4 * n_docentes

    wb = Workbook()
    ws = wb.active
    ws.title = "Anexo 3 - Prod Bibliográfica"

    # Row 1: Ministry header (merged B1:K1)
    ws.cell(row=1, column=2, value=_HEADER_ANNEX3)
    ws.cell(row=1, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(row=1, column=2).font = Font(bold=True)
    ws.merge_cells("B1:K1")

    # Row 2: blank
    # Row 3: Subtitle (merged B3:G3)
    ws.cell(row=3, column=2, value=_SUBTITLE_ANNEX3)
    ws.cell(row=3, column=2).alignment = Alignment(wrap_text=True)
    ws.merge_cells("B3:G3")

    # Row 4: blank
    # Row 5: Column headers
    for col_idx, header in enumerate(_COLUMNS_ANNEX3, 1):
        cell = ws.cell(row=5, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)

    # Data rows starting from row 6
    for row_idx, item in enumerate(items, 1):
        excel_row = row_idx + 5
        exceeds = "SIM" if row_idx > limit_4n else ""

        ws.cell(row=excel_row, column=1, value=row_idx)
        ws.cell(row=excel_row, column=2, value=item.tipo)
        ws.cell(row=excel_row, column=3, value=item.issn_ou_isbn)
        ws.cell(row=excel_row, column=4, value=item.sigla_evento)
        # Título exportado LITERALMENTE — sem normalização (Req 14.2)
        ws.cell(row=excel_row, column=5, value=item.titulo)
        ws.cell(row=excel_row, column=6, value=item.autores_docentes)
        ws.cell(row=excel_row, column=7, value=item.autores_discentes)
        ws.cell(row=excel_row, column=8, value=item.outros_autores)
        ws.cell(row=excel_row, column=9, value=item.justificativa)
        # Estrato: pode conter NAO_CLASSIFICAVEL ou NAO_CONSIDERADO (Req 14.5)
        ws.cell(row=excel_row, column=10, value=item.estrato)
        # Indicador visual de excedente 4N (Req 14.3)
        ws.cell(row=excel_row, column=11, value=exceeds)

    # Footnote row (Req 14.4)
    footnote_row = len(items) + 5 + 2  # 2 rows after last data
    ws.cell(row=footnote_row, column=1, value=_FOOTNOTE)
    ws.cell(row=footnote_row, column=1).font = Font(italic=True, size=9)
    ws.merge_cells(
        start_row=footnote_row,
        start_column=1,
        end_row=footnote_row,
        end_column=len(_COLUMNS_ANNEX3),
    )

    # Auto-fit rough column widths
    _auto_width(ws)

    wb.save(output_path)
    return output_path


def generate_annex4(
    items: list[AnnexTechItem],
    n_docentes: int,
    output_path: str | Path,
) -> Path:
    """Gera o Anexo 4 (Produção Técnica) em formato XLSX.

    Args:
        items: Lista de itens de produção técnica. Títulos são
               exportados literalmente (Req 14.2).
        n_docentes: Número de docentes permanentes do programa.
                    M = max(10, N/4). Itens além de M são marcados.
        output_path: Caminho do arquivo XLSX de saída.

    Returns:
        Path do arquivo gerado.
    """
    output_path = Path(output_path)
    limit_m = max(10, n_docentes // 4)

    wb = Workbook()
    ws = wb.active
    ws.title = "Anexo 4 - Prod Técnica"

    # Row 1: Ministry header (merged B1:I1)
    ws.cell(row=1, column=2, value=_HEADER_ANNEX4)
    ws.cell(row=1, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(row=1, column=2).font = Font(bold=True)
    ws.merge_cells("B1:I1")

    # Row 2: blank
    # Row 3: Subtitle (merged B3:H3)
    ws.cell(row=3, column=2, value=_SUBTITLE_ANNEX4)
    ws.cell(row=3, column=2).alignment = Alignment(wrap_text=True)
    ws.merge_cells("B3:H3")

    # Row 4: blank
    # Row 5: Column headers
    for col_idx, header in enumerate(_COLUMNS_ANNEX4, 1):
        cell = ws.cell(row=5, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)

    # Data rows starting from row 6
    for row_idx, item in enumerate(items, 1):
        excel_row = row_idx + 5
        exceeds = "SIM" if row_idx > limit_m else ""

        ws.cell(row=excel_row, column=1, value=row_idx)
        ws.cell(row=excel_row, column=2, value=item.tipo)
        # Título exportado LITERALMENTE (Req 14.2)
        ws.cell(row=excel_row, column=3, value=item.titulo)
        ws.cell(row=excel_row, column=4, value=item.autores_docentes)
        ws.cell(row=excel_row, column=5, value=item.autores_discentes)
        ws.cell(row=excel_row, column=6, value=item.outros_autores)
        ws.cell(row=excel_row, column=7, value=item.parceiro_institucional)
        ws.cell(row=excel_row, column=8, value=item.justificativa)
        ws.cell(row=excel_row, column=9, value=item.estrato)
        ws.cell(row=excel_row, column=10, value=exceeds)
        ws.cell(row=excel_row, column=11, value=item.produto_bibliografico)

    # Footnote row (Req 14.4)
    footnote_row = len(items) + 5 + 2
    ws.cell(row=footnote_row, column=1, value=_FOOTNOTE)
    ws.cell(row=footnote_row, column=1).font = Font(italic=True, size=9)
    ws.merge_cells(
        start_row=footnote_row,
        start_column=1,
        end_row=footnote_row,
        end_column=len(_COLUMNS_ANNEX4),
    )

    _auto_width(ws)

    wb.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auto_width(ws) -> None:
    """Sets rough column widths based on header length."""
    for col_cells in ws.columns:
        max_length = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            if cell.value:
                # For multiline, use the longest line
                lines = str(cell.value).split("\n")
                line_max = max(len(line) for line in lines)
                max_length = max(max_length, line_max)
        adjusted = min(max_length + 2, 50)
        ws.column_dimensions[col_letter].width = adjusted
