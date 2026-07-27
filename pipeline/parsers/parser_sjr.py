"""Parser para a fonte SCImago Journal Rank (SJR).

Formato do arquivo: CSV com separador ";" e vírgula decimal ",".
Encoding: UTF-8.

⚠️ Não abra e salve no Excel — o arquivo original deve ser processado diretamente.
"""

import csv
from typing import Iterator

from pipeline.parsers.base import ParsedRecord


class Parser:
    """Parser SJR implementando a interface SourceParser.

    Extrai ISSN(s), título, quartil e valor SJR de cada linha do CSV
    disponibilizado em scimagojr.com.
    """

    @property
    def source_id(self) -> str:
        return "sjr"

    @property
    def provides(self) -> list[str]:
        return ["sjr_quartil", "sjr_valor"]

    def parse(self, path: str) -> Iterator[ParsedRecord]:
        """Lê o CSV do SciMago e produz ParsedRecord por linha.

        O campo Issn pode conter múltiplos ISSNs separados por ", ".
        Exemplo: "15424863, 00079235"

        O valor SJR usa vírgula como separador decimal (formato europeu).
        Exemplo: "104,065" → 104.065
        """
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                issn_raw = row.get("Issn", "").strip()
                titulo = row.get("Title", "").strip() or None
                quartil = row.get("SJR Best Quartile", "").strip() or None
                sjr_raw = row.get("SJR", "").strip()

                # Extrair ISSNs (podem ser múltiplos separados por ", ")
                issns = [s.strip() for s in issn_raw.split(",") if s.strip()]
                issn = issns[0] if issns else None
                issn_alt = issns[1] if len(issns) > 1 else None

                # Converter valor SJR (vírgula decimal → ponto)
                sjr_valor = self._parse_decimal(sjr_raw)

                # Montar métricas
                metricas: dict[str, str | int | float] = {}
                if quartil:
                    metricas["sjr_quartil"] = quartil
                if sjr_valor is not None:
                    metricas["sjr_valor"] = sjr_valor

                # Pular linhas sem ISSN e sem métricas úteis
                if issn is None and not metricas:
                    continue

                yield ParsedRecord(
                    issn=issn,
                    issn_alt=issn_alt,
                    doi=None,
                    titulo=titulo,
                    metricas=metricas,
                )

    @staticmethod
    def _parse_decimal(value: str) -> float | None:
        """Converte string com vírgula decimal para float.

        Retorna None se a string estiver vazia ou não for conversível.
        """
        if not value:
            return None
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
