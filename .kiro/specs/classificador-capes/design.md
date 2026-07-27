# Design Document — Classificador CAPES

## Overview

O Classificador CAPES é um sistema open-source que classifica produções bibliográficas do Zotero segundo critérios CAPES para o ciclo 2025-2028, por Área de Avaliação. O sistema é composto por dois pacotes independentes em um monorepo:

- **`pipeline/`** (Python): ingestão de fontes bibliométricas, normalização, motor de regras declarativo e geração de snapshots imutáveis.
- **`plugin/`** (Zotero 7, JavaScript): consome snapshots locais e apresenta vereditos na interface do Zotero.

### Princípios Arquiteturais

1. **Motor declarativo**: toda lógica de classificação vive em JSON (`areas/*.json`) validado por `schema/area.schema.json`. Zero regras em código.
2. **Snapshots imutáveis**: versionados por data (`area02-2026-06.json`). Nunca existe `latest`.
3. **Crescimento incremental**: nasce com zero fontes, cresce uma por vez sem quebrar.
4. **Separação de interesses**: regras referenciam MÉTRICAS, nunca fontes diretamente.
5. **Degradação conservadora**: dados parciais produzem estimativas que nunca superestimam.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MONOREPO                                       │
│                                                                         │
│  ┌───────────────────────────────────┐   ┌───────────────────────────┐  │
│  │         pipeline/ (Python)        │   │   plugin/ (Zotero 7, JS)  │  │
│  │                                   │   │                           │  │
│  │  ┌─────────┐  ┌──────────────┐   │   │  ┌─────────────────────┐  │  │
│  │  │ Parsers │─▶│ Tabela de    │   │   │  │ Leitor de Snapshots │  │  │
│  │  │ (1 por  │  │ Veículos     │   │   │  └──────────┬──────────┘  │  │
│  │  │  fonte) │  │ (ISSN-L key) │   │   │             │             │  │
│  │  └─────────┘  └──────┬───────┘   │   │  ┌──────────▼──────────┐  │  │
│  │                       │           │   │  │ Avaliador Local     │  │  │
│  │  ┌────────────────────▼────────┐  │   │  │ (aplica regras do   │  │  │
│  │  │    Motor de Regras          │  │   │  │  snapshot ao item)  │  │  │
│  │  │ (interpreta areas/*.json)   │  │   │  └──────────┬──────────┘  │  │
│  │  └────────────────────┬────────┘  │   │             │             │  │
│  │                       │           │   │  ┌──────────▼──────────┐  │  │
│  │  ┌────────────────────▼────────┐  │   │  │ UI: Colunas +      │  │  │
│  │  │  Gerador de Snapshots       │  │   │  │ Painel + Tags      │  │  │
│  │  │  (JSON imutável por data)   │  │   │  └─────────────────────┘  │  │
│  │  └─────────────────────────────┘  │   │                           │  │
│  └───────────────────────────────────┘   └───────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ schema/              │  │ areas/            │  │ config/          │  │
│  │  area.schema.json    │  │  area02-*.json    │  │  local.yml       │  │
│  │                      │  │  area27-*.json    │  │  (gitignored)    │  │
│  └──────────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    sources.yml (Camada 1)                        │   │
│  │  Registro global: id, licenca, provides[], status                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados Principal

```
  Fontes externas          Pipeline                      Plugin
  ─────────────          ──────────                    ────────
                                                        
  ┌──────────┐     ┌──────────────────┐                 
  │ SJR.csv  │────▶│ parser_sjr.py    │──┐              
  └──────────┘     └──────────────────┘  │              
  ┌──────────┐     ┌──────────────────┐  │  ┌────────┐ 
  │Scopus.xl │────▶│ parser_scopus.py │──┼─▶│Tabela  │ 
  └──────────┘     └──────────────────┘  │  │Veículos│ 
  ┌──────────┐     ┌──────────────────┐  │  └───┬────┘ 
  │ ABDC.xl  │────▶│ parser_abdc.py   │──┘      │      
  └──────────┘     └──────────────────┘         │      
                                                │      
       areas/area27-administracao.json ─────┐   │      
       areas/area02-computacao.json ────────┼───┤      
                                            │   │      
                              ┌─────────────▼───▼───┐  
                              │  Motor de Regras    │  
                              │  (genérico)         │  
                              └──────────┬──────────┘  
                                         │             
                              ┌──────────▼──────────┐       ┌───────────────┐
                              │  Snapshot Imutável   │──────▶│ Plugin Zotero │
                              │  area27-2026-07.json │       │ (offline)     │
                              └─────────────────────┘       └───────────────┘
```

## Components and Interfaces

### 1. Interface de Parser (Contrato Crítico)

Todo parser de fonte bibliométrica implementa esta interface. É o contrato mais importante do sistema — deve ser tão simples que adicionar uma fonte nova seja trivial.

```python
# pipeline/parsers/base.py
from typing import Protocol, Iterator
from dataclasses import dataclass

@dataclass
class ParsedRecord:
    """Registro produzido por um parser."""
    issn: str | None          # ISSN original (com ou sem hífen)
    issn_alt: str | None      # ISSN alternativo (impresso/eletrônico)
    doi: str | None           # DOI para enriquecimento (se disponível)
    titulo: str | None        # Título do veículo (fallback de resolução)
    metricas: dict[str, str | int | float]
    # Chaves = nomes canônicos de métricas (ex: "sjr_quartil", "scopus_percentil")
    # Valores = valor extraído da fonte, no tipo declarado pelo schema


class SourceParser(Protocol):
    """Interface que todo parser de fonte deve cumprir."""

    @property
    def source_id(self) -> str:
        """Identificador da fonte conforme sources.yml (ex: 'sjr', 'scopus')."""
        ...

    @property
    def provides(self) -> list[str]:
        """Lista de nomes canônicos de métricas que esta fonte entrega."""
        ...

    def parse(self, path: str) -> Iterator[ParsedRecord]:
        """
        Extrai registros do arquivo da fonte.
        
        Yields ParsedRecord para cada veículo encontrado.
        Não faz normalização de ISSN — isso é responsabilidade do pipeline.
        Não faz merge — apenas extrai.
        """
        ...
```

**Decisão de design**: Parsers são geradores (yield). Isso permite processar arquivos grandes sem carregar tudo em memória e facilita testes (basta gerar um ou dois registros mock).

### 2. Normalizador de ISSN

```python
# pipeline/issn.py

def normalize_issn(raw: str) -> str | None:
    """
    Normaliza ISSN para formato XXXX-XXXX.
    Retorna None se inválido (< 8 dígitos ou dígito verificador incorreto).
    """
    ...

def validate_check_digit(issn: str) -> bool:
    """Valida dígito verificador conforme algoritmo ISSN (mod 11)."""
    ...

def resolve_issn_l(issn: str, issn_l_table: dict[str, str]) -> str:
    """
    Resolve ISSN para ISSN-L usando tabela oficial.
    Se não encontrado, retorna o próprio ISSN como chave.
    """
    ...

def normalize_title(title: str) -> str:
    """
    Normaliza título: lowercase, sem acentos, sem pontuação, espaços colapsados.
    Usado como fallback de resolução quando ISSN e DOI falham.
    """
    ...
```

### 3. Tabela de Veículos

Estrutura central em memória durante o processamento do pipeline.

```python
# pipeline/vehicles.py
from dataclasses import dataclass, field

@dataclass
class MetricValue:
    """Valor de uma métrica com proveniência."""
    valor: str | int | float
    fonte_id: str          # id da fonte que forneceu (ex: "sjr")
    data_fonte: str        # data do arquivo da fonte (ISO 8601)

@dataclass
class VehicleRecord:
    """Registro completo de um veículo na tabela normalizada."""
    issn_l: str                                    # Chave primária
    titulos: list[str]                             # Títulos conhecidos
    issns: set[str]                                # Todos os ISSNs mapeados
    metricas: dict[str, MetricValue] = field(default_factory=dict)
    # Chaves = nomes canônicos de métricas
    avisos: list[str] = field(default_factory=list)
```

### 4. Motor de Regras

O motor é completamente genérico. Lê o JSON de área e aplica a lógica declarada sem conhecimento prévio de nenhuma área específica.

```python
# pipeline/engine.py
from dataclasses import dataclass

@dataclass
class Verdict:
    """Resultado completo de uma classificação."""
    estrato: str                # Rótulo final (ex: "A1", "MB", "NAO_CLASSIFICAVEL")
    estado: str                 # "COMPLETO" | "ESTIMATIVA_CONSERVADORA" | "NAO_CLASSIFICAVEL"
    trilha: list[TrailEntry]    # Trilha de decisão completa
    area: int                   # Código da área
    data_snapshot: str          # Data do snapshot que produziu este veredito

@dataclass
class TrailEntry:
    """Uma entrada na trilha de decisão."""
    etapa: str                  # "regra_avaliada" | "regra_ativada" | "ajuste" | "fallback"
    metrica: str | None         # Nome canônico da métrica
    valor: str | int | float | None  # Valor utilizado
    regra_idx: int | None       # Índice da regra no array
    resultado: str | None       # Resultado desta etapa
    fonte_id: str | None        # Fonte que forneceu o valor
    data_fonte: str | None      # Data da fonte
    nota: str | None            # Informação adicional (métrica ausente, teto aplicado, etc)


def classify(
    item_type: str,
    metricas: dict[str, MetricValue],
    area_rules: dict,          # JSON de área carregado e validado
) -> Verdict:
    """
    Classifica um item usando as regras da área.
    
    Algoritmo:
    1. Selecionar bloco de veículo por item_type
    2. Avaliar conforme modo de combinação
    3. Aplicar ajustes pós-classificação
    4. Rotular estado (COMPLETO / ESTIMATIVA_CONSERVADORA / NAO_CLASSIFICAVEL)
    5. Retornar Verdict com trilha completa
    """
    ...
```

#### Algoritmo do Motor de Regras

```
┌─────────────────────────────────────────────────────────────────────┐
│                    classify(item_type, metricas, area_rules)         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │ 1. Selecionar bloco veículo │
                │    area_rules["veiculos"]   │
                │    [item_type]              │
                └──────────────┬──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Bloco existe?       │
                    └──┬─────────────┬────┘
                       │ NÃO         │ SIM
                       ▼             ▼
              ┌────────────┐  ┌─────────────────────────────┐
              │ Retorna    │  │ 2. Avaliar conforme modo    │
              │ NAO_CLAS.  │  │    de combinação            │
              └────────────┘  └──────────────┬──────────────┘
                                             │
                    ┌────────────────────────┬┴────────────────────┐
                    │                        │                      │
                    ▼                        ▼                      ▼
         ┌──────────────────┐  ┌──────────────────────┐  ┌────────────────┐
         │ melhor_posicao   │  │ metrica_unica        │  │ primeira_regra │
         │                  │  │                      │  │                │
         │ Avalia TODAS as  │  │ Resolve expressão    │  │ Avalia regras  │
         │ regras. Coleta   │  │ (max/min). Avalia    │  │ em ordem.      │
         │ todos resultados │  │ valor contra faixas. │  │ Retorna 1º     │
         │ satisfeitos.     │  │ Retorna faixa        │  │ match.         │
         │ Retorna MELHOR   │  │ correspondente.      │  │                │
         │ na escala.       │  │                      │  │                │
         └────────┬─────────┘  └───────────┬──────────┘  └───────┬────────┘
                  │                         │                      │
                  └─────────────────────────┼──────────────────────┘
                                            │
                              ┌─────────────▼──────────────┐
                              │ 3. Estrato base definido?  │
                              └──┬──────────────────────┬──┘
                                 │ NÃO                  │ SIM
                                 ▼                      ▼
                        ┌──────────────┐   ┌───────────────────────────┐
                        │ Retorna      │   │ 4. Aplicar ajustes        │
                        │ fallback     │   │    (na ordem declarada)   │
                        └──────────────┘   └────────────┬──────────────┘
                                                        │
                                           ┌────────────▼──────────────┐
                                           │ Para cada ajuste:         │
                                           │ - Verificar condição "se" │
                                           │ - Se qualitativo=true:    │
                                           │   SINALIZAR, não aplicar  │
                                           │ - Se não-qualitativo:     │
                                           │   Aplicar efeito/resultado│
                                           │   Respeitar teto          │
                                           └────────────┬──────────────┘
                                                        │
                                           ┌────────────▼──────────────┐
                                           │ 5. Determinar estado:     │
                                           │ - Todos operandos? →      │
                                           │   COMPLETO                │
                                           │ - Parcial? →              │
                                           │   ESTIMATIVA_CONSERVADORA │
                                           │ - Nenhum? → (já tratado  │
                                           │   no passo 3)             │
                                           └────────────┬──────────────┘
                                                        │
                                           ┌────────────▼──────────────┐
                                           │ 6. Montar Verdict com     │
                                           │    trilha de decisão      │
                                           └───────────────────────────┘
```

#### Avaliação de Expressões `max(...)` / `min(...)`

```python
def evaluate_expression(expr: str, metricas: dict[str, MetricValue]) -> tuple[float | None, list[str]]:
    """
    Avalia expressão max(...) ou min(...).
    
    Retorna:
      - valor: resultado numérico ou None se nenhum operando disponível
      - ausentes: lista de nomes de métricas que não estavam disponíveis
    
    Regras:
      - Ignora operandos cujo valor não está em `metricas`
      - Se pelo menos 1 operando disponível: retorna max/min dos disponíveis
      - Se nenhum operando disponível: retorna None
    """
    # Parse: "max(wos_percentil, scopus_percentil)" → ["wos_percentil", "scopus_percentil"]
    ...
```

#### Avaliação de Regras Individuais

```python
def evaluate_rule(rule: dict, metricas: dict[str, MetricValue]) -> bool:
    """
    Avalia uma regra individual contra métricas disponíveis.
    
    Campo "in": pertencimento a conjunto (case-sensitive, tipo-exata)
    Campo "min"/"max": min inclusivo, max exclusivo
    Campo "requer": conjunção lógica de condições booleanas
    
    Se a métrica requerida não está disponível → regra não satisfeita (False)
    """
    ...
```

#### Aplicação de Ajustes

```python
def apply_adjustments(
    base_label: str,
    adjustments: list[dict],
    scale: list[str],           # Rótulos do melhor ao pior
    metricas: dict[str, MetricValue],
    teto_qualitativo: str | None,
) -> tuple[str, list[TrailEntry]]:
    """
    Aplica ajustes na ordem declarada.
    
    Tipos de ajuste:
    - "efeito": "+N" ou "-N" → desloca N posições na escala
    - "resultado": atribuição direta de rótulo
    - "teto": limite máximo do ajuste específico
    
    Se qualitativo=True:
      - NÃO aplica o ajuste
      - Registra sinalização na trilha
      - Respeita teto_qualitativo do bloco
    
    Limites:
      - Nunca ultrapassa primeiro rótulo (melhor) nem último (pior)
      - Nunca ultrapassa teto do ajuste
      - Ajustes qualitativos respeitam teto_qualitativo
    """
    ...
```

### 5. Gerador de Snapshots

O snapshot é o artefato que cruza a fronteira pipeline → plugin. É imutável, versionado por data, e contém tudo que o plugin precisa para classificar itens offline.

```python
# pipeline/snapshot.py

def generate_snapshot(
    area_rules: dict,
    vehicles: dict[str, VehicleRecord],
    snapshot_date: str,         # ISO 8601 (AAAA-MM-DD)
) -> dict:
    """
    Gera snapshot para uma área.
    
    Pré-calcula vereditos para todos os veículos na tabela
    que possuem pelo menos uma métrica relevante para a área.
    
    Nome do arquivo: area{codigo:02d}-{data_sem_dia}.json
    Exemplo: area02-2026-07.json
    """
    ...
```

### 6. Plugin Zotero 7

```
plugin/
├── manifest.json
├── prefs.js
├── src/
│   ├── index.js              # Bootstrap do plugin
│   ├── snapshot-loader.js    # Lê snapshots do diretório de dados
│   ├── evaluator.js          # Busca veredito pré-calculado por ISSN
│   ├── columns.js            # ItemTreeManager.registerColumns
│   ├── panel.js              # ItemPaneManager.registerSection
│   ├── tagger.js             # Ação em lote de tagging
│   └── preferences.js        # Seletor de áreas, limiar obsolescência
└── snapshots/                # Diretório de dados (populado pelo usuário)
    ├── area02-2026-07.json
    ├── area27-2026-07.json
    └── qualis-historico-2021-2024.json
```

**Decisão de design**: O plugin NÃO executa o motor de regras. Ele apenas consulta vereditos pré-calculados no snapshot por ISSN. Isso mantém o plugin simples e rápido.

### 7. Onboarding CLI

```
pipeline/onboard.py status    → lista fontes registradas e seus estados
pipeline/onboard.py next      → sugere próxima fonte a adicionar (por impacto)
pipeline/onboard.py add <id>  → integra fonte (parse → validate → merge → snapshot)
```

Diagrama de sequência do `onboard.py add`:

```
Usuário          onboard.py          Parser          Tabela          Motor         Snapshot
  │                  │                  │               │               │              │
  │  add scopus      │                  │               │               │              │
  │─────────────────▶│                  │               │               │              │
  │                  │  load parser     │               │               │              │
  │                  │─────────────────▶│               │               │              │
  │                  │                  │               │               │              │
  │                  │  parse(path)     │               │               │              │
  │                  │─────────────────▶│               │               │              │
  │                  │  ◀─ records ─────│               │               │              │
  │                  │                  │               │               │              │
  │                  │  validate schema │               │               │              │
  │                  │──────┐           │               │               │              │
  │                  │◀─────┘           │               │               │              │
  │                  │                                  │               │              │
  │                  │  merge records                   │               │              │
  │                  │─────────────────────────────────▶│               │              │
  │                  │                                  │               │              │
  │                  │  classify all affected ISSNs     │               │              │
  │                  │─────────────────────────────────────────────────▶│              │
  │                  │  ◀─ verdicts ────────────────────────────────────│              │
  │                  │                                                  │              │
  │                  │  generate snapshot                               │              │
  │                  │────────────────────────────────────────────────────────────────▶│
  │                  │                                                                 │
  │  ◀── diff report│                                                                 │
  │  (ISSNs que     │                                                                 │
  │   mudaram)      │                                                                 │
```

### 8. GitHub Actions

```yaml
# .github/workflows/update-sources.yml
# Job semanal: baixa fontes livres, gera snapshot, abre PR se houver diff

# .github/workflows/watch-upstream.yml  
# Job mensal: verifica ETag/Last-Modified de fontes e documentos normativos
```

Fluxo do job `update-sources`:

```
Cron (semanal)
      │
      ▼
┌─────────────────┐     ┌──────────────────┐
│ Baixar fontes   │────▶│ Timeout 120s/    │
│ livres          │     │ fonte            │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐
│ Parser falhou?  │─── SIM ──▶ Abre issue + aborta
└────────┬────────┘
         │ NÃO
         ▼
┌─────────────────┐
│ Diff com        │─── IGUAL ──▶ Encerra sem ação
│ snapshot        │
│ anterior?       │
└────────┬────────┘
         │ DIFERENTE
         ▼
┌─────────────────┐
│ Gera snapshot   │
│ + diff legível  │
│ + abre PR       │
└─────────────────┘
```

## Data Models

### Formato do Snapshot (Contrato Pipeline → Plugin)

O snapshot é o único artefato que o plugin consome. Estrutura definida:

```json
{
  "$schema": "../schema/snapshot.schema.json",
  "area": 2,
  "nome": "Computação",
  "vigencia": "2025-2028",
  "status": "experimental",
  "escala": {
    "rotulos": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"],
    "pontos": {"A1": 1, "A2": 0.875, "A3": 0.75, "A4": 0.625, "A5": 0, "A6": 0, "A7": 0, "A8": 0}
  },
  "data_snapshot": "2026-07-15",
  "fontes_utilizadas": [
    {"id": "scopus", "data_arquivo": "2026-06-01", "registros": 28450},
    {"id": "sjr", "data_arquivo": "2026-05-15", "registros": 30120}
  ],
  "nao_automatizavel": [
    "FWCI: os 5% dos artigos com maior FWCI sobem 1 nível. Impossível calcular localmente."
  ],
  "veiculos": {
    "0001-0782": {
      "titulo": "Communications of the ACM",
      "issns": ["0001-0782", "1557-7317"],
      "tipos": {
        "journalArticle": {
          "estrato": "A1",
          "estado": "COMPLETO",
          "trilha": [
            {
              "etapa": "expressao_avaliada",
              "metrica": "max(wos_percentil, scopus_percentil)",
              "operandos": {"scopus_percentil": 98.2, "wos_percentil": null},
              "valor_calculado": 98.2,
              "nota": "wos_percentil ausente — estimativa com scopus_percentil apenas"
            },
            {
              "etapa": "regra_ativada",
              "regra_idx": 0,
              "condicao": "min=87.5",
              "resultado": "A1"
            },
            {
              "etapa": "ajuste_sinalizado",
              "condicao": "periodico_sbc",
              "elegivel": false
            }
          ],
          "metricas_utilizadas": {
            "scopus_percentil": {"valor": 98.2, "fonte": "scopus", "data": "2026-06-01"}
          },
          "metricas_ausentes": ["wos_percentil"]
        }
      }
    }
  }
}
```

**Observação sobre o campo `estado`**: No exemplo acima, embora `wos_percentil` esteja ausente, o resultado `A1` é atribuído como `COMPLETO` porque o máximo possível com `wos_percentil` presente seria ≥ 98.2 (manteria A1) ou < 98.2 (não afetaria o max). Quando o resultado parcial já é o melhor rótulo da escala, o estado é `COMPLETO`. Quando o operando ausente PODERIA elevar o estrato, aí sim é `ESTIMATIVA_CONSERVADORA`.

### Formato do Snapshot Histórico (Qualis 2021-2024)

```json
{
  "tipo": "historico",
  "ciclo": "Periódicos 2021-2024",
  "area": 27,
  "data_snapshot": "2026-07-15",
  "veiculos": {
    "0001-0782": {
      "titulo": "Communications of the ACM",
      "estrato_historico": "A1",
      "area_avaliacao_original": "Ciência da Computação"
    }
  }
}
```

### Formato de `sources.yml` (Camada 1)

```yaml
fontes:
  - id: sjr
    nome: SCImago Journal Rank
    landing_url: https://www.scimagojr.com/journalrank.php
    licenca: livre
    acquisition: auto
    provides:
      - sjr_quartil
      - sjr_valor
    status: ativa
    formato:
      tipo: csv
      separador: ";"
      decimal: ","

  - id: scopus
    nome: Scopus Source List
    landing_url: https://www.elsevier.com/products/scopus/content
    licenca: livre
    acquisition: auto
    provides:
      - scopus_percentil
      - scopus_quartil
      - scopus_citescore
    status: ativa
    formato:
      tipo: xlsx
      aba: 0

  - id: abdc
    nome: ABDC Journal Quality List
    landing_url: https://abdc.edu.au/abdc-journal-quality-list/
    licenca: restrita
    acquisition: manual
    provides:
      - abdc_rating
    status: ativa

  - id: jcr
    nome: Journal Citation Reports (Clarivate)
    landing_url: https://jcr.clarivate.com
    licenca: restrita
    acquisition: manual
    provides:
      - jcr_quartil
      - jcr_jif
      - wos_percentil
    status: ativa

  - id: spell
    nome: SPELL - Scientific Periodicals Electronic Library
    landing_url: https://spell.org.br/impacto
    licenca: livre
    acquisition: manual
    provides:
      - spell_faixa
      - spell_fator_impacto
    status: ativa

  - id: scielo
    nome: SciELO Brasil - Periódicos Correntes
    landing_url: https://www.scielo.br
    licenca: livre
    acquisition: manual
    provides:
      - indexado_scielo_br
    status: pendente

  - id: sbc_eventos
    nome: Lista de Eventos SBC com H5
    landing_url: ""
    licenca: livre
    acquisition: manual
    provides:
      - h5_google_scholar
      - ce_sbc_top10
      - ce_sbc_top20
      - ce_sbc_relevante
      - evento_sbc_nacional
    status: bloqueada
```

### Formato de `config/local.yml` (Camada 3)

```yaml
# config/local.yml — gitignored
# Apenas caminhos de fontes restritas e credenciais

fontes:
  abdc:
    caminho: ~/Downloads/ABDC-JQL-2025-v1-260326.xlsx
  jcr:
    caminho: ~/Downloads/jcr-2025.csv
  abs:
    caminho: ~/Downloads/abs-ajg-2024.xlsx

# Credenciais opcionais para APIs
apis:
  crossref:
    mailto: meuemail@universidade.edu.br
```

### Estrutura de Diretórios do Projeto

```
NoQualis_Zotero/
├── areas/                       # Regras declarativas por área (Camada 2)
│   ├── area02-computacao.json
│   └── area27-administracao.json
├── schema/
│   ├── area.schema.json         # Schema das regras (JÁ EXISTE)
│   └── snapshot.schema.json     # Schema do snapshot (a criar)
├── pipeline/                    # Pacote Python
│   ├── __init__.py
│   ├── issn.py                  # Normalização e resolução ISSN
│   ├── vehicles.py              # Tabela de veículos
│   ├── engine.py                # Motor de regras genérico
│   ├── snapshot.py              # Geração de snapshots
│   ├── onboard.py               # CLI de onboarding
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py              # Interface SourceParser (Protocol)
│   │   └── ...                  # Um arquivo por fonte (quando implementado)
│   └── actions/                 # Lógica dos jobs de CI
│       ├── update_sources.py
│       └── watch_upstream.py
├── plugin/                      # Plugin Zotero 7
│   ├── manifest.json
│   └── src/
├── config/
│   └── local.yml                # Camada 3 (gitignored)
├── sources.yml                  # Camada 1 (versionado)
├── scripts/
│   └── make_sample.py           # Inventário de colunas (JÁ EXISTE)
├── docs/
├── LIMITATIONS.md
├── README.md
└── .github/workflows/
    ├── update-sources.yml
    └── watch-upstream.yml
```

## Correctness Properties

*Uma propriedade é uma característica ou comportamento que deve ser verdadeiro em todas as execuções válidas de um sistema — essencialmente, uma declaração formal sobre o que o sistema deve fazer. Propriedades servem como ponte entre especificações legíveis por humanos e garantias de corretude verificáveis por máquina.*

### Property 1: Normalização de ISSN — round-trip

*Para qualquer* ISSN válido de 8 dígitos com dígito verificador correto, normalizar para formato `XXXX-XXXX` e depois extrair os dígitos deve produzir os mesmos 8 dígitos originais, e o resultado deve sempre satisfazer o algoritmo de verificação ISSN (mod 11).

**Validates: Requirements 1.1**

### Property 2: Normalização de título — idempotência

*Para qualquer* string Unicode, aplicar `normalize_title` duas vezes deve produzir o mesmo resultado que aplicar uma vez: `normalize_title(normalize_title(t)) == normalize_title(t)`.

**Validates: Requirements 1.4**

### Property 3: Modos de combinação — semântica correta

*Para qualquer* conjunto de regras e métricas de entrada: (a) no modo `melhor_posicao`, o resultado deve ser o rótulo de maior posição na escala dentre todas as regras satisfeitas; (b) no modo `metrica_unica`, o resultado deve ser o rótulo cuja faixa contém o valor da métrica avaliada; (c) no modo `primeira_regra`, o resultado deve ser o da primeira regra satisfeita na ordem declarada.

**Validates: Requirements 2.2**

### Property 4: Campo `in` — pertencimento case-sensitive

*Para qualquer* valor `v` e conjunto `S`, a regra com campo `in: S` é satisfeita se e somente se `v` pertence a `S` com comparação case-sensitive e tipo-exata (string "1" ≠ inteiro 1).

**Validates: Requirements 2.3**

### Property 5: Campos `min`/`max` — semântica de limites

*Para qualquer* valor numérico `v`, limite inferior `lo` e limite superior `hi`: a regra é satisfeita se e somente se `lo <= v < hi` (min inclusivo, max exclusivo). Se apenas `min` é declarado, não há limite superior. Se apenas `max` é declarado, não há limite inferior.

**Validates: Requirements 2.4**

### Property 6: Campo `requer` — conjunção lógica

*Para qualquer* regra com campo `requer` contendo N condições, a regra é satisfeita se e somente se TODAS as N condições são verdadeiras nas métricas do item. Se qualquer condição for falsa ou não-disponível, a regra não é satisfeita.

**Validates: Requirements 2.5**

### Property 7: Ajustes — limites de escala e tetos

*Para qualquer* estrato base, escala ordenada, ajuste com efeito `+N` ou `-N`, e teto declarado: o rótulo resultante nunca ultrapassa (a) o primeiro rótulo da escala (melhor), (b) o último rótulo da escala (pior), (c) o valor do campo `teto` do ajuste, (d) o valor de `teto_qualitativo` do bloco quando `qualitativo: true`.

**Validates: Requirements 2.6, 2.7**

### Property 8: Expressões max/min — operandos parciais

*Para qualquer* expressão `max(a, b, ...)` ou `min(a, b, ...)` onde pelo menos um operando está disponível, o resultado deve ser respectivamente o máximo ou mínimo dos operandos disponíveis, ignorando os indisponíveis. Se nenhum operando está disponível, o resultado deve ser `None`.

**Validates: Requirements 2.8**

### Property 9: Trilha de decisão — completude

*Para qualquer* veredito produzido pelo motor, a trilha de decisão deve conter: (a) a métrica utilizada (nome e valor), (b) a regra ativada (ou indicação de fallback), (c) ajustes aplicados ou sinalizados, (d) fonte e data de cada métrica consumida, (e) se ESTIMATIVA_CONSERVADORA, a lista de métricas ausentes com nome canônico.

**Validates: Requirements 2.9, 16.4**

### Property 10: Fallback — nenhuma regra satisfeita

*Para qualquer* item cujas métricas não satisfazem nenhuma regra do bloco de veículo, o motor deve retornar exatamente o valor declarado no campo `fallback` do bloco (`NAO_CLASSIFICAVEL`, `NAO_CONSIDERADO` ou `pior_rotulo`), e a trilha deve registrar que nenhuma regra foi ativada.

**Validates: Requirements 2.11, 2.13**

### Property 11: Validação de schema — rejeição de JSON inválido

*Para qualquer* arquivo JSON que viola `schema/area.schema.json` (campo obrigatório ausente, tipo incorreto, valor fora de enum), o motor deve rejeitar o carregamento com mensagem indicando a localização do campo inválido, sem processar classificações para essa área.

**Validates: Requirements 2.12**

### Property 12: Resolução de métricas — completude

*Para qualquer* métrica referenciada em regras de `areas/*.json`, essa métrica deve corresponder a pelo menos um campo `provides` em `sources.yml`. Se uma métrica não é resolvível, o carregamento da regra deve ser rejeitado com mensagem indicando o nome canônico órfão.

**Validates: Requirements 13.2, 13.5, 13.6, 13.7**

### Property 13: Pipeline com subconjunto arbitrário de fontes

*Para qualquer* subconjunto (inclusive vazio) das fontes registradas em `sources.yml`, o pipeline deve executar sem erro, gerando um snapshot válido conforme schema. Itens sem dados suficientes recebem `NAO_CLASSIFICAVEL`.

**Validates: Requirements 15.1, 15.7**

### Property 14: Atomicidade do onboard — falha não modifica estado

*Para qualquer* falha durante `onboard.py add` (parse ou validação), a Tabela de Veículos e o snapshot devem permanecer inalterados: estado_antes == estado_depois.

**Validates: Requirements 15.5**

### Property 15: Degradação conservadora — rotulagem correta

*Para qualquer* expressão `max(...)` ou combinação `melhor_posicao` com pelo menos um operando/regra avaliável mas não todos, o veredito deve ser rotulado como `ESTIMATIVA_CONSERVADORA`. Quando nenhum operando/regra é avaliável, o veredito deve ser `NAO_CLASSIFICAVEL`.

**Validates: Requirements 16.1, 16.2**

### Property 16: Monotonicidade — operandos parciais nunca superestimam

*Para qualquer* item classificado com operandos parciais (subconjunto S₁) e posteriormente reclassificado com superset de operandos (S₂ ⊇ S₁), o estrato com S₁ deve ser menor ou igual ao estrato com S₂ na escala ordenada. A adição de uma fonte ausente pode apenas manter ou elevar o estrato, nunca reduzi-lo.

**Validates: Requirements 16.5**

### Property 17: Isolamento de dados históricos

*Para qualquer* item com dados Qualis históricos (ciclo 2021-2024), os dados históricos não devem participar do cálculo de veredito do ciclo 2025-2028. Um item com estrato histórico "A1" mas sem dados no ciclo corrente deve receber `NAO_CLASSIFICAVEL` no veredito corrente.

**Validates: Requirements 5.3**

### Property 18: Relatório de cobertura — invariante de soma

*Para qualquer* execução do pipeline sobre um conjunto de fontes, o relatório de cobertura deve satisfazer: para cada fonte, `total_processados == total_resolvidos + total_nao_resolvidos`.

**Validates: Requirements 1.8**

## Error Handling

### Pipeline

| Cenário | Comportamento | Resultado |
|---------|--------------|-----------|
| ISSN inválido (< 8 dígitos ou check digit incorreto) | Tenta enriquecimento por DOI, depois por título | Registra aviso se não resolvido |
| Fonte indisponível no job de atualização | Registra na issue, prossegue com demais fontes | PR indica fontes ausentes |
| Parser falha com erro de lógica | Abre issue com contexto completo | Aborta sem snapshot parcial |
| JSON de área inválido | Rejeita carregamento com mensagem de erro | Área não processável até correção |
| Métrica referenciada sem fonte em sources.yml | Rejeita carregamento da regra | Mensagem indica métrica órfã |
| Timeout em enriquecimento DOI (>10s) | Tenta próximo serviço (até 3 tentativas por serviço) | Se todos falham, tenta título |
| Fonte restrita sem override em local.yml | Falha com mensagem indicando onde baixar | Sugere comando make_sample |
| `onboard.py add` com parse falhando | Aborta sem modificar Tabela/snapshot | Exibe motivo e registros rejeitados |

### Plugin

| Cenário | Comportamento | Resultado |
|---------|--------------|-----------|
| Snapshot ausente para área selecionada | Exibe mensagem informativa | Nenhuma classificação para essa área |
| Snapshot obsoleto (> 180 dias) | Exibe aviso com idade em dias | Classificação disponível com aviso |
| Item sem ISSN reconhecível | NAO_CLASSIFICAVEL | Motivo na trilha de decisão |
| Tipo de item não definido na área | Retorna fallback do bloco | NAO_CLASSIFICAVEL ou NAO_CONSIDERADO |
| Múltiplas áreas selecionadas | Coluna separada por área | Cada área avalia independentemente |
| Tag anterior existente para mesma área | Substitui tag antes de aplicar nova | Apenas uma tag por área por item |

### Degradação Conservadora — Detalhamento

```
┌──────────────────────────────────────────────────────────────────────┐
│ Cenário: max(wos_percentil, scopus_percentil) com apenas scopus     │
│                                                                      │
│ scopus_percentil = 72.3                                              │
│ wos_percentil = AUSENTE                                              │
│                                                                      │
│ Cálculo: max(72.3) = 72.3 → A3 (faixa 62.5-75)                     │
│                                                                      │
│ Se wos_percentil estivesse presente:                                 │
│   - Se wos >= 72.3: max >= 72.3 → A3 ou melhor (nunca pior)        │
│   - Se wos < 72.3: max = 72.3 → ainda A3                           │
│                                                                      │
│ Monotonicidade: GARANTIDA                                            │
│ Estado: ESTIMATIVA_CONSERVADORA (poderia ser A2 ou A1 com WoS)      │
│ Trilha: "wos_percentil ausente — fonte: jcr"                        │
└──────────────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────────────┐
│ Cenário: melhor_posicao (Área 27) com apenas sjr_quartil            │
│                                                                      │
│ sjr_quartil = "Q2" → regra satisfeita → B                           │
│ abdc_rating = AUSENTE, abs_rating = AUSENTE, jcr_quartil = AUSENTE  │
│                                                                      │
│ Resultado parcial: B                                                 │
│ Com todas as fontes: poderia ser MB (se ABDC A* ou ABS >= 2)        │
│                                                                      │
│ Monotonicidade: B ≤ MB ✓                                            │
│ Estado: ESTIMATIVA_CONSERVADORA                                      │
│ Trilha: "abdc_rating, abs_rating, jcr_quartil ausentes"             │
└──────────────────────────────────────────────────────────────────────┘
```

## Testing Strategy

### Abordagem Dual

O projeto adota uma abordagem complementar de testes unitários (exemplos específicos) e testes baseados em propriedades (verificação universal).

- **Testes unitários**: cobrem exemplos concretos, edge cases, integração entre componentes.
- **Testes de propriedade**: cobrem invariantes universais que devem valer para TODOS os inputs válidos.

### Testes Baseados em Propriedades (PBT)

**Biblioteca**: [Hypothesis](https://hypothesis.readthedocs.io/) (Python, para o pipeline).

**Configuração**: mínimo 100 iterações por propriedade (via `settings(max_examples=100)`).

**Tag**: cada teste referencia a propriedade do design:
```python
# Feature: classificador-capes, Property 16: Monotonicidade
```

**Propriedades implementáveis como PBT:**

| # | Propriedade | Gerador Principal |
|---|-------------|-------------------|
| 1 | ISSN round-trip | ISSNs aleatórios válidos (8 dígitos + check digit) |
| 2 | Título idempotente | Strings Unicode arbitrárias |
| 3 | Modos de combinação | Regras + métricas geradas conforme schema |
| 4 | Campo `in` case-sensitive | Valores + conjuntos com variações de case |
| 5 | Limites min/max | Valores numéricos + limites no boundary |
| 6 | Conjunção `requer` | Listas de condições booleanas |
| 7 | Ajustes com limites | Escalas + estratos + ajustes aleatórios |
| 8 | Expressões max/min parciais | Listas de operandos com None aleatórios |
| 9 | Trilha completa | Classificações aleatórias |
| 10 | Fallback | Itens sem métricas correspondentes |
| 11 | Schema validation | JSONs com mutações aleatórias |
| 12 | Resolução de métricas | sources.yml + regras com métricas variadas |
| 13 | Subconjunto de fontes | Subsets aleatórios de fontes |
| 14 | Atomicidade | Falhas simuladas em pontos aleatórios |
| 15 | Degradação conservadora | Expressões com operandos parciais |
| 16 | Monotonicidade | Pares (subconjunto, superset) de operandos |
| 17 | Isolamento histórico | Itens com/sem dados históricos |
| 18 | Invariante de soma | Conjuntos de registros com resolução parcial |

### Testes Unitários (Exemplos)

- Classificação de periódicos conhecidos contra resultado esperado (ACM, IEEE, etc.)
- Área 27: periódico com SciELO + SPELL décil superior → B (cumulativo)
- Área 02: conferencePaper h5=0 → NAO_CONSIDERADO
- Área 02: book → NAO_CLASSIFICAVEL
- Área 27: conferencePaper → NAO_CLASSIFICAVEL
- Status experimental → indicação no veredito
- Plugin: snapshot ausente → mensagem informativa
- Plugin: snapshot obsoleto → aviso de idade

### Testes de Integração

- `onboard.py add` end-to-end com fonte mock
- Job `update-sources` com servidor HTTP mock
- Job `watch-upstream` com respostas ETag diferentes
- Plugin: leitura de snapshot e renderização de veredito
- Geração de Anexo 3/4 comparada com template

### Organização de Testes

```
pipeline/
├── tests/
│   ├── test_issn.py               # Props 1, 2
│   ├── test_engine.py             # Props 3-10, 15, 16
│   ├── test_schema_validation.py  # Prop 11
│   ├── test_sources.py            # Prop 12
│   ├── test_pipeline.py           # Props 13, 14, 18
│   ├── test_isolation.py          # Prop 17
│   ├── test_area02.py             # Exemplos Área 02
│   ├── test_area27.py             # Exemplos Área 27
│   └── conftest.py                # Fixtures: escalas, regras mock, geradores
plugin/
├── tests/
│   ├── test_evaluator.js          # Busca por ISSN no snapshot
│   ├── test_columns.js            # Registro de colunas
│   └── test_tagger.js             # Lógica de tagging
```

