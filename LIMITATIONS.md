# Limitações

> **Última atualização:** 2025-07-27

---

## Natureza não-oficial

Este projeto NÃO é oficial da CAPES, do MEC nem de qualquer órgão governamental. O classificador reproduz as regras publicadas nas fichas de avaliação e no referencial para o novo Qualis, porém não possui vínculo institucional.

Em caso de divergência entre o resultado desta ferramenta e a ficha oficial da área na Plataforma Sucupira, a ficha oficial prevalece.

O resultado exibido pelo plugin é uma estimativa automatizada. Ele não substitui a consulta ao sistema oficial de classificação.

---

## Conteúdos não automatizáveis

Os seguintes critérios exigem avaliação humana e NÃO são computados por esta ferramenta:

- **FWCI (Field-Weighted Citation Impact)** — utilizado pela Área 02 (Ciência da Computação) como métrica complementar. O FWCI requer acesso institucional ao SciVal/Scopus e não está disponível em fontes abertas.
- **Aderência à área** — a verificação de que um periódico ou evento pertence ao escopo temático de uma área é qualitativa e depende de deliberação do comitê.
- **Artigos retratados** — a identificação de retratações exige consulta a bases externas (Retraction Watch) e não é integrada ao pipeline.
- **Elegibilidade de ajustes qualitativos** — ajustes como "evento Top-10 SBC" ou "evento nacional com tradição ≥ 20 anos" dependem de listas curadas que não possuem formato padronizado para ingestão automática.
- **Livros e capítulos de livro** — as fichas de área definem critérios específicos para livros (editora, selo, avaliação por pares) que não são passíveis de automação via metadados bibliográficos.
- **Produção técnica** — patentes, softwares e demais produções técnicas seguem critérios de avaliação distintos, não cobertos por este sistema.

---

## Limites do matching por ISSN

A identificação de periódicos depende da convergência entre o ISSN informado nos metadados do item e o ISSN presente nas tabelas de classificação.

- A resolução para ISSN-L depende da tabela oficial mantida pelo ISSN International Centre. Periódicos não listados nessa tabela não são resolvidos.
- Itens cujo ISSN está ausente ou incorreto nos metadados do Zotero dependem de enriquecimento por DOI ou título para serem classificados. Sem esse enriquecimento, o item recebe status `NAO_ENCONTRADO`.
- Eventos (conference papers) são identificados por sigla, não por ISSN. A ausência de um identificador padronizado impede matching automático contra tabelas de classificação que não incluam a sigla exata.

---

## Defasagem temporal dos dados

O veredito de classificação reflete o snapshot de dados indicado no campo `data_snapshot` do arquivo de snapshot. Ele NÃO reflete atualizações posteriores a essa data.

- **SJR (Scimago Journal Rank)** — atualizado anualmente. O pipeline utiliza o CSV público do ano indicado no snapshot.
- **JCR (Journal Citation Reports)** — requer download manual pelo mantenedor. A versão incorporada é a indicada no snapshot.
- **Qualis Periódicos 2021-2024** — dados estáticos do ciclo encerrado. Não recebem atualizações.
- **Lista de Eventos CAPES 2025** — dados estáticos publicados pela Portaria 109/2025. Não recebem atualizações.
- **Google Scholar h5-index** — extraído manualmente. A versão utilizada é a indicada no snapshot.

O usuário DEVE verificar a data do snapshot antes de utilizar os resultados para decisões acadêmicas.

---

## Ressalva sobre Qualis histórico

O Qualis Periódicos 2021-2024 e a Lista de Eventos 2025 representam o histórico de um ciclo de avaliação encerrado. Esses dados NÃO possuem validade para a avaliação quadrienal 2025-2028.

O novo referencial de avaliação (2025-2028) adota critérios, escalas e métricas diferentes do Qualis anterior. Os dois sistemas NÃO são equivalentes e NÃO são comparáveis diretamente.

A presença dos dados históricos neste sistema serve exclusivamente como referência contextual. O estrato obtido via Qualis histórico NÃO indica a classificação futura do veículo no novo ciclo.

---

## Falsos positivos conhecidos

Nenhum falso positivo registrado até o momento.

Quando identificado, cada entrada nesta seção conterá:
- Descrição do caso (veículo ou padrão afetado)
- Comportamento observado versus esperado
- Status: aberto ou resolvido (com referência ao PR de correção)
