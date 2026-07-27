#!/usr/bin/env python3
"""
make_sample.py — prepara amostras de bases bibliométricas para o repositório.

Recebe um arquivo baixado (csv/tsv/xlsx/xls), e produz:
  1. uma amostra enxuta (N linhas) em docs/fontes/
  2. um inventário de colunas em docs/fontes/<nome>_schema.md

O inventário é o que o agente de código lê para escrever o parser: nome REAL da
coluna, tipo inferido, taxa de nulos e valores de exemplo. Nada é adivinhado.

Uso:
    python scripts/make_sample.py ~/Downloads/scimagojr\\ 2025.csv --id sjr
    python scripts/make_sample.py ~/Downloads/ext_list.xlsx --id scopus --sheet 0
    python scripts/make_sample.py ~/Downloads/jcr.csv --id jcr --rows 30 --no-copy

Notas:
  - Detecta separador e encoding automaticamente para CSV (inclui o formato
    europeu do SciMago: separador ';' e vírgula decimal).
  - --no-copy evita versionar a amostra: usar para bases licenciadas (JCR, ABS),
    onde só o inventário de colunas deve ir para o repositório.
"""

import argparse
import csv
import io
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Faltando pandas. Rode: pip install pandas openpyxl")

OUT_DIR = Path("docs/fontes")

# Bases cujos dados brutos NÃO podem ser versionados no repositório.
LICENCIADAS = {"jcr", "abs", "wos"}


def sniff_csv(path: Path):
    """Descobre encoding e separador sem depender de sorte."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            head = path.open("r", encoding=enc).read(64 * 1024)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit(f"Não consegui decodificar {path} com nenhum encoding testado.")

    try:
        sep = csv.Sniffer().sniff(head, delimiters=";,\t|").delimiter
    except csv.Error:
        # Fallback: o separador mais frequente na primeira linha
        first = head.splitlines()[0] if head.splitlines() else ""
        sep = max(";,\t|", key=first.count)
    return enc, sep


def load(path: Path, sheet):
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        df = pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)
        return df, {"formato": "xlsx", "aba": str(sheet if sheet is not None else 0)}
    if path.suffix.lower() == ".xls":
        df = pd.read_excel(path, sheet_name=sheet if sheet is not None else 0, engine="xlrd")
        return df, {"formato": "xls", "aba": str(sheet if sheet is not None else 0)}

    enc, sep = sniff_csv(path)
    df = pd.read_csv(path, sep=sep, encoding=enc, dtype=str, keep_default_na=False,
                     na_values=[""], engine="python")
    return df, {"formato": "csv", "encoding": enc, "separador": repr(sep)}


def inventario(df: pd.DataFrame, meta: dict, origem: Path, source_id: str) -> str:
    total = len(df)
    linhas = []
    linhas.append(f"# Inventário de colunas — `{source_id}`\n")
    linhas.append("> Gerado por `scripts/make_sample.py`. Nomes de coluna são REAIS,")
    linhas.append("> lidos do arquivo baixado. NÃO edite à mão.\n")
    linhas.append(f"- Arquivo de origem: `{origem.name}`")
    for k, v in meta.items():
        linhas.append(f"- {k}: `{v}`")
    linhas.append(f"- Total de linhas: **{total}**")
    linhas.append(f"- Total de colunas: **{len(df.columns)}**\n")

    linhas.append("| # | Nome exato da coluna | Preenchida | Valores de exemplo |")
    linhas.append("|---|---|---|---|")
    for i, col in enumerate(df.columns, 1):
        s = df[col]
        preenchida = f"{(s.notna().sum() / total * 100):.0f}%" if total else "—"
        exemplos = [str(v) for v in s.dropna().unique()[:3]]
        ex = " · ".join(e[:40] for e in exemplos) or "—"
        ex = ex.replace("|", "\\|")
        nome = str(col).replace("|", "\\|")
        linhas.append(f"| {i} | `{nome}` | {preenchida} | {ex} |")

    # Pistas úteis para o parser
    linhas.append("\n## Candidatas a chave\n")
    def marca(termos):
        return [c for c in df.columns if any(t in str(c).lower() for t in termos)]
    for rotulo, termos in [
        ("ISSN", ["issn"]),
        ("Título", ["title", "titulo", "título", "nome", "periodico", "periódico"]),
        ("Quartil", ["quartile", "quartil"]),
        ("Percentil", ["percentile", "percentil"]),
        ("Métrica de impacto", ["citescore", "sjr", "jif", "impact", "h index", "h-index", "h5"]),
    ]:
        achadas = marca(termos)
        linhas.append(f"- **{rotulo}**: " + (", ".join(f"`{c}`" for c in achadas) or "_nenhuma óbvia_"))

    linhas.append("\n## Pendências para o parser\n")
    linhas.append("- [ ] Confirmar qual coluna de ISSN usar quando houver print e eletrônico")
    linhas.append("- [ ] Verificar formato do ISSN (com ou sem hífen, com zeros à esquerda)")
    if meta.get("formato") == "csv":
        linhas.append("- [ ] Confirmar separador decimal (vírgula vs ponto) nas métricas numéricas")
    linhas.append("- [ ] Confirmar se há linhas de cabeçalho/rodapé fora da tabela")
    return "\n".join(linhas) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", type=Path)
    ap.add_argument("--id", required=True,
                    help="id da fonte em sources.yml (sjr, scopus, abdc, abs, jcr, spell, scielo, qualis)")
    ap.add_argument("--rows", type=int, default=50, help="linhas na amostra (padrão 50)")
    ap.add_argument("--sheet", default=None, help="aba da planilha (nome ou índice)")
    ap.add_argument("--no-copy", action="store_true",
                    help="gera só o inventário, sem versionar dados brutos")
    args = ap.parse_args()

    if not args.arquivo.exists():
        sys.exit(f"Não encontrei {args.arquivo}")

    sheet = args.sheet
    if sheet is not None and sheet.isdigit():
        sheet = int(sheet)

    df, meta = load(args.arquivo, sheet)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    schema_path = OUT_DIR / f"{args.id}_schema.md"
    schema_path.write_text(inventario(df, meta, args.arquivo, args.id), encoding="utf-8")
    print(f"✅ inventário  → {schema_path}  ({len(df.columns)} colunas, {len(df)} linhas)")

    licenciada = args.id.lower() in LICENCIADAS
    if args.no_copy or licenciada:
        motivo = "base licenciada" if licenciada else "--no-copy"
        print(f"⏭️  amostra NÃO gerada ({motivo}). Só o inventário vai para o repositório.")
        if licenciada:
            print("   Aponte o arquivo local em config/local.yml para o pipeline usar.")
        return

    amostra = df.head(args.rows)
    out = OUT_DIR / f"{args.id}_sample.csv"
    amostra.to_csv(out, index=False, encoding="utf-8")
    print(f"✅ amostra     → {out}  ({len(amostra)} linhas)")


if __name__ == "__main__":
    main()
