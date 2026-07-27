# Implementation Plan: Classificador CAPES

## Overview

Plano de implementação incremental seguindo a restrição R15: o sistema nasce com ZERO fontes e cresce uma por vez. Nenhuma tarefa depende de ter todas as fontes disponíveis. A ordenação é:

1. Motor de regras + testes com fixtures sintéticas
2. Plugin com dados mockados para validar UX
3. Interface de parser + comando de onboarding
4. Primeiro parser real (quando a primeira amostra chegar)
5. Parsers restantes, um por vez

**Linguagens**: Python (pipeline), JavaScript (plugin Zotero 7).

## Tasks

- [x] 1. Esqueleto do monorepo e contratos fundamentais
  - [x] 1.1 Criar estrutura de diretórios e configuração do projeto Python
    - Criar `pipeline/` com `__init__.py`, `pyproject.toml` (com pytest + hypothesis como deps de dev)
    - Criar `pipeline/parsers/__init__.py`, `pipeline/parsers/base.py` (interface `SourceParser` Protocol)
    - Criar `pipeline/tests/conftest.py` com fixtures básicas
    - Criar `sources.yml` com as fontes conhecidas (todas em status `pendente` ou `bloqueada`)
    - Criar `config/local.yml.example` (template gitignored)
    - Adicionar `.gitignore` com regras para `config/local.yml` e dados restritos
    - _Requirements: 1.6, 8.1, 8.4, 8.5, 13.1, 13.3_

  - [x] 1.2 Criar `schema/snapshot.schema.json` (contrato pipeline → plugin)
    - Definir JSON Schema para o formato do snapshot conforme design (campos: area, nome, vigencia, status, escala, data_snapshot, fontes_utilizadas, nao_automatizavel, veiculos)
    - Validar que o schema aceita snapshots com zero veículos (sistema nasce vazio)
    - _Requirements: 15.1, 16.3_

  - [x] 1.3 Criar dataclasses do domínio (`pipeline/vehicles.py`, `pipeline/issn.py` stubs)
    - Implementar `MetricValue`, `VehicleRecord`, `ParsedRecord` como dataclasses
    - Implementar stubs de `normalize_issn`, `validate_check_digit`, `resolve_issn_l`, `normalize_title`
    - _Requirements: 1.1, 1.2, 1.4_

- [x] 2. Normalização de ISSN e título
  - [x] 2.1 Implementar `pipeline/issn.py` completo
    - `normalize_issn`: formata para XXXX-XXXX, retorna None se inválido
    - `validate_check_digit`: algoritmo ISSN mod 11
    - `resolve_issn_l`: resolução via tabela ISSN-L, fallback para o próprio ISSN
    - `normalize_title`: lowercase, sem acentos, sem pontuação, espaços colapsados
    - _Requirements: 1.1, 1.2, 1.4_

  - [ ]* 2.2 Escrever testes de propriedade para normalização de ISSN
    - **Property 1: Normalização de ISSN — round-trip**
    - **Validates: Requirements 1.1**

  - [ ]* 2.3 Escrever testes de propriedade para normalização de título
    - **Property 2: Normalização de título — idempotência**
    - **Validates: Requirements 1.4**

  - [ ]* 2.4 Escrever testes unitários para ISSN e título
    - Casos: ISSN com/sem hífen, ISSN com X como dígito verificador, ISSN curto, título com acentos e pontuação
    - _Requirements: 1.1, 1.4_

- [x] 3. Checkpoint — Normalização funcional
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Motor de regras genérico (com fixtures sintéticas)
  - [x] 4.1 Implementar avaliação de regras individuais (`pipeline/engine.py`)
    - `evaluate_rule`: campo `in` (case-sensitive, tipo-exata), `min`/`max` (min inclusivo, max exclusivo), `requer` (conjunção lógica)
    - Testar com fixtures sintéticas (NÃO dados reais)
    - _Requirements: 2.3, 2.4, 2.5, 2.13_

  - [ ]* 4.2 Escrever testes de propriedade para campo `in`
    - **Property 4: Campo `in` — pertencimento case-sensitive**
    - **Validates: Requirements 2.3**

  - [ ]* 4.3 Escrever testes de propriedade para campos `min`/`max`
    - **Property 5: Campos `min`/`max` — semântica de limites**
    - **Validates: Requirements 2.4**

  - [ ]* 4.4 Escrever testes de propriedade para campo `requer`
    - **Property 6: Campo `requer` — conjunção lógica**
    - **Validates: Requirements 2.5**

  - [x] 4.5 Implementar avaliação de expressões `max(...)`/`min(...)` 
    - `evaluate_expression`: parse de operandos, tratamento de ausentes, retorno de valor e lista de ausentes
    - _Requirements: 2.8, 16.1, 16.2_

  - [ ]* 4.6 Escrever testes de propriedade para expressões max/min
    - **Property 8: Expressões max/min — operandos parciais**
    - **Validates: Requirements 2.8**

  - [x] 4.7 Implementar modos de combinação (`melhor_posicao`, `metrica_unica`, `primeira_regra`)
    - Cada modo implementado como função independente
    - Lógica de seleção por campo `combinacao` do bloco de veículo
    - _Requirements: 2.2_

  - [ ]* 4.8 Escrever testes de propriedade para modos de combinação
    - **Property 3: Modos de combinação — semântica correta**
    - **Validates: Requirements 2.2**

  - [x] 4.9 Implementar aplicação de ajustes pós-classificação
    - Efeito (+N/-N), resultado direto, teto, teto_qualitativo
    - Ajustes qualitativos: sinalizar sem aplicar
    - Respeitar limites de escala (nunca ultrapassa primeiro/último rótulo)
    - _Requirements: 2.6, 2.7_

  - [ ]* 4.10 Escrever testes de propriedade para ajustes
    - **Property 7: Ajustes — limites de escala e tetos**
    - **Validates: Requirements 2.6, 2.7**

  - [x] 4.11 Implementar função principal `classify()` com trilha de decisão
    - Orquestrar: selecionar bloco, avaliar modo, aplicar ajustes, determinar estado, montar Verdict
    - Gerar TrailEntry para cada etapa
    - Estado: COMPLETO / ESTIMATIVA_CONSERVADORA / NAO_CLASSIFICAVEL
    - _Requirements: 2.9, 2.11, 16.1, 16.2, 16.4_

  - [ ]* 4.12 Escrever testes de propriedade para trilha de decisão
    - **Property 9: Trilha de decisão — completude**
    - **Validates: Requirements 2.9, 16.4**

  - [ ]* 4.13 Escrever testes de propriedade para fallback
    - **Property 10: Fallback — nenhuma regra satisfeita**
    - **Validates: Requirements 2.11, 2.13**

  - [ ]* 4.14 Escrever testes de propriedade para degradação conservadora
    - **Property 15: Degradação conservadora — rotulagem correta**
    - **Validates: Requirements 16.1, 16.2**

  - [ ]* 4.15 Escrever testes de propriedade para monotonicidade
    - **Property 16: Monotonicidade — operandos parciais nunca superestimam**
    - **Validates: Requirements 16.5**

- [x] 5. Checkpoint — Motor de regras funcional com fixtures sintéticas
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Validação de schema e resolução de métricas
  - [x] 6.1 Implementar validação de arquivos JSON de área contra `schema/area.schema.json`
    - Usar `jsonschema` para validação
    - Rejeitar carregamento com mensagem indicando campo inválido
    - _Requirements: 2.12_

  - [ ]* 6.2 Escrever testes de propriedade para validação de schema
    - **Property 11: Validação de schema — rejeição de JSON inválido**
    - **Validates: Requirements 2.12**

  - [x] 6.3 Implementar resolução de métricas via `sources.yml`
    - Carregar sources.yml, validar que toda métrica em areas/*.json tem pelo menos uma fonte em `provides`
    - Rejeitar carregamento com mensagem indicando métrica órfã
    - _Requirements: 13.2, 13.5, 13.6, 13.7_

  - [ ]* 6.4 Escrever testes de propriedade para resolução de métricas
    - **Property 12: Resolução de métricas — completude**
    - **Validates: Requirements 13.2, 13.5, 13.6, 13.7**

- [x] 7. Testes de integração do motor com regras reais (Área 02 e Área 27)
  - [x] 7.1 Escrever testes unitários para Área 02 — Computação
    - journalArticle com percentis conhecidos → estratos esperados
    - conferencePaper com h5 conhecidos → estratos esperados
    - book/bookSection → NAO_CLASSIFICAVEL
    - Ajustes qualitativos SBC → apenas sinalizados, teto_qualitativo A3
    - Status experimental → indicação no veredito
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

  - [x] 7.2 Escrever testes unitários para Área 27 — Administração
    - melhor_posicao com múltiplas métricas → melhor estrato
    - Ajuste SciELO: R→B, F→R, B sem ajuste, MB sem ajuste
    - SPELL + SciELO cumulativo → B
    - conferencePaper/book/bookSection → NAO_CLASSIFICAVEL
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 8. Gerador de snapshots
  - [x] 8.1 Implementar `pipeline/snapshot.py`
    - Pré-calcular vereditos para todos os veículos na tabela
    - Gerar JSON conforme `schema/snapshot.schema.json`
    - Nome do arquivo: `area{codigo:02d}-{data_sem_dia}.json`
    - Funcionar com zero veículos (snapshot vazio mas válido)
    - _Requirements: 15.1_

  - [ ]* 8.2 Escrever testes de propriedade para pipeline com subconjunto de fontes
    - **Property 13: Pipeline com subconjunto arbitrário de fontes**
    - **Validates: Requirements 15.1, 15.7**

  - [ ]* 8.3 Escrever testes de propriedade para invariante de soma do relatório
    - **Property 18: Relatório de cobertura — invariante de soma**
    - **Validates: Requirements 1.8**

- [x] 9. Checkpoint — Pipeline gera snapshots válidos com dados sintéticos
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Plugin Zotero 7 com snapshots mockados
  - [x] 10.1 Criar esqueleto do plugin (`plugin/manifest.json`, `plugin/src/index.js`)
    - Bootstrap do plugin Zotero 7
    - Estrutura de diretórios conforme design
    - _Requirements: 6.7, 6.8_

  - [x] 10.2 Implementar `plugin/src/snapshot-loader.js`
    - Leitura de snapshots do diretório de dados local
    - Validação contra schema
    - Detecção de obsolescência (> 180 dias → aviso)
    - Sem acesso a rede
    - _Requirements: 6.5, 6.7_

  - [x] 10.3 Implementar `plugin/src/evaluator.js`
    - Busca de veredito pré-calculado por ISSN no snapshot
    - Tratamento de item sem ISSN → NAO_CLASSIFICAVEL
    - Tratamento de tipo não definido → fallback do bloco
    - _Requirements: 6.6_

  - [x] 10.4 Implementar `plugin/src/columns.js`
    - Registrar colunas via `ItemTreeManager.registerColumns`
    - Uma coluna por área ativa
    - Exibir estrato com indicação de estado
    - _Requirements: 6.1_

  - [x] 10.5 Implementar `plugin/src/panel.js`
    - Registrar seção via `ItemPaneManager.registerSection`
    - Exibir: veredito, trilha de decisão, métricas-fonte, Qualis histórico
    - Três estados visuais distintos (COMPLETO, ESTIMATIVA_CONSERVADORA, NAO_CLASSIFICAVEL)
    - _Requirements: 6.2, 16.3_

  - [x] 10.6 Implementar `plugin/src/tagger.js`
    - Ação em lote de tagging com prefixo `Qualis:<Área>:<Estrato>`
    - Substituir tag anterior para mesma área
    - _Requirements: 6.4_

  - [x] 10.7 Implementar `plugin/src/preferences.js`
    - Seletor de áreas (múltiplas simultâneas)
    - Configuração de limiar de obsolescência
    - _Requirements: 6.3_

  - [x] 10.8 Implementar exibição de Qualis histórico no painel
    - Seção distinta com rótulo de ciclo ("Histórico 2021-2024" ou "Qualis Eventos 2025")
    - Omitir seção se snapshot histórico ausente
    - Nunca mesclar com classificação corrente
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 10.9 Escrever testes de propriedade para isolamento de dados históricos
    - **Property 17: Isolamento de dados históricos**
    - **Validates: Requirements 5.3**

  - [ ]* 10.10 Escrever testes unitários do plugin
    - test_evaluator.js: busca por ISSN, item sem ISSN, tipo não definido
    - test_columns.js: registro de colunas por área
    - test_tagger.js: aplicação/substituição de tags
    - _Requirements: 6.1, 6.2, 6.4, 6.6_

- [x] 11. Checkpoint — Plugin funcional com snapshots mockados
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Interface de parser e comando de onboarding
  - [x] 12.1 Implementar `pipeline/onboard.py` — comando `status`
    - Listar fontes de sources.yml com estado (carregada/pendente)
    - _Requirements: 15.2_

  - [x] 12.2 Implementar `pipeline/onboard.py` — comando `next`
    - Ordenar fontes pendentes por número de métricas novas (decrescente)
    - _Requirements: 15.3_

  - [x] 12.3 Implementar `pipeline/onboard.py` — comando `add <id>`
    - Orquestrar: carregar parser, parse, validar schema, merge na tabela, gerar snapshot
    - Atomicidade: falha aborta sem modificar tabela/snapshot
    - Gerar diff de ISSNs que mudaram de estrato
    - _Requirements: 15.4, 15.5, 15.6_

  - [ ]* 12.4 Escrever testes de propriedade para atomicidade do onboard
    - **Property 14: Atomicidade do onboard — falha não modifica estado**
    - **Validates: Requirements 15.5**

  - [ ]* 12.5 Escrever teste de integração para `onboard.py add` com parser mock
    - End-to-end: parser mock → tabela → snapshot → diff
    - _Requirements: 15.4, 15.6_

- [x] 13. Checkpoint — Onboarding funcional com parser mock
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Primeiro parser real: SJR
  - [x] 14.1 Implementar `pipeline/parsers/parser_sjr.py`
    - Implementar interface SourceParser
    - source_id: "sjr", provides: ["sjr_quartil", "sjr_valor"]
    - Parse de CSV com separador ";" e decimal ","
    - Extrair ISSN, quartil e valor SJR
    - Testar com amostra em `docs/fontes/scimagojr 2025.csv`
    - _Requirements: 1.6, 1.7, 8.2_

  - [ ]* 14.2 Escrever testes unitários para parser SJR
    - Registros com ISSN válido, ISSN inválido, campos ausentes
    - _Requirements: 1.6_

- [x] 15. Segundo parser: Scopus Source List
  - [x] 15.1 Implementar `pipeline/parsers/parser_scopus.py`
    - source_id: "scopus", provides: ["scopus_percentil", "scopus_quartil", "scopus_citescore"]
    - Parse de XLSX (aba 0)
    - _Requirements: 1.6, 1.7, 8.2_

  - [ ]* 15.2 Escrever testes unitários para parser Scopus
    - _Requirements: 1.6_

- [x] 16. Terceiro parser: ABDC Journal Quality List
  - [x] 16.1 Implementar `pipeline/parsers/parser_abdc.py`
    - source_id: "abdc", provides: ["abdc_rating"]
    - Parse de XLSX, fonte restrita (exige config/local.yml)
    - _Requirements: 1.6, 1.7, 8.3, 8.5_

  - [ ]* 16.2 Escrever testes unitários para parser ABDC
    - _Requirements: 1.6_

- [x] 17. Quarto parser: Qualis Histórico
  - [x] 17.1 Implementar parser para classificações Qualis publicadas (2021-2024)
    - Parse de XLSX da lista oficial (`classificações_publicadas_todas_as_areas_avaliacao*.xlsx`)
    - Gerar snapshot histórico separado conforme formato do design
    - _Requirements: 5.1, 5.3_

  - [ ]* 17.2 Escrever testes unitários para parser Qualis Histórico
    - Verificar separação de ciclos, campo de ciclo de origem
    - _Requirements: 5.1, 5.3_

- [x] 18. Quinto parser: SPELL
  - [x] 18.1 Implementar `pipeline/parsers/parser_spell.py`
    - source_id: "spell", provides: ["spell_faixa", "spell_fator_impacto"]
    - Parse de XLS
    - _Requirements: 1.6, 1.7_

  - [ ]* 18.2 Escrever testes unitários para parser SPELL
    - _Requirements: 1.6_

- [x] 19. Checkpoint — Parsers implementados e integrados
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 20. Relatório de cobertura e enriquecimento
  - [x] 20.1 Implementar relatório de cobertura por fonte
    - Total processados, resolvidos, não-resolvidos por fonte
    - _Requirements: 1.8_

  - [x] 20.2 Implementar enriquecimento por DOI (Crossref/OpenAlex fallback)
    - Timeout 10s por requisição, máx 3 tentativas por serviço
    - Fallback para busca por título normalizado
    - Registrar item não-resolvido com motivo detalhado
    - _Requirements: 1.3, 1.4, 1.5_

- [x] 21. Exportação de Anexos (Área 02)
  - [x] 21.1 Implementar geração de Anexos 3 e 4 em formato XLSX
    - Estrutura de colunas/cabeçalhos/ordenação idêntica ao template oficial
    - Título byte-a-byte conforme fonte canônica
    - Itens excedentes de 4N marcados com indicador visual
    - NAO_CLASSIFICAVEL/NAO_CONSIDERADO no campo de estrato
    - Nota de rodapé sobre autoria múltipla
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 21.2 Escrever teste de integração para exportação de Anexos
    - Comparação estrutural célula-a-célula com template
    - _Requirements: 14.1_

- [x] 22. GitHub Actions — Atualização automatizada
  - [x] 22.1 Criar `.github/workflows/update-sources.yml`
    - Job semanal (cron configurável)
    - Baixar fontes `livre` + `auto` de sources.yml com timeout 120s/fonte
    - Gerar diff legível se houver mudança
    - Abrir PR para revisão humana (nunca publicar automaticamente)
    - Se parser falha → abrir issue e abortar
    - Se fonte indisponível → registrar na issue, prosseguir com demais
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x] 22.2 Criar `.github/workflows/watch-upstream.yml`
    - Job mensal
    - Verificar ETag/Last-Modified de fontes e documentos normativos
    - Fonte livre alterada → PR com diff
    - Fonte restrita alterada → issue `acao-manual`
    - Documento normativo alterado → issue `severidade-alta`
    - URL com erro persistente (2 meses) → issue `fonte-inacessivel`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 23. Enforcement de fronteira de redistribuição
  - [x] 23.1 Implementar validação CI/pre-commit para fontes restritas
    - Fontes com `licenca: restrita` em sources.yml não podem ter dados rastreados no git
    - Falhar com mensagem indicando arquivo e fonte violada
    - Validar que métricas em areas/*.json permanecem resolvíveis após mudanças em sources.yml
    - _Requirements: 13.4, 13.7_

- [x] 24. Documentação
  - [x] 24.1 Criar `LIMITATIONS.md`
    - Seções obrigatórias: "Natureza não-oficial", "Conteúdos não automatizáveis", "Limites do matching por ISSN", "Defasagem temporal dos dados", "Ressalva sobre Qualis histórico", "Falsos positivos conhecidos"
    - Campo "Última atualização" no topo
    - Redação sem qualificadores subjetivos
    - _Requirements: 10.1, 10.4, 10.5_

  - [x] 24.2 Criar `README.md` principal
    - Estilo referência: docs/referencia/README-MDBundle.md
    - Corpo em inglês com seção Português após separador ---
    - Estrutura completa: H1, tagline, badges, About, Features, How it works, Installation, Usage, Supported Areas, Data Provenance, Contributing an Area, Limitations, Citation
    - _Requirements: 11.1, 11.2, 11.3, 12.1, 12.2_

  - [x] 24.3 Criar `CONTRIBUTING.md`
    - Guia para contribuir com nova área (adicionar JSON + PR)
    - Guia para contribuir com novo parser (implementar interface + PR)
    - Política: um parser por PR, nunca agrupar
    - _Requirements: 11.2_

  - [x] 24.4 Criar `LICENSE` (MIT) e arquivos de repositório
    - Criar arquivo `LICENSE` MIT na raiz (badge já referencia MIT — o arquivo DEVE existir)
    - Criar `.github/ISSUE_TEMPLATE/bug_report.md` e `.github/ISSUE_TEMPLATE/feature_request.md`
    - Criar `plugin/src/locale/en-US/messages.ftl` e `plugin/src/locale/pt-BR/messages.ftl` (mínimo)
    - _Requirements: 11.2, 12.1_

- [x] 25. Checkpoint final — Todos os testes passam, documentação completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (18 properties)
- Unit tests validate specific examples and edge cases
- A ordenação respeita R15: motor + testes sintéticos → plugin mockado → onboarding → parsers um a um
- Um parser por PR. Nunca agrupar parsers no mesmo PR.
- Fixtures de teste são SINTÉTICAS. Jamais apresentadas como dados reais.
- O snapshot schema (tarefa 1.2) é criado cedo pois é o contrato entre pipeline e plugin.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 4, "tasks": ["4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "4.4", "4.5"] },
    { "id": 6, "tasks": ["4.6", "4.7"] },
    { "id": 7, "tasks": ["4.8", "4.9"] },
    { "id": 8, "tasks": ["4.10", "4.11"] },
    { "id": 9, "tasks": ["4.12", "4.13", "4.14", "4.15"] },
    { "id": 10, "tasks": ["6.1", "6.3"] },
    { "id": 11, "tasks": ["6.2", "6.4"] },
    { "id": 12, "tasks": ["7.1", "7.2", "8.1"] },
    { "id": 13, "tasks": ["8.2", "8.3"] },
    { "id": 14, "tasks": ["10.1"] },
    { "id": 15, "tasks": ["10.2", "10.3"] },
    { "id": 16, "tasks": ["10.4", "10.5", "10.6", "10.7"] },
    { "id": 17, "tasks": ["10.8"] },
    { "id": 18, "tasks": ["10.9", "10.10"] },
    { "id": 19, "tasks": ["12.1", "12.2"] },
    { "id": 20, "tasks": ["12.3"] },
    { "id": 21, "tasks": ["12.4", "12.5"] },
    { "id": 22, "tasks": ["14.1"] },
    { "id": 23, "tasks": ["14.2"] },
    { "id": 24, "tasks": ["15.1"] },
    { "id": 25, "tasks": ["15.2"] },
    { "id": 26, "tasks": ["16.1"] },
    { "id": 27, "tasks": ["16.2"] },
    { "id": 28, "tasks": ["17.1"] },
    { "id": 29, "tasks": ["17.2"] },
    { "id": 30, "tasks": ["18.1"] },
    { "id": 31, "tasks": ["18.2"] },
    { "id": 32, "tasks": ["20.1", "20.2"] },
    { "id": 33, "tasks": ["21.1"] },
    { "id": 34, "tasks": ["21.2"] },
    { "id": 35, "tasks": ["22.1", "22.2", "23.1"] },
    { "id": 36, "tasks": ["24.1", "24.2", "24.3", "24.4"] }
  ]
}
```
