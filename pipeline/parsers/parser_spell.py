"""Parser para a fonte SPELL — Scientific Periodicals Electronic Library.

A fonte SPELL publica um ranking de impacto de ~111 periódicos brasileiros
no formato XML Spreadsheet (.xls). O arquivo não contém ISSN, portanto
o parser retorna apenas o título do periódico para resolução posterior.

A métrica `spell_faixa` é derivada da posição no ranking:
- Top 10%: "decil_superior"
- 10%-40%: "10_a_40"
- 40%-70%: "40_a_70"
- Abaixo de 70%: "abaixo_70"

A métrica `spell_fator_impacto` é o "Impacto 5 Anos" (fator de impacto
de 5 anos com autocitação, coluna principal de ordenação do ranking SPELL).
"""

import math
import re
import xml.etree.ElementTree as ET
from typing import Iterator

from pipeline.parsers.base import ParsedRecord, SourceParser


def _calcular_faixa(posicao: int, total: int) -> str:
    """Calcula a faixa SPELL a partir da posição no ranking.

    A posição é 1-based (1 = primeiro lugar).
    Os cortes são: top 10% → decil_superior, 10-40% → 10_a_40,
    40-70% → 40_a_70, abaixo de 70% → abaixo_70.

    Usa ceil para definir o corte de cada faixa, garantindo que
    pelo menos 1 item caia no décil superior mesmo para listas pequenas.
    """
    if total <= 0:
        return "abaixo_70"

    corte_10 = math.ceil(total * 0.10)
    corte_40 = math.ceil(total * 0.40)
    corte_70 = math.ceil(total * 0.70)

    if posicao <= corte_10:
        return "decil_superior"
    elif posicao <= corte_40:
        return "10_a_40"
    elif posicao <= corte_70:
        return "40_a_70"
    else:
        return "abaixo_70"


def _parse_decimal_br(valor: str) -> float | None:
    """Converte número em formato brasileiro (vírgula decimal) para float.

    Retorna None se o valor for vazio ou não conversível.
    """
    if not valor or not valor.strip():
        return None
    try:
        return float(valor.strip().replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_xml_spreadsheet(path: str) -> Iterator[dict]:
    """Extrai linhas do XML Spreadsheet (formato .xls do SPELL).

    Yields dicts com chaves: posicao, titulo, impacto_5_anos.
    """
    ns = {
        "ss": "urn:schemas-microsoft-com:office:spreadsheet",
    }

    # O arquivo SPELL pode ter caracteres inválidos para XML estrito.
    # Lemos como texto e usamos um parser tolerante.
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extrair linhas via regex — mais robusto que ET.parse para este arquivo
    rows = re.findall(r"<Row>(.*?)</Row>", content, re.DOTALL)
    if not rows:
        return

    # Pular header (primeira linha)
    for row_xml in rows[1:]:
        cells = re.findall(
            r'<Data ss:Type="([^"]+)">([^<]*)</Data>', row_xml
        )
        if len(cells) < 5:
            continue

        # Colunas: [0]=posição, [1]=título, [2]=impacto5a_sem_auto,
        #           [3]=impacto2a_sem_auto, [4]=impacto5anos,
        #           [5]=impacto2anos, ...
        posicao_str = cells[0][1]
        titulo = cells[1][1]
        # Impacto 5 Anos (com autocitação) é a coluna 4 (índice 4)
        impacto_5_anos_str = cells[4][1] if len(cells) > 4 else ""

        try:
            posicao = int(posicao_str)
        except (ValueError, TypeError):
            continue

        impacto_5_anos = _parse_decimal_br(impacto_5_anos_str)

        yield {
            "posicao": posicao,
            "titulo": titulo.strip(),
            "impacto_5_anos": impacto_5_anos,
        }


class Parser:
    """Parser SPELL — ranking de impacto de periódicos brasileiros."""

    @property
    def source_id(self) -> str:
        return "spell"

    @property
    def provides(self) -> list[str]:
        return ["spell_faixa", "spell_fator_impacto"]

    def parse(self, path: str) -> Iterator[ParsedRecord]:
        """Extrai registros do arquivo SPELL.

        O arquivo SPELL não contém ISSN, portanto os registros são
        emitidos apenas com título (para resolução por matching de título).

        Yields:
            ParsedRecord com titulo e métricas spell_faixa + spell_fator_impacto.
        """
        # Primeiro passo: coletar todas as linhas para saber o total
        linhas = list(_parse_xml_spreadsheet(path))
        total = len(linhas)

        for linha in linhas:
            posicao = linha["posicao"]
            titulo = linha["titulo"]
            impacto = linha["impacto_5_anos"]

            faixa = _calcular_faixa(posicao, total)

            metricas: dict[str, str | int | float] = {
                "spell_faixa": faixa,
            }
            if impacto is not None:
                metricas["spell_fator_impacto"] = impacto

            yield ParsedRecord(
                issn=None,
                issn_alt=None,
                doi=None,
                titulo=titulo,
                metricas=metricas,
            )
