"""Parser para a Scopus Source List (XLSX).

Fonte: Elsevier — Scopus Source Title List
URL: https://www.elsevier.com/products/scopus/content
Formato: XLSX, aba 0 (principal)

Colunas relevantes identificadas no arquivo ext_list_Jun_2026.xlsx:
  - "Source Title" → título do periódico
  - "ISSN" → Print-ISSN (8 dígitos, sem hífen)
  - "EISSN" → E-ISSN (8 dígitos, sem hífen)
  - "Percentile" → percentil CiteScore (se presente)
  - "CiteScore Quartile" / "Quartile" → quartil CiteScore (se presente)
  - "CiteScore" → valor numérico CiteScore (se presente)

Nota: O arquivo ext_list_Jun_2026.xlsx é a Source Title List e NÃO contém
as colunas de CiteScore/Percentile/Quartile. Para esses dados, é necessário
um arquivo CiteScore separado (mesmo formato XLSX). O parser detecta
automaticamente quais colunas existem e extrai o que estiver disponível.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

import pandas as pd

from pipeline.parsers.base import ParsedRecord


def _format_issn(raw: str | None) -> str | None:
    """Formata ISSN bruto (8 dígitos sem hífen) para XXXX-XXXX.

    Retorna None se o valor não for convertível em ISSN válido.
    """
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    # Remove hífens existentes e espaços
    digits = raw.replace("-", "").replace(" ", "")
    if len(digits) != 8:
        return None
    # Verifica se são 7 dígitos + dígito verificador (0-9 ou X)
    if not re.match(r"^\d{7}[\dXx]$", digits):
        return None
    return f"{digits[:4]}-{digits[4:].upper()}"


def _find_column(columns: list[str], patterns: list[str]) -> str | None:
    """Encontra coluna por nome, tentando múltiplos padrões (case-insensitive)."""
    col_lower = {c.lower().strip(): c for c in columns}
    for pat in patterns:
        pat_lower = pat.lower().strip()
        # Busca exata
        if pat_lower in col_lower:
            return col_lower[pat_lower]
        # Busca parcial
        for key, original in col_lower.items():
            if pat_lower in key:
                return original
    return None


class Parser:
    """Parser para Scopus Source List / CiteScore (XLSX).

    Implementa a interface SourceParser.
    """

    @property
    def source_id(self) -> str:
        return "scopus"

    @property
    def provides(self) -> list[str]:
        return ["scopus_percentil", "scopus_quartil", "scopus_citescore"]

    def parse(self, path: str) -> Iterator[ParsedRecord]:
        """Extrai registros do XLSX Scopus (aba 0).

        Yields:
            ParsedRecord para cada linha com pelo menos um ISSN válido.
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        df = pd.read_excel(filepath, sheet_name=0, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        # Detectar colunas de ISSN
        col_issn = _find_column(df.columns.tolist(), ["Print-ISSN", "ISSN"])
        col_eissn = _find_column(df.columns.tolist(), ["E-ISSN", "EISSN"])
        col_title = _find_column(
            df.columns.tolist(),
            ["Source Title", "Sourcetitle", "Title"],
        )

        # Detectar colunas de métricas (podem não existir)
        col_percentile = _find_column(
            df.columns.tolist(),
            ["Percentile", "CiteScore Percentile", "Percentil"],
        )
        col_quartile = _find_column(
            df.columns.tolist(),
            [
                "CiteScore Quartile",
                "Quartile",
                "CiteScore Best Quartile",
                "Best Quartile",
            ],
        )
        col_citescore = _find_column(
            df.columns.tolist(),
            ["CiteScore", "CiteScore 2024", "CiteScore 2023", "Cite Score"],
        )

        if col_issn is None and col_eissn is None:
            raise ValueError(
                f"Nenhuma coluna de ISSN encontrada no arquivo. "
                f"Colunas disponíveis: {df.columns.tolist()}"
            )

        for _, row in df.iterrows():
            issn = _format_issn(row.get(col_issn)) if col_issn else None
            eissn = _format_issn(row.get(col_eissn)) if col_eissn else None

            # Pular linhas sem nenhum ISSN válido
            if issn is None and eissn is None:
                continue

            titulo = None
            if col_title:
                val = row.get(col_title)
                if pd.notna(val) and str(val).strip():
                    titulo = str(val).strip()

            # Extrair métricas disponíveis
            metricas: dict[str, str | int | float] = {}

            if col_percentile:
                val = row.get(col_percentile)
                if pd.notna(val) and str(val).strip():
                    try:
                        metricas["scopus_percentil"] = float(val)
                    except (ValueError, TypeError):
                        pass

            if col_quartile:
                val = row.get(col_quartile)
                if pd.notna(val) and str(val).strip():
                    val_str = str(val).strip().upper()
                    if val_str in ("Q1", "Q2", "Q3", "Q4"):
                        metricas["scopus_quartil"] = val_str

            if col_citescore:
                val = row.get(col_citescore)
                if pd.notna(val) and str(val).strip():
                    try:
                        metricas["scopus_citescore"] = float(val)
                    except (ValueError, TypeError):
                        pass

            yield ParsedRecord(
                issn=issn,
                issn_alt=eissn,
                doi=None,
                titulo=titulo,
                metricas=metricas,
            )
