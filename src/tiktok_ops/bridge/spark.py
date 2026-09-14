"""Ponte orgânico → pago.

O ciclo que dá nome ao projeto: publicar no perfil, medir a performance orgânica
por alguns dias e promover como Spark Ad apenas o que passou de um limiar.

Desde que a Custom Identity foi desativada para posicionamentos TikTok/Automático
em 15/01/2026, esta é a rota canônica para anunciar em feed — não uma alternativa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..http import TikTokClient


@dataclass(slots=True)
class CriterioPromocao:
    """Limiar que um post orgânico precisa cruzar para virar anúncio."""

    min_views: int = 0
    min_engagement_rate: float = 0.0  # (curtidas + comentários + compartilhamentos) / views
    min_idade_horas: int = 24  # tempo mínimo no ar antes de julgar

    def aprova(self, metricas: dict[str, Any], idade_horas: float) -> tuple[bool, str]:
        if idade_horas < self.min_idade_horas:
            return False, f"no ar há {idade_horas:.0f}h; o mínimo é {self.min_idade_horas}h"

        views = int(metricas.get("video_views", 0) or 0)
        if views < self.min_views:
            return False, f"{views} views; o mínimo é {self.min_views}"

        if self.min_engagement_rate > 0:
            if views == 0:
                return False, "sem views para calcular engajamento"
            interacoes = sum(
                int(metricas.get(k, 0) or 0) for k in ("likes", "comments", "shares")
            )
            taxa = interacoes / views
            if taxa < self.min_engagement_rate:
                return False, f"engajamento {taxa:.2%} abaixo de {self.min_engagement_rate:.2%}"

        return True, "aprovado"


class SparkBridge:
    def __init__(self, accounts_client: TikTokClient, business_id: str):
        self.client = accounts_client
        self.business_id = business_id

    def listar_posts(self, *, page_size: int = 20) -> dict[str, Any]:
        """Posts da conta com métricas — a base da decisão de promover."""
        return self.client.get(
            "business/video/list", business_id=self.business_id, page_size=page_size
        )

    def autorizar_para_anuncio(
        self, item_id: str, *, dias: int = 30, dry_run: bool = True
    ) -> dict[str, Any]:
        """Habilita a autorização de anúncio em um post próprio.

        É este passo que torna o post elegível a virar Spark Ad — sem ele o
        `tiktok_item_id` não é aceito em `/ad/create/`.
        """
        payload = {
            "business_id": self.business_id,
            "item_id": item_id,
            "auth_period": dias,
        }
        if dry_run:
            return {"dry_run": True, "endpoint": "business/video/ad/auth", "payload": payload}
        return self.client.post("business/video/ad/auth", payload)

    def status_autorizacao(self, item_id: str) -> dict[str, Any]:
        return self.client.get(
            "business/video/ad/auth", business_id=self.business_id, item_id=item_id
        )
