"""Funções de normalização e validação de ISSN.

Implementa:
- normalize_issn: formata para XXXX-XXXX, retorna None se inválido
- validate_check_digit: algoritmo ISSN mod 11
- resolve_issn_l: resolução via tabela ISSN-L
- normalize_title: normalização de títulos para fallback de resolução
"""

import re
import unicodedata


def validate_check_digit(issn: str) -> bool:
    """Valida dígito verificador conforme algoritmo ISSN (mod 11).

    O ISSN deve ter exatamente 8 caracteres (dígitos, com último podendo ser 'X').
    Algoritmo: sum((8-i) * digit_i para i=0..6), check_digit = 11 - (soma % 11).
    Se o resultado for 11, check_digit = 0. Se for 10, check_digit = 'X'.
    """
    # Remove hífens para validação
    digits = issn.replace("-", "")
    if len(digits) != 8:
        return False

    # Primeiros 7 devem ser dígitos
    if not digits[:7].isdigit():
        return False

    # Último pode ser dígito ou 'X'
    last = digits[7].upper()
    if last not in "0123456789X":
        return False

    # Calcula soma ponderada dos primeiros 7 dígitos
    total = sum((8 - i) * int(digits[i]) for i in range(7))
    remainder = total % 11
    expected = 11 - remainder if remainder != 0 else 0

    # Compara com o dígito verificador
    if expected == 10:
        return last == "X"
    return last == str(expected)


def normalize_issn(raw: str) -> str | None:
    """Normaliza ISSN para formato XXXX-XXXX.

    Processo:
    1. Remove hífens e espaços em branco
    2. Verifica comprimento = 8
    3. Valida dígito verificador
    4. Formata como XXXX-XXXX

    Retorna None se inválido (< 8 dígitos, caracteres inválidos,
    ou dígito verificador incorreto).
    """
    # Strip hyphens e whitespace
    cleaned = raw.replace("-", "").replace(" ", "").strip()

    # Verifica comprimento
    if len(cleaned) != 8:
        return None

    # Primeiros 7 devem ser dígitos, último pode ser dígito ou X
    if not cleaned[:7].isdigit():
        return None
    if cleaned[7].upper() not in "0123456789X":
        return None

    # Normaliza o X para maiúsculo
    cleaned = cleaned[:7] + cleaned[7].upper()

    # Valida check digit
    if not validate_check_digit(cleaned):
        return None

    # Formata XXXX-XXXX
    return f"{cleaned[:4]}-{cleaned[4:]}"


def resolve_issn_l(issn: str, issn_l_table: dict[str, str]) -> str:
    """Resolve ISSN para ISSN-L usando tabela oficial.

    Busca o ISSN na tabela. Se encontrado, retorna o ISSN-L correspondente.
    Se não encontrado, retorna o próprio ISSN como chave (fallback).

    Args:
        issn: ISSN normalizado no formato XXXX-XXXX.
        issn_l_table: Dicionário mapeando ISSN → ISSN-L.

    Returns:
        ISSN-L correspondente ou o próprio ISSN se não encontrado na tabela.
    """
    return issn_l_table.get(issn, issn)


def normalize_title(title: str) -> str:
    """Normaliza título para uso como fallback de resolução.

    Processo:
    1. Decompõe em NFKD (unicodedata) — decompõe acentos e caracteres de compatibilidade
    2. Remove caracteres combining (categoria 'Mn')
    3. Converte para lowercase
    4. Remove pontuação (mantém apenas alfanuméricos e espaços)
    5. Colapsa múltiplos espaços em um só
    6. Strip de espaços nas bordas

    Args:
        title: Título original do veículo.

    Returns:
        Título normalizado para comparação.
    """
    # 1. Decomposição NFKD (decompõe acentos e compatibilidade)
    nfkd = unicodedata.normalize("NFKD", title)

    # 2. Remove combining characters (acentos)
    without_accents = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")

    # 3. Lowercase
    lower = without_accents.lower()

    # 4. Remove pontuação — mantém apenas alfanuméricos e espaços
    alphanumeric = re.sub(r"[^a-z0-9\s]", "", lower)

    # 5. Colapsa múltiplos espaços
    collapsed = re.sub(r"\s+", " ", alphanumeric)

    # 6. Strip
    return collapsed.strip()
