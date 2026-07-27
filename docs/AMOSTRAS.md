# Aquisição das bases

Marque conforme baixar. O pipeline funciona parcialmente com o que houver — fonte
ausente vira parser bloqueado, nunca dado inventado.

Para cada arquivo baixado, rode:

```bash
python scripts/make_sample.py ~/Downloads/<arquivo> --id <id>
```

O script gera `docs/fontes/<id>_schema.md` com os nomes **reais** das colunas.
É esse inventário que o agente lê para escrever o parser.

---

## Conjunto mínimo — grátis, sem login, começa por aqui

- [ ] **`scopus`** — Scopus Source List
  `elsevier.com/products/scopus/content` → "Source title list" (.xlsx, 15–20 MB,
  atualizado trimestralmente). Confira a data no nome do arquivo.
  Entrega: `scopus_percentil` (Área 02) **e** `scopus_quartil` (Área 27).
  ```bash
  python scripts/make_sample.py ~/Downloads/ext_list.xlsx --id scopus --sheet 0
  ```

- [ ] **`sjr`** — SCImago Journal Rank
  `scimagojr.com/journalrank.php?type=j` → botão "Download data".
  ⚠️ Separador `;` e vírgula decimal. **Não abra e salve no Excel** — mande o
  original para o script.

- [ ] **`qualis`** — Qualis Periódicos 2021-2024 (camada histórica)
  Sucupira legado → consulta geral de periódicos → filtrar área → exportar.

Com esses três: Área 27 quase completa, Área 02 na parte de periódicos.

---

## Complementares — grátis, algum trabalho manual

- [ ] **`spell`** — `spell.org.br/impacto`
  Tabela HTML, só ~111 periódicos. Copiar e colar numa planilha resolve.

- [ ] **`abdc`** — `abdc.edu.au/abdc-journal-quality-list/`
  Download direto, pode pedir cadastro.

- [ ] **`scielo`** — lista de periódicos correntes do SciELO Brasil (~328 títulos)
  Não há CSV limpo. Copiar o HTML ou usar a API do SciELO.

---

## Restritas — só o inventário vai para o repositório

O script detecta essas pela `--id` e **não** gera amostra versionável. Aponte o
caminho local em `config/local.yml`.

- [ ] **`abs`** — `charteredabs.org/academic-journal-guide/` (conta gratuita)
- [ ] **`jcr`** — Clarivate via **Portal de Periódicos CAPES** (login CAFe / IFMA)

---

## Bloqueadas — sem fonte localizada

- [ ] **`wos`** — percentil da Web of Science
  A Área 02 usa `max(wos_percentil, scopus_percentil)`. Sem a WoS, o motor
  calcula com o Scopus e o resultado é **sempre igual ou menor** que o oficial.
  Nunca superestima. O veredito deve ser rotulado como
  **estimativa conservadora**, indicando qual fonte faltou.

- [ ] **`sbc_eventos`** — lista oficial de siglas de eventos da Área 02, com H5 e
  marcação Top10 / Top20 / relevante das Comissões Especiais da SBC.
  Citada no Anexo 3 da ficha ("sigla do evento conforme indicado pela área").
  URL A LOCALIZAR — verificar página do CA-CC e documentos institucionais da SBC.
  Sem ela, `conferencePaper` permanece em `NAO_CLASSIFICAVEL`.

- [ ] **`qualis_eventos`** — Qualis Eventos 2025. Fonte oficial a localizar.
