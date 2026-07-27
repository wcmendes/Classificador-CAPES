# 📦 MdBundle for Zotero

Bundle, analyze & export your PDF/MD attachments from Zotero

![Zotero](https://img.shields.io/badge/Zotero-7%20%7C%208%20%7C%209-CC2936)
![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

English | [Português](#português)

## About

MdBundle is a Zotero plugin that manages the relationship between your PDFs and their Markdown counterparts. It exports matched PDF/MD pairs, diagnoses your library's attachment health, generates MDs from PDFs, and selects cited items directly from Word documents.

The key feature is **intelligent pairing**: MdBundle only considers a PDF and MD as a pair when they share the same base filename (e.g., `Smith et al 2024.pdf` ↔ `Smith et al 2024.md`).

### Why Markdown matters for research

Markdown versions of academic papers are essential for modern AI-assisted research workflows:

- **LLM context**: Feed your papers as MD directly into ChatGPT, Claude, Gemini, or local models for summarization, Q&A, and literature review
- **RAG pipelines**: Build Retrieval-Augmented Generation systems over your Zotero library using structured text
- **Semantic search**: MD files are lightweight and easily indexed, enabling fast full-text search across your entire corpus
- **Interoperability**: Works with Obsidian, Logseq, Notion, and other knowledge management tools
- **Version control**: Plain text diffs cleanly in Git, unlike PDFs

MdBundle pairs naturally with tools like [pdftollm](https://github.com/wcmendes/pdftollm) for high-quality PDF→MD conversion with OCR support, enabling a complete pipeline from Zotero to LLM-ready text.

## Features

| Feature | Description |
|---------|-------------|
| **Export** | Export PDF/MD pairs to a folder (all, PDFs only, or MDs only) |
| **Analyze** | Diagnostic report: items with/without PDF, with/without matching MD, suspicious small MDs |
| **Generate** | Extract text from PDFs and create linked MD files automatically |
| **Select from .docx** | Read a Word document and select all cited items in your library |
| **OCR tagging** | Items with non-extractable PDFs are tagged `needs-ocr` for later processing |

## How it works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Selected Items │────▶│  MdBundle Plugin  │────▶│  Export Folder   │
│  (or .docx)     │     │                  │     │  PDF + MD pairs  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Diagnostic &    │
                        │  MD Generation   │
                        └──────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Tagged items    │
                        │  "needs-ocr"     │
                        └──────────────────┘
```

## Installation

1. Download `mdbundle.xpi` from [Releases](https://github.com/wcmendes/MdBundle-for-Zotero/releases)
2. In Zotero: **Tools → Add-ons → ⚙️ → Install Add-on From File**
3. Select the `.xpi` file

## Usage

### Right-click menu (on selected items)

```
MdBundle...
  ├── Export All (PDF + MD)
  ├── Export PDFs only
  ├── Export MDs only
  ├── ─────────────
  ├── Analyze items (diagnostic)
  ├── ─────────────
  └── Generate missing MDs (PDF→MD)
```

### Tools menu

```
Tools → Select cited items from .docx...
```

### Workflow example

```bash
# 1. Open your Word article (.docx)
Tools → "Select cited items from .docx..."
→ Select your .docx file
→ Items are automatically selected in Zotero

# 2. Analyze what you have
Right-click → MdBundle → Analyze items
→ See which items are missing PDF or MD

# 3. Generate missing MDs
Right-click → MdBundle → Generate missing MDs
→ MDs are created and linked; OCR-needed items are tagged

# 4. Export
Right-click → MdBundle → Export All
→ Choose destination folder
→ All PDF/MD pairs are copied there
```

## Localization

MdBundle supports multiple languages:

| Language | Locale | Language | Locale |
|----------|--------|----------|--------|
| 🇺🇸 English | en-US | 🇯🇵 日本語 | ja-JP |
| 🇧🇷 Português | pt-BR | 🇰🇷 한국어 | ko-KR |
| 🇪🇸 Español | es-ES | 🇷🇺 Русский | ru-RU |
| 🇨🇳 中文 | zh-CN | 🇵🇱 Polski | pl-PL |
| 🇮🇹 Italiano | it-IT | 🇹🇷 Türkçe | tr-TR |
| 🇫🇷 Français | fr-FR | 🇩🇪 Deutsch | de-DE |

Zotero automatically selects the language based on your settings. Unsupported locales fall back to English.

## About OCR

When MdBundle detects a PDF without extractable text (scanned/image-based):
1. The item is tagged with `needs-ocr`
2. You can filter by this tag later and process with your preferred OCR tool

## Build

```bash
cd src
zip -r ../mdbundle.xpi .
```

## Related Projects

| Project | Description |
|---------|-------------|
| [pdftollm](https://github.com/wcmendes/pdftollm) | High-quality PDF→MD conversion with OCR support for LLM pipelines |

## Compatibility

| Zotero Version | Status |
|---------------|--------|
| 7.x | ✅ |
| 8.x | ✅ |
| 9.x | ✅ |

---

## Português

### Sobre

MdBundle é um plugin para Zotero que gerencia a relação entre seus PDFs e seus equivalentes em Markdown. Exporta pares PDF/MD, diagnostica a saúde dos anexos da sua biblioteca, gera MDs a partir de PDFs e seleciona itens citados diretamente de documentos Word.

#### Por que Markdown importa para pesquisa

Versões em Markdown de artigos acadêmicos são essenciais para fluxos de trabalho modernos com IA:

- **Contexto para LLMs**: Alimente seus artigos como MD diretamente no ChatGPT, Claude, Gemini ou modelos locais para sumarização, Q&A e revisão de literatura
- **Pipelines RAG**: Construa sistemas de Geração Aumentada por Recuperação sobre sua biblioteca Zotero
- **Busca semântica**: Arquivos MD são leves e facilmente indexáveis
- **Interoperabilidade**: Funciona com Obsidian, Logseq, Notion e outras ferramentas de gestão do conhecimento

MdBundle combina naturalmente com ferramentas como [pdftollm](https://github.com/wcmendes/pdftollm) para conversão PDF→MD de alta qualidade com suporte a OCR.

### Funcionalidades

| Funcionalidade | Descrição |
|---------------|-----------|
| **Exportar** | Exporta pares PDF/MD para uma pasta (tudo, só PDFs ou só MDs) |
| **Analisar** | Relatório: itens com/sem PDF, com/sem MD correspondente, MDs suspeitos |
| **Gerar** | Extrai texto de PDFs e cria arquivos MD vinculados automaticamente |
| **Selecionar do .docx** | Lê um documento Word e seleciona todos os itens citados na biblioteca |
| **Tag OCR** | Itens com PDFs sem texto extraível são marcados com `needs-ocr` |

### Instalação

1. Baixe `mdbundle.xpi` da página de [Releases](https://github.com/wcmendes/MdBundle-for-Zotero/releases)
2. No Zotero: **Ferramentas → Complementos → ⚙️ → Instalar complemento a partir de arquivo**
3. Selecione o arquivo `.xpi`

---

## Author

**William Corrêa Mendes**

Diretor de Gestão de TI — [IFMA](http://www.ifma.edu.br/) · Coordenador do Observatório de Egressos (SETEC/MEC)
MSc. Engenharia Elétrica / Ciência da Computação — UFMA · Doutorando — Fucape Business School

[Lattes](http://lattes.cnpq.br/7726054867638395) | [LinkedIn](https://www.linkedin.com/in/williamcmendes/) | [GitHub](https://github.com/wcmendes) | [ORCID](https://orcid.org/0009-0006-8272-8549)

## Support the Project

If MdBundle is useful for your research, consider supporting its development:

- ⭐ Star this repository
- 🐛 [Report bugs or suggest features](https://github.com/wcmendes/MdBundle-for-Zotero/issues)
- 🌍 [Contribute translations](CONTRIBUTING.md)
- 🔀 [Submit a Pull Request](CONTRIBUTING.md)
- 💜 [GitHub Sponsors](https://github.com/sponsors/wcmendes)
- ☕ [Buy Me a Coffee](https://buymeacoffee.com/wcmendes)
- 🇧🇷 PIX: `2ddcbe7b-e3f3-4502-ae29-c735beee9ed6`

## License

MIT
