"""Parser para a fonte Qualis Periódicos 2021-2024 (camada histórica).

Formato do arquivo: XLSX (openpyxl).
Fonte livre — disponível via Sucupira/CAPES.

A planilha "RelatorioQualis" tem cabeçalho na linha 1 com colunas:
  ISSN | Título | Área de Avaliação | Estrato

Estratos válidos: A1, A2, A3, A4, B1, B2, B3, B4, C.

⚠️ Estes são dados HISTÓRICOS do ciclo 2021-2024.
    Não devem ser mesclados com a classificação 2025-2028.
"""

from typing import Iterator

import openpyxl

from pipeline.parsers.base import ParsedRecord

# Estratos válidos no Qualis 2021-2024
_ESTRATOS_VALIDOS = {"A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C"}


class Parser:
    """Parser Qualis Histórico implementando a interface SourceParser.

    Extrai ISSN, título, área de avaliação e estrato de cada linha
    do XLSX publicado pela CAPES com as classificações do ciclo 2021-2024.

    Cada registro produz a métrica `qualis_estrato_historico` com o valor
    do estrato (ex: "A1", "B2"). A área de avaliação original é preservada
    no campo `titulo` como "<título> [<área>]" para permitir geração de
    snapshot histórico com separação por área.
    """

    @property
    def source_id(self) -> str:
        return "qualis"

    @property
    def provides(self) -> list[str]:
        return ["qualis_estrato_historico"]

    def parse(self, path: str) -> Iterator[ParsedRecord]:
        """Lê o XLSX do Qualis e produz ParsedRecord por linha.

        Linhas sem ISSN ou sem estrato válido são ignoradas.
        O campo `area_avaliacao` é codificado nas métricas como metadata
        para que o gerador de snapshot histórico possa separar por área.
        """
        wb = openpyxl.load_workbook(path, read_only=False, data_only=True)
        ws = wb.active

        header_map: dict[str, int] | None = None

        for row in ws.iter_rows(values_only=True):
            if header_map is None:
                # Procurar a linha de cabeçalho (contém "ISSN")
                cells = [str(c).strip() if c is not None else "" for c in row]
                if "ISSN" in cells:
                    header_map = {cells[i]: i for i in range(len(cells)) if cells[i]}
                continue

            # Extrair valores usando o mapa de cabeçalhos
            issn = self._cell_str(row, header_map.get("ISSN"))
            titulo = self._cell_str(row, header_map.get("Título"))
            area = self._cell_str(row, header_map.get("Área de Avaliação"))
            estrato = self._cell_str(row, header_map.get("Estrato"))

            # Ignorar linhas sem ISSN ou sem estrato válido
            if not issn or not estrato:
                continue

            # Validar que o estrato é um valor reconhecido
            if estrato not in _ESTRATOS_VALIDOS:
                continue

            # Montar métricas — estrato histórico + área como metadata
            metricas: dict[str, str | int | float] = {
                "qualis_estrato_historico": estrato,
            }
            if area:
                metricas["qualis_area_avaliacao"] = area

            yield ParsedRecord(
                issn=issn,
                issn_alt=None,
                doi=None,
                titulo=titulo or None,
                metricas=metricas,
            )

        wb.close()

    @staticmethod
    def _cell_str(row: tuple, col_idx: int | None) -> str | None:
        """Extrai valor de célula como string limpa, ou None se vazia."""
        if col_idx is None or col_idx >= len(row):
            return None
        val = row[col_idx]
        if val is None:
            return None
        cleaned = str(val).strip()
        return cleaned if cleaned else None
