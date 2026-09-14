"""Relatórios da Marketing API.

Restrições que este módulo aplica antes de chamar, porque a TikTok as aplica
silenciosamente:

- janela de 30 dias quando `stat_time_day` está nas dimensões (1 dia para
  `stat_time_hour`);
- teto de 20.000 ads por requisição — acima disso a resposta é **truncada** com
  um header de aviso, não um erro;
- máximo de 100 IDs por requisição.

`enable_report_title_translation` vai sempre como `false`: com `true` a TikTok
retraduz os cabeçalhos e quebra o parser sem avisar.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Literal

from ..http import TikTokClient

MAX_IDS_POR_REQUEST = 100
JANELA_MAX_DIA = 30
JANELA_MAX_HORA = 1

DataLevel = Literal[
    "AUCTION_AD", "AUCTION_ADGROUP", "AUCTION_CAMPAIGN", "AUCTION_ADVERTISER"
]

METRICAS_PADRAO = (
    "spend", "impressions", "clicks", "ctr", "cpc", "cpm",
    "conversion", "cost_per_conversion", "conversion_rate",
)


class Reports:
    def __init__(self, client: TikTokClient, advertiser_id: str):
        self.client = client
        self.advertiser_id = advertiser_id

    @staticmethod
    def _validar_janela(inicio: date, fim: date, dimensions: Iterable[str]) -> None:
        dims = set(dimensions)
        dias = (fim - inicio).days + 1
        if "stat_time_hour" in dims and dias > JANELA_MAX_HORA:
            raise ValueError("com stat_time_hour a janela máxima é de 1 dia")
        if "stat_time_day" in dims and dias > JANELA_MAX_DIA:
            raise ValueError(
                f"com stat_time_day a janela máxima é de {JANELA_MAX_DIA} dias; "
                f"pedido de {dias} dias — quebre em blocos ou use relatório assíncrono"
            )

    def integrated(
        self,
        *,
        data_level: DataLevel = "AUCTION_CAMPAIGN",
        dimensions: tuple[str, ...] = ("campaign_id", "stat_time_day"),
        metrics: tuple[str, ...] = METRICAS_PADRAO,
        start_date: date | None = None,
        end_date: date | None = None,
        incluir_deletados: bool = False,
        page: int = 1,
        page_size: int = 1000,
    ) -> dict[str, Any]:
        end_date = end_date or date.today() - timedelta(days=1)
        start_date = start_date or end_date - timedelta(days=JANELA_MAX_DIA - 1)
        self._validar_janela(start_date, end_date, dimensions)

        params: dict[str, Any] = {
            "advertiser_id": self.advertiser_id,
            "report_type": "BASIC",
            "data_level": data_level,
            "dimensions": list(dimensions),
            "metrics": list(metrics),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": page,
            "page_size": min(page_size, 1000),
            "enable_report_title_translation": False,
        }
        if incluir_deletados:
            # Sem isso a TikTok filtra entidades deletadas por padrão.
            params["filtering"] = [
                {"field_name": "ad_status", "filter_type": "IN", "filter_value": ["STATUS_ALL"]}
            ]
        return self.client.get("report/integrated/get", **params)

    def por_janelas(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Quebra um período longo em blocos de 30 dias e concatena."""
        resultados: list[dict[str, Any]] = []
        cursor = start_date
        while cursor <= end_date:
            fim_bloco = min(cursor + timedelta(days=JANELA_MAX_DIA - 1), end_date)
            resultados.append(
                self.integrated(start_date=cursor, end_date=fim_bloco, **kwargs)
            )
            cursor = fim_bloco + timedelta(days=1)
        return resultados
