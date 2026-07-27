"""Dataclasses do domínio para a tabela normalizada de veículos."""

from dataclasses import dataclass, field


@dataclass
class MetricValue:
    """Valor de uma métrica com proveniência."""

    valor: str | int | float
    fonte_id: str  # id da fonte que forneceu (ex: "sjr")
    data_fonte: str  # data do arquivo da fonte (ISO 8601)


@dataclass
class VehicleRecord:
    """Registro completo de um veículo na tabela normalizada."""

    issn_l: str  # Chave primária
    titulos: list[str]  # Títulos conhecidos
    issns: set[str]  # Todos os ISSNs mapeados
    metricas: dict[str, MetricValue] = field(default_factory=dict)
    # Chaves = nomes canônicos de métricas
    avisos: list[str] = field(default_factory=list)
