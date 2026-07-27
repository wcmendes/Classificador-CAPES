# Requirements Document

## Introduction

Sistema open-source de classificação de produções bibliográficas do Zotero segundo os critérios CAPES para o ciclo 2025-2028, por Área de Avaliação. O projeto é um monorepo com dois pacotes independentes: `pipeline/` (Python) — responsável por ingestão, normalização e geração de snapshots — e `plugin/` (Zotero 7, JavaScript) — que consome exclusivamente os snapshots publicados pelo pipeline, sem acesso a fontes externas.

Princípios arquiteturais invioláveis:
- Motor de regras genérico e declarativo; regras em JSON validado por schema; adicionar uma área = adicionar um arquivo.
- Snapshots imutáveis versionados por data (`area02-2026-06.json`). Jamais um arquivo `latest` mutável.
- Todo veredito carrega a data da fonte que o produziu.
- O sistema nasce com ZERO fontes carregadas e cresce uma por vez.

## Glossary

- **Pipeline**: Pacote Python (`pipeline/`) que realiza ingestão, normalização e publicação de snapshots.
- **Plugin**: Extensão para Zotero 7 (`plugin/`, JavaScript) que consome snapshots e apresenta vereditos ao usuário.
- **Motor_de_Regras**: Componente do Pipeline que interpreta arquivos `areas/*.json` conforme `schema/area.schema.json`.
- **Snapshot**: Arquivo JSON imutável contendo a tabela normalizada de veículos para uma área em uma data específica.
- **Veículo**: Periódico ou evento científico passível de classificação.
- **Veredito**: Resultado da classificação de um item, incluindo estrato, trilha de decisão e data da fonte.
- **Trilha_de_Decisão**: Registro completo de qual métrica, qual regra e quais ajustes produziram o veredito.
- **Tabela_de_Veículos**: Estrutura normalizada indexada por ISSN normalizado, contendo métricas de todas as fontes.
- **ISSN-L**: ISSN de ligação que unifica as variantes impressa e eletrônica de um mesmo título.
- **Estrato**: Classificação final de um veículo na escala da área (ex: A1..A8, MB/B/R/F/I).
- **Ajuste_Qualitativo**: Modificação do estrato que exige julgamento humano; o Motor apenas sinaliza elegibilidade.
- **NAO_CLASSIFICAVEL**: Estado indicando que faltam dados para classificar o item.
- **NAO_CONSIDERADO**: Estado indicando que a área explicitamente descarta o tipo de item.
- **Estimativa_Conservadora**: Veredito calculado com operandos parciais de uma expressão `max(a,b)`, rotulado como tal.
- **Fonte**: Base de dados bibliométrica (SJR, Scopus, JCR, ABDC, ABS, SPELL, SciELO, Crossref, OpenAlex).
- **Métrica**: Indicador derivado de uma ou mais fontes (ex: `sjr_quartil`, `wos_percentil`, `h5_google_scholar`).
- **sources.yml**: Registro global (Camada 1) de todas as fontes conhecidas pelo sistema.
- **Onboarding**: Processo incremental de adicionar fontes ao sistema via `onboard.py`.

## Requirements

### Requisito 1: Pipeline de Ingestão e Normalização

**User Story:** Como pesquisador, quero que o pipeline normalize múltiplas bases bibliométricas em uma tabela única de veículos, para que o motor de regras tenha dados consistentes independente da fonte original.

#### Critérios de Aceitação

1. QUANDO um parser processa uma base, O Pipeline DEVE produzir registros na Tabela_de_Veículos indexados por ISSN-L normalizado (formato `XXXX-XXXX`, 8 dígitos com dígito verificador válido conforme algoritmo ISSN).
2. QUANDO um título possui ISSN impresso e eletrônico distintos, O Pipeline DEVE convergir ambos para o mesmo ISSN-L usando a tabela oficial ISSN-L. SE o ISSN não consta na tabela oficial ISSN-L, ENTÃO O Pipeline DEVE utilizar o próprio ISSN válido como chave e registrar um aviso de convergência pendente.
3. QUANDO o ISSN está ausente ou inválido (ausente, com menos de 8 dígitos, ou com dígito verificador incorreto) em um registro da base, O Pipeline DEVE buscar enriquecimento via DOI usando Crossref ou OpenAlex como fallback, respeitando um timeout de 10 segundos por requisição e no máximo 3 tentativas por serviço.
4. QUANDO o enriquecimento por DOI também falha, O Pipeline DEVE realizar busca por título normalizado (lowercase, sem acentos, sem pontuação, espaços colapsados) como segundo fallback.
5. SE nenhuma estratégia de resolução (ISSN, DOI, título) identifica o veículo, ENTÃO O Pipeline DEVE registrar o item como não-resolvido incluindo: a fonte de origem, o identificador original tentado, a estratégia que falhou e a razão da falha (ex: ISSN ausente, DOI não encontrado no Crossref, título sem correspondência), sem inventar um mapeamento.
6. O Pipeline DEVE implementar uma interface de parser que toda fonte cumpre, expondo no mínimo: um identificador da fonte, a lista de métricas que a fonte fornece (campo `provides`) e um método de extração que retorna registros com ISSN e valores de métricas.
7. QUANDO uma nova fonte é adicionada via `onboard.py add`, O Pipeline DEVE integrar as métricas da fonte à Tabela_de_Veículos sem exigir modificação de código do motor.
8. QUANDO o Pipeline conclui o processamento de todas as fontes configuradas, O Pipeline DEVE gerar um relatório de cobertura indicando, por fonte: total de registros processados, total de registros resolvidos e total de registros não-resolvidos.

### Requisito 2: Motor de Regras Declarativo

**User Story:** Como mantenedor, quero que toda lógica de classificação esteja em arquivos JSON validados por schema, para que adicionar ou corrigir uma área nunca exija alteração de código.

#### Critérios de Aceitação

1. O Motor_de_Regras DEVE interpretar arquivos conformes a `schema/area.schema.json` sem lógica hard-coded por área.
2. O Motor_de_Regras DEVE suportar os modos de combinação: `melhor_posicao` (avalia todas as regras e retorna o rótulo de melhor posição na escala ordenada), `metrica_unica` (uma métrica contínua determina o estrato por faixas) e `primeira_regra` (avalia as regras na ordem declarada e retorna o resultado da primeira que for satisfeita).
3. QUANDO uma regra usa o campo `in`, O Motor_de_Regras DEVE verificar pertencimento a um conjunto discreto de valores, usando comparação case-sensitive e tipo-exata conforme declarado no array.
4. QUANDO uma regra usa os campos `min` e/ou `max`, O Motor_de_Regras DEVE avaliar a métrica contra limites contínuos (min inclusivo, max exclusivo).
5. QUANDO uma regra possui o campo `requer`, O Motor_de_Regras DEVE validar que todas as condições adicionais listadas são verdadeiras (conjunção lógica) antes de considerar a regra satisfeita.
6. QUANDO ajustes pós-classificação são declarados, O Motor_de_Regras DEVE aplicá-los na ordem declarada do array `ajustes`, respeitando o campo `efeito` (deslocamento em níveis na escala ordenada, limitado ao primeiro e último rótulo da escala), `resultado` (atribuição direta de rótulo, ignorando a classificação base) e `teto` (o rótulo resultante não pode ser melhor que o valor de `teto`).
7. QUANDO um ajuste é marcado como `qualitativo: true`, O Motor_de_Regras DEVE respeitar o `teto_qualitativo` do bloco de veículo, impedindo que o rótulo resultante seja melhor que esse limite na escala ordenada.
8. QUANDO o campo `metrica` contém uma expressão `max(...)` ou `min(...)`, O Motor_de_Regras DEVE avaliar respectivamente o máximo ou o mínimo entre os operandos nomeados, ignorando operandos cujo valor não esteja disponível.
9. O Motor_de_Regras DEVE gerar uma Trilha_de_Decisão para cada veredito, contendo: métrica utilizada (nome e valor numérico ou categórico), regra ativada (com limiares aplicados), ajustes aplicados ou sinalizados (com efeito calculado) e fonte/data de cada métrica consumida.
10. O Motor_de_Regras NÃO DEVE conter limiares, acrônimos de fontes nem rótulos de escala em código-fonte; esses valores existem exclusivamente nos arquivos JSON de área.
11. IF nenhuma regra do bloco de veículo for satisfeita, THEN O Motor_de_Regras DEVE retornar o valor declarado no campo `fallback` do bloco (`NAO_CLASSIFICAVEL`, `NAO_CONSIDERADO` ou `pior_rotulo`) e registrar na Trilha_de_Decisão que nenhuma regra foi ativada.
12. IF um arquivo JSON de área não for conforme a `schema/area.schema.json`, THEN O Motor_de_Regras DEVE rejeitar o carregamento do arquivo, indicar o erro de validação com a localização do campo inválido, e não processar classificações para essa área até que o arquivo seja corrigido.
13. IF uma métrica necessária para avaliação de regra não estiver disponível para o item sob classificação, THEN O Motor_de_Regras DEVE considerar essa regra como não satisfeita e registrar na Trilha_de_Decisão que a métrica estava ausente.

### Requisito 3: Área 27 — Administração

**User Story:** Como pesquisador de Administração, quero que o sistema classifique periódicos conforme a ficha da Área 27 (ciclo 2025-2028), para obter vereditos compatíveis com a avaliação CAPES.

#### Critérios de Aceitação

1. QUANDO o Motor_de_Regras carrega `areas/area27-administracao.json`, O Motor_de_Regras DEVE avaliar todas as regras aplicáveis ao periódico para journalArticle usando as métricas `abdc_rating`, `abs_rating`, `jcr_quartil`, `sjr_quartil` e `spell_faixa`, e atribuir o estrato de maior valor conforme a ordem da escala (MB > B > R > F > I).
2. QUANDO o Motor_de_Regras determina o estrato base de um periódico indexado no SciELO Brasil, O Motor_de_Regras DEVE elevar o estrato em exatamente 1 posição na escala (ex.: R → B, F → R), sem ultrapassar o teto B; se o estrato base já for B ou MB, o ajuste não se aplica.
3. QUANDO a regra SPELL possui campo `requer: ["indexado_scielo_br"]`, O Motor_de_Regras DEVE exigir as duas condições cumulativamente (SPELL décil superior E indexação SciELO Brasil) para atribuir estrato B.
4. IF nenhuma regra é satisfeita para um periódico do tipo journalArticle, THEN O Motor_de_Regras DEVE retornar o veredito NAO_CLASSIFICAVEL sem atribuir estrato numérico.
5. O Motor_de_Regras DEVE utilizar a escala de 5 rótulos com pontuação fixa: MB (8 pontos), B (4 pontos), R (2 pontos), F (1 ponto), I (0 pontos).
6. IF o tipo do item é conferencePaper, book ou bookSection, THEN O Motor_de_Regras DEVE retornar NAO_CLASSIFICAVEL, sem inferir estrato aproximado.
7. WHILE o campo `status` do arquivo area27-administracao.json for "experimental", O Motor_de_Regras DEVE exibir junto ao veredito uma indicação de que a classificação ainda não foi validada contra a ficha oficial.
8. [INCERTO — VERIFICAR NA FICHA] As faixas SPELL codificadas como `10_a_40` para R e `40_a_70` para F foram inferidas de fonte não-oficial. Confirmar valores na ficha antes de mudar status para `validada`.
9. [INCERTO — VERIFICAR NA FICHA] O rótulo I (Insuficiente) não aparece explicitamente no Quadro 1 da ficha. Confirmar se I é definido pela área ou é apenas ausência de classificação.

### Requisito 4: Área 02 — Computação

**User Story:** Como pesquisador de Computação, quero que o sistema classifique periódicos e eventos conforme a ficha da Área 02 (ciclo 2025-2028), para obter vereditos com a escala de 8 níveis utilizada pela área.

#### Critérios de Aceitação

1. QUANDO o Motor_de_Regras carrega `areas/area02-computacao.json`, O Motor_de_Regras DEVE utilizar combinação `metrica_unica` para journalArticle com a expressão `max(wos_percentil, scopus_percentil)`.
2. O Motor_de_Regras DEVE mapear percentis a estratos usando limiares contínuos: A1 ≥ 87.5, A2 ∈ [75, 87.5), A3 ∈ [62.5, 75), A4 ∈ [50, 62.5), A5 ∈ [37.5, 50), A6 ∈ [25, 37.5), A7 ∈ [12.5, 25), A8 ∈ [0, 12.5).
3. SE nenhuma das métricas `wos_percentil` e `scopus_percentil` estiver disponível para um journalArticle, ENTÃO O Motor_de_Regras DEVE retornar `NAO_CLASSIFICAVEL` e registrar na Trilha_de_Decisão que os dados de percentil estão ausentes.
4. QUANDO o tipo de item é `conferencePaper`, O Motor_de_Regras DEVE classificá-lo usando escala independente baseada na métrica `h5_google_scholar` com limiares: A1 ≥ 35, A2 ∈ [25, 35), A3 ∈ [20, 25), A4 ∈ [15, 20), A5 ∈ [12, 15), A6 ∈ [9, 12), A7 ∈ [6, 9), A8 ∈ [1, 6).
5. SE o tipo de item é `conferencePaper` e o valor de `h5_google_scholar` é 0 ou inexistente e nenhum ajuste qualitativo SBC é aplicável, ENTÃO O Motor_de_Regras DEVE retornar `NAO_CONSIDERADO`.
6. QUANDO um ajuste qualitativo é elegível (condições: `periodico_sbc` para journalArticle; `ce_sbc_top10`, `ce_sbc_top20`, `ce_sbc_relevante`, `evento_sbc_nacional` para conferencePaper), O Motor_de_Regras DEVE apenas SINALIZAR a elegibilidade na Trilha_de_Decisão, sem aplicar o ajuste automaticamente.
7. QUANDO ajustes qualitativos são sinalizados, O Motor_de_Regras DEVE respeitar o `teto_qualitativo` A3, impedindo que mesmo uma sinalização sugira elevação acima de A3.
8. O Motor_de_Regras DEVE utilizar a escala de 8 rótulos com pontuação: A1=1, A2=0.875, A3=0.75, A4=0.625, A5=0, A6=0, A7=0, A8=0.
9. QUANDO o tipo de item é `book` ou `bookSection`, O Motor_de_Regras DEVE retornar `NAO_CLASSIFICAVEL` (estratificação qualitativa caso a caso, não automatizável).
10. [INCERTO — VERIFICAR NA FICHA] O limite inferior A8 para eventos foi codificado como H5 ≥ 1. Confirmar tratamento de eventos com H5 exatamente 0 (se devem ser NAO_CONSIDERADO ou A8).
11. [INCERTO — VERIFICAR NA FICHA] O Documento de Área cita "Procedimento 2 recomendado pela CAPES" com um link não resolvido no PDF. Localizar URL.
12. [INCERTO — VERIFICAR NA FICHA] A lista oficial de siglas de eventos da SBC (Anexo 3) é a chave canônica de conferências. URL a localizar.

### Requisito 5: Camada Histórica Qualis

**User Story:** Como pesquisador, quero consultar a classificação Qualis histórica (2021-2024 e Eventos 2025) separadamente da classificação 2025-2028, para comparar com o novo ciclo sem confundir as duas avaliações.

#### Critérios de Aceitação

1. O Pipeline DEVE armazenar dados Qualis históricos em Snapshots separados dos Snapshots do ciclo 2025-2028, cada registro contendo um campo de ciclo de origem com valor literal ("Periódicos 2021-2024" ou "Eventos 2025").
2. O Plugin DEVE exibir a classificação histórica acompanhada de rótulo textual indicando o ciclo de origem ("Histórico 2021-2024" ou "Qualis Eventos 2025"), posicionado em seção distinta da classificação 2025-2028 no painel de item.
3. O Motor_de_Regras NÃO DEVE mesclar dados históricos com a classificação corrente em nenhuma circunstância; dados históricos não participam do cálculo de veredito do ciclo 2025-2028.
4. IF um item possui Qualis histórico mas não possui classificação 2025-2028, THEN O Plugin DEVE exibir o estrato histórico com seu rótulo de ciclo e indicar explicitamente a ausência de classificação no ciclo corrente, sem inferir equivalência entre ciclos.
5. IF um item possui classificação 2025-2028 mas não possui Qualis histórico, THEN O Plugin DEVE exibir o veredito corrente e omitir a seção histórica sem exibir erro.
6. IF o Snapshot histórico não está disponível localmente para a área selecionada, THEN O Plugin DEVE omitir a seção de classificação histórica e indicar que dados históricos não estão carregados para aquela área.

### Requisito 6: Plugin Zotero 7

**User Story:** Como pesquisador usando Zotero, quero ver a classificação CAPES diretamente na interface do Zotero com detalhes completos de como o veredito foi calculado, para tomar decisões informadas sobre onde publicar.

#### Critérios de Aceitação

1. O Plugin DEVE registrar uma coluna customizada por área ativa via `ItemTreeManager.registerColumns`, exibindo o estrato do item; QUANDO mais de uma área está selecionada, O Plugin DEVE registrar uma coluna separada por área, identificada pelo nome da área.
2. O Plugin DEVE registrar uma seção no painel de item via `ItemPaneManager.registerSection` contendo: veredito (estrato + estado COMPLETO/ESTIMATIVA_CONSERVADORA/NAO_CLASSIFICAVEL), Trilha_de_Decisão completa, métricas-fonte utilizadas com respectivas datas e Qualis histórico com rótulo do ciclo de origem.
3. O Plugin DEVE oferecer um seletor de áreas nas preferências, permitindo múltiplas áreas simultâneas ativas dentre as áreas disponíveis nos Snapshots locais.
4. O Plugin DEVE oferecer uma ação em lote que aplica tags com prefixo fixo identificável (ex: `Qualis:<Área>:<Estrato>`) aos itens com base no estrato classificado; QUANDO um item já possui tag de estrato anterior para a mesma área, O Plugin DEVE substituir a tag existente pela nova antes de aplicar.
5. QUANDO a data do Snapshot é anterior a um limiar configurável (padrão: 180 dias), O Plugin DEVE exibir um aviso de obsolescência indicando a idade dos dados em dias.
6. QUANDO um item não pode ser classificado, O Plugin DEVE exibir explicitamente o estado NAO_CLASSIFICAVEL (faltam dados) ou NAO_CONSIDERADO (área descarta o tipo), acompanhado do motivo extraído do campo `fallback` e da Trilha_de_Decisão.
7. O Plugin NÃO DEVE acessar fontes externas, APIs nem rede; toda informação vem exclusivamente dos Snapshots locais.
8. O Plugin NÃO DEVE utilizar localStorage nem sessionStorage do navegador para armazenamento.

### Requisito 7: Atualização Automatizada via GitHub Actions

**User Story:** Como mantenedor, quero que um job agendado baixe fontes abertas e abra PR para revisão humana, para manter os dados atualizados sem publicação automática.

#### Critérios de Aceitação

1. QUANDO o job agendado executa (semanalmente, via cron configurável no workflow), O Pipeline DEVE baixar apenas fontes marcadas como `livre` em sources.yml, aplicando um timeout de 120 segundos por fonte.
2. QUANDO os dados baixados diferem do snapshot anterior (comparação byte-a-byte do conteúdo normalizado), O Pipeline DEVE gerar um diff legível listando veículos adicionados, removidos e com métricas alteradas, e abrir um Pull Request para revisão humana.
3. QUANDO nenhuma fonte apresenta alteração em relação ao snapshot anterior, O Pipeline DEVE encerrar o job sem abrir Pull Request nem criar commits.
4. O Pipeline NÃO DEVE publicar snapshots automaticamente; a publicação requer merge humano do PR.
5. SE um parser falha com erro de lógica ou dados inválidos durante a execução do job, ENTÃO O Pipeline DEVE abrir uma issue no repositório contendo: identificador da fonte, etapa que falhou, mensagem de erro e timestamp UTC, e abortar o processo sem gerar snapshot parcial.
6. SE uma fonte não responde dentro do timeout ou retorna erro de rede, ENTÃO O Pipeline DEVE registrar a indisponibilidade na issue, prosseguir com as demais fontes disponíveis e sinalizar no PR quais fontes ficaram ausentes.
7. O Pipeline NÃO DEVE versionar dados brutos de bases licenciadas no repositório.

### Requisito 8: Registro e Aquisição de Fontes

**User Story:** Como mantenedor, quero um registro centralizado de todas as fontes bibliométricas (livres e restritas), para rastrear o que está disponível e o que falta.

#### Critérios de Aceitação

1. O Pipeline DEVE manter um arquivo `sources.yml` (Camada 1) listando todas as fontes conhecidas com campos obrigatórios: `id`, `nome`, `landing_url`, `licenca` (valores: `livre` ou `restrita`), `acquisition` (valores: `auto` ou `manual`), `provides` (lista de nomes canônicos de métricas) e `status` (valores: `ativa`, `pendente` ou `bloqueada`).
2. QUANDO uma fonte é marcada como `livre` e `auto` em sources.yml, O Pipeline DEVE ser capaz de adquiri-la automaticamente no job de atualização sem intervenção humana.
3. QUANDO uma fonte é marcada como `restrita` ou `manual`, O Pipeline DEVE exigir configuração local (`config/local.yml`, gitignored) com o caminho do arquivo; SE o override não existir, ENTÃO O Pipeline DEVE falhar com mensagem indicando qual arquivo baixar, de onde, e o comando make_sample sugerido.
4. O Pipeline DEVE registrar fontes livres conhecidas: SJR, SPELL, SciELO, Crossref, OpenAlex, tabela ISSN-L.
5. O Pipeline DEVE registrar fontes restritas conhecidas: ABDC, ABS/AJG, JCR.
6. [INCERTO — VERIFICAR NA FICHA] Fontes pendentes de localização: lista de eventos SBC com H5, percentis WoS/Scopus por periódico, Qualis Eventos 2025.

### Requisito 9: Monitoramento de Versões Upstream

**User Story:** Como mantenedor, quero ser notificado quando uma fonte ou documento normativo muda, para manter o sistema atualizado com mínimo esforço manual.

#### Critérios de Aceitação

1. QUANDO o job `watch-upstream` mensal executa, O Pipeline DEVE comparar pelo menos um indicador de versão (ETag, Last-Modified ou hash SHA-256 do conteúdo) de cada fonte em `sources.yml` que possua URL de aquisição, contra os valores armazenados na execução anterior.
2. QUANDO uma fonte livre apresenta alteração, O Pipeline DEVE abrir um Pull Request contendo o diff dos dados normalizados entre a versão anterior e a nova, referenciando o identificador da fonte e a data de detecção.
3. QUANDO uma fonte restrita apresenta alteração detectável via cabeçalhos HTTP (ETag ou Last-Modified) sem download do conteúdo, O Pipeline DEVE abrir uma issue rotulada `acao-manual` contendo: identificador da fonte, URL monitorada, valor anterior e novo do indicador alterado, e data de detecção.
4. QUANDO um documento normativo (ficha, documento de área) apresenta alteração, O Pipeline DEVE abrir uma issue rotulada `severidade-alta` contendo: identificador do documento, URL monitorada, indicador alterado e lista das áreas potencialmente afetadas.
5. SE uma URL monitorada retorna erro HTTP (4xx, 5xx) ou não responde dentro de 30 segundos, ENTÃO O Pipeline DEVE registrar a falha no log da execução e, se a falha persiste em 2 verificações consecutivas (2 meses), abrir uma issue rotulada `fonte-inacessivel` com o identificador da fonte e o código de erro.

### Requisito 10: Documento LIMITATIONS.md

**User Story:** Como usuário, quero entender claramente o que o sistema não faz e quais são suas limitações, para não tomar decisões baseadas em expectativas incorretas.

#### Critérios de Aceitação

1. O Projeto DEVE manter um arquivo `LIMITATIONS.md` na raiz do repositório contendo seções com os seguintes títulos obrigatórios: "Natureza não-oficial", "Conteúdos não automatizáveis", "Limites do matching por ISSN", "Defasagem temporal dos dados", "Ressalva sobre Qualis histórico" e "Falsos positivos conhecidos". Cada seção DEVE conter ao menos um parágrafo declarativo descrevendo a limitação em termos observáveis.
2. QUANDO um Pull Request introduz comportamento que pode gerar expectativa incorreta no usuário (novo parser com cobertura parcial, fonte com defasagem conhecida, tipo de item não suportado ou caso de matching ambíguo), O mantenedor DEVE adicionar a limitação correspondente ao LIMITATIONS.md no mesmo PR, antes do merge.
3. QUANDO um falso positivo é registrado na seção "Falsos positivos conhecidos", O Projeto DEVE incluir para cada entrada: descrição do caso (veículo ou padrão afetado), comportamento observado versus esperado, e status atual (aberto ou resolvido com referência ao PR de correção).
4. QUANDO o conteúdo de LIMITATIONS.md é alterado, O Projeto DEVE manter um campo "Última atualização" no topo do arquivo com a data da modificação mais recente no formato ISO 8601 (AAAA-MM-DD).
5. O Projeto DEVE redigir cada limitação sem qualificadores subjetivos (ex: "geralmente", "pode eventualmente", "em alguns casos") — cada sentença deve afirmar objetivamente o que o sistema não faz ou onde falha.

### Requisito 11: README.md Principal

**User Story:** Como potencial usuário ou contribuidor, quero um README claro no estilo do projeto que explique o propósito, limitações e como contribuir.

#### Critérios de Aceitação

1. O Projeto DEVE manter um `README.md` no estilo do projeto (referência: `docs/referencia/README-MDBundle.md`), com corpo principal em inglês e seção em português após separador `---`.
2. O README DEVE conter, nesta ordem: H1 com emoji + nome, tagline de uma linha, badges shields.io (Zotero, License, Platform), seletor de idioma (`English | [Português](#português)`), seção About com subseção "Why", Features em tabela, How it works com diagrama ASCII em code fence, aviso de NÃO-OFICIALIDADE em blockquote, Installation numerada, Usage com menus em árvore, Supported Areas, Data Provenance, Contributing an Area, Limitations (link para LIMITATIONS.md), Citation, seção Português.
3. O README DEVE incluir badges de licença, plataforma Zotero 7 e status de build do GitHub Actions.

### Requisito 12: Documentação em Português

**User Story:** Como pesquisador brasileiro, quero documentação em português acessível diretamente no README, para entender o projeto sem barreira de idioma.

#### Critérios de Aceitação

1. O README DEVE conter uma seção `## Português` após separador `---`, contendo no mínimo: aviso de natureza não-oficial, tabela de áreas suportadas, instruções de instalação e passo a passo para contribuir com uma nova área.
2. A seção em português DEVE replicar a estrutura da seção principal (About, Features, Installation) sem ser mera tradução automática — a linguagem deve ser natural e idiomática em pt-BR.

### Requisito 13: Configuração de Fontes em Três Camadas

**User Story:** Como mantenedor, quero separar o registro de fontes, as referências de métricas nas regras e as configurações locais, para que fontes licenciadas nunca sejam acidentalmente versionadas e que regras referenciem métricas e não fontes.

#### Critérios de Aceitação

1. O Pipeline DEVE implementar Camada 1 (`sources.yml`): registro global de fontes onde cada entrada contém, no mínimo, os campos `id` (identificador único da fonte), `nome`, `licenca` (com valor `livre` ou `restrita`) e `provides` (lista de nomes canônicos de métricas que a fonte entrega).
2. O Pipeline DEVE implementar Camada 2 (`areas/*.json`): regras que referenciam MÉTRICAS exclusivamente por nome canônico presente em pelo menos um campo `provides` de `sources.yml`, jamais por identificador de fonte ou caminho de arquivo.
3. O Pipeline DEVE implementar Camada 3 (`config/local.yml`, gitignored): overrides locais limitados a caminhos de arquivos de fontes restritas e credenciais de acesso a APIs de fontes, sem permitir redefinição de métricas ou regras de classificação.
4. O Pipeline DEVE aplicar enforcement de fronteira de redistribuição por meio de validação automatizada (pre-commit hook ou etapa de CI): fontes com campo `licenca` igual a `restrita` em `sources.yml` não podem ter seus arquivos de dados rastreados pelo controle de versão, e a validação DEVE falhar com mensagem indicando o arquivo e a fonte restrita violada.
5. QUANDO uma regra referencia uma métrica, O Motor_de_Regras DEVE resolver a fonte via campo `provides` de `sources.yml`, nunca por referência direta à fonte no JSON de área.
6. IF uma métrica referenciada em uma regra de `areas/*.json` não corresponde a nenhum campo `provides` em `sources.yml`, THEN O Pipeline DEVE rejeitar o carregamento da regra com mensagem indicando o nome canônico da métrica não resolvida e o arquivo de área de origem.
7. QUANDO `sources.yml` é modificado, O Pipeline DEVE validar que toda métrica referenciada nos arquivos de `areas/*.json` permanece resolvível por pelo menos uma fonte, e DEVE reportar métricas órfãs antes de aceitar a alteração.

### Requisito 14: Exportação de Anexos (Área 02)

**User Story:** Como coordenador de programa, quero exportar os Anexos 3 e 4 no formato oficial exato, para submeter à CAPES sem retrabalho manual.

#### Critérios de Aceitação

1. O Pipeline DEVE gerar os Anexos 3 e 4 da Área 02 em formato XLSX com estrutura de colunas, cabeçalhos e ordenação idênticos ao template oficial (docs/fontes/anexos-computacao.xlsx), de modo que uma comparação estrutural célula-a-célula entre o arquivo gerado e o template não apresente divergências de layout.
2. QUANDO um título de veículo (periódico ou evento) é exportado no Anexo, O Pipeline DEVE reproduzi-lo com identidade byte-a-byte em relação ao título registrado no arquivo de regras da área (area02-computacao.json) ou na fonte de dados canônica que o alimentou.
3. IF a produção bibliográfica de um docente excede 4N itens (onde N é o número de docentes permanentes do programa informado como parâmetro de entrada), THEN O Pipeline DEVE manter todos os itens no arquivo exportado e marcar os itens excedentes com indicador visual em coluna dedicada, sem descartar nenhum registro.
4. O Pipeline DEVE incluir, como nota de rodapé na última linha do Anexo exportado, uma ressalva informando que itens com múltiplos autores vinculados ao mesmo programa podem requerer separação de autoria para fins de contagem individual.
5. IF um item possui status NAO_CLASSIFICAVEL ou NAO_CONSIDERADO no momento da exportação, THEN O Pipeline DEVE incluí-lo no Anexo com o campo de estrato preenchido pelo status correspondente em vez de um rótulo de classificação, preservando a rastreabilidade.

### Requisito 15: Onboarding Incremental

**User Story:** Como mantenedor, quero adicionar fontes uma por vez sem quebrar o sistema, para que o projeto cresça gradualmente conforme fontes são localizadas.

#### Critérios de Aceitação

1. O Pipeline DEVE funcionar corretamente com zero fontes carregadas, retornando NAO_CLASSIFICAVEL para todos os itens e gerando snapshot válido conforme schema.
2. O Pipeline DEVE fornecer o comando `onboard.py status` listando cada fonte registrada em `sources.yml` com seu estado atual (carregada ou pendente), onde "pendente" significa registrada em `sources.yml` mas sem dados ingeridos na Tabela_de_Veículos.
3. O Pipeline DEVE fornecer o comando `onboard.py next` exibindo a lista de fontes pendentes ordenada decrescentemente pelo número de métricas declaradas no campo `provides` de `sources.yml` que ainda não possuem nenhuma fonte carregada.
4. O Pipeline DEVE fornecer o comando `onboard.py add <id>` que integra uma nova fonte executando: parse do arquivo, validação de schema dos registros produzidos, merge na Tabela_de_Veículos e geração de novo snapshot.
5. IF a validação de schema ou o parse falha durante `onboard.py add`, THEN O Pipeline DEVE abortar sem modificar a Tabela_de_Veículos nem o snapshot, e DEVE exibir mensagem indicando o motivo da falha e o número de registros rejeitados.
6. QUANDO uma fonte é adicionada com sucesso via `onboard.py add`, O Pipeline DEVE recalcular vereditos de todos os veículos que utilizam métricas providas pela nova fonte e gerar diff listando cada ISSN cujo estrato mudou, com estrato anterior e estrato novo.
7. A ordenação de tarefas no desenvolvimento NÃO DEVE depender de todas as fontes estarem presentes; o Pipeline DEVE executar parse, validação e geração de snapshot com qualquer subconjunto de fontes carregadas sem erro.

### Requisito 16: Degradação Conservadora

**User Story:** Como pesquisador, quero que o sistema calcule o melhor veredito possível mesmo com dados incompletos, sinalizando claramente quando o resultado pode ser melhor com fontes adicionais.

#### Critérios de Aceitação

1. QUANDO uma expressão `max(...)` ou combinação `melhor_posicao` possui ao menos um operando ou regra avaliável mas não todos, O Motor_de_Regras DEVE calcular o veredito com os operandos disponíveis e rotular o resultado como ESTIMATIVA_CONSERVADORA.
2. QUANDO nenhum operando de uma expressão `max(...)` está disponível e nenhuma regra de uma combinação `melhor_posicao` é avaliável para o item, O Motor_de_Regras DEVE retornar NAO_CLASSIFICAVEL.
3. O Plugin DEVE apresentar três estados visuais distintos para vereditos: COMPLETO (todos os operandos presentes), ESTIMATIVA_CONSERVADORA (operandos parciais) e NAO_CLASSIFICAVEL (nenhum dado suficiente).
4. QUANDO um veredito é rotulado como ESTIMATIVA_CONSERVADORA, A Trilha_de_Decisão DEVE listar cada métrica ausente pelo nome canônico e a fonte correspondente (conforme `provides` em sources.yml) que forneceria o operando faltante.
5. O Motor_de_Regras DEVE garantir monotonicidade: o estrato atribuído com operandos parciais DEVE ser menor ou igual ao estrato que seria atribuído com todos os operandos presentes (a adição de uma fonte ausente pode apenas manter ou elevar o estrato, nunca reduzi-lo).
