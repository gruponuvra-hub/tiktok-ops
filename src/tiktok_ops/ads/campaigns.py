"""Gestão de campanhas via Marketing API v1.3.

Duas mudanças de 2026 moldam este módulo:

- 15/01/2026: Custom Identity deixou de poder ser criada para posicionamentos
  TikTok/Automático. Na prática, **Spark Ads virou obrigatório** — todo ad sai
  com `identity_type` de conta real.
- 27/01/2026: `dark_post_status` passou a ter default `ON`, o que esconde o post
  do perfil. Aqui ele é sempre explícito.

Sobre orçamento: a documentação da TikTok se contradiz no piso de campanha
(R$ 20 no texto, R$ 50 na tabela de moedas). Por isso o default é
`BUDGET_MODE_INFINITE` na campanha, com o gasto controlado no ad group, onde o
piso de R$ 20 é inequívoco nas duas fontes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from ..http import TikTokClient

AD_GROUP_MIN_DAILY_BUDGET = 20.0  # BRL e USD — mesma faixa, razão 1:1
CAMPAIGN_MIN_DAILY_BUDGET_SAFE = 50.0  # o maior dos dois valores em conflito

BudgetMode = Literal["BUDGET_MODE_INFINITE", "BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"]


@dataclass(slots=True)
class CampaignSpec:
    campaign_name: str
    objective_type: str = "TRAFFIC"
    budget_mode: BudgetMode = "BUDGET_MODE_INFINITE"
    budget: float | None = None
    budget_optimize_on: bool = False  # CBO. INFINITE só é válido com CBO desligado.

    def validate(self) -> None:
        if len(self.campaign_name) > 512:
            raise ValueError("campaign_name tem limite de 512 caracteres e não aceita emoji")
        if self.budget_mode == "BUDGET_MODE_INFINITE":
            if self.budget_optimize_on:
                raise ValueError(
                    "BUDGET_MODE_INFINITE não é válido com CBO ligado; "
                    "use BUDGET_MODE_DAY ou desligue budget_optimize_on"
                )
            return
        if self.budget is None:
            raise ValueError(f"{self.budget_mode} exige um valor em `budget`")
        if self.budget < CAMPAIGN_MIN_DAILY_BUDGET_SAFE:
            raise ValueError(
                f"orçamento de campanha abaixo do piso seguro de "
                f"{CAMPAIGN_MIN_DAILY_BUDGET_SAFE:.0f}. A documentação da TikTok se "
                f"contradiz entre 20 e 50 — prefira BUDGET_MODE_INFINITE e controle "
                f"o gasto no ad group."
            )

    def to_payload(self, advertiser_id: str) -> dict[str, Any]:
        self.validate()
        payload: dict[str, Any] = {
            "advertiser_id": advertiser_id,
            "campaign_name": self.campaign_name,
            "objective_type": self.objective_type,
            "budget_mode": self.budget_mode,
            "budget_optimize_on": self.budget_optimize_on,
            # Idempotência: mesma request_id em até 10s é deduplicada pela TikTok.
            # Reutilize-a de propósito ao reprocessar uma falha de rede.
            "request_id": str(uuid.uuid4()),
        }
        if self.budget is not None:
            payload["budget"] = self.budget
        return payload


@dataclass(slots=True)
class AdGroupSpec:
    campaign_id: str
    adgroup_name: str
    budget: float
    schedule_type: str = "SCHEDULE_FROM_NOW"
    budget_mode: Literal["BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"] = "BUDGET_MODE_DAY"
    optimization_goal: str = "CLICK"
    billing_event: str = "CPC"
    placement_type: str = "PLACEMENT_TYPE_NORMAL"
    placements: tuple[str, ...] = ("PLACEMENT_TIKTOK",)
    location_ids: tuple[str, ...] = ()
    extras: dict[str, Any] | None = None

    def validate(self) -> None:
        if self.budget < AD_GROUP_MIN_DAILY_BUDGET:
            raise ValueError(
                f"orçamento do ad group precisa ser no mínimo {AD_GROUP_MIN_DAILY_BUDGET:.0f}"
            )
        if len(self.location_ids) > 3000:
            raise ValueError("máximo de 3000 IDs de localização por ad group")

    def to_payload(self, advertiser_id: str) -> dict[str, Any]:
        self.validate()
        payload: dict[str, Any] = {
            "advertiser_id": advertiser_id,
            "campaign_id": self.campaign_id,
            "adgroup_name": self.adgroup_name,
            "budget_mode": self.budget_mode,
            "budget": self.budget,
            "schedule_type": self.schedule_type,
            "optimization_goal": self.optimization_goal,
            "billing_event": self.billing_event,
            "placement_type": self.placement_type,
            "placements": list(self.placements),
        }
        if self.location_ids:
            payload["location_ids"] = list(self.location_ids)
        if self.extras:
            payload.update(self.extras)
        return payload


class Campaigns:
    def __init__(self, client: TikTokClient, advertiser_id: str):
        self.client = client
        self.advertiser_id = advertiser_id

    # -- campanha ----------------------------------------------------------

    def create(self, spec: CampaignSpec, *, dry_run: bool = True) -> dict[str, Any]:
        payload = spec.to_payload(self.advertiser_id)
        if dry_run:
            return {"dry_run": True, "endpoint": "campaign/create", "payload": payload}
        return self.client.post("campaign/create", payload)

    def list(self, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self.client.get(
            "campaign/get", advertiser_id=self.advertiser_id, page=page, page_size=page_size
        )

    def set_status(
        self, campaign_ids: list[str], status: Literal["ENABLE", "DISABLE", "DELETE"],
        *, dry_run: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "advertiser_id": self.advertiser_id,
            "campaign_ids": campaign_ids,
            "operation_status": status,
        }
        if dry_run:
            return {"dry_run": True, "endpoint": "campaign/status/update", "payload": payload}
        return self.client.post("campaign/status/update", payload)

    # -- ad group ----------------------------------------------------------

    def create_adgroup(self, spec: AdGroupSpec, *, dry_run: bool = True) -> dict[str, Any]:
        payload = spec.to_payload(self.advertiser_id)
        if dry_run:
            return {"dry_run": True, "endpoint": "adgroup/create", "payload": payload}
        return self.client.post("adgroup/create", payload)

    # -- ad ----------------------------------------------------------------

    def create_spark_ad(
        self,
        adgroup_id: str,
        ad_name: str,
        identity_id: str,
        tiktok_item_id: str,
        *,
        identity_type: Literal["TT_USER", "BC_AUTH_TT", "AUTH_CODE"] = "TT_USER",
        call_to_action: str = "LEARN_MORE",
        landing_page_url: str | None = None,
        show_on_profile: bool = True,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Cria um Spark Ad a partir de um post que já existe no perfil.

        `show_on_profile=True` manda `dark_post_status: OFF` — necessário desde
        que o default virou `ON` em 27/01/2026 e passou a esconder o post.
        """
        creative: dict[str, Any] = {
            "ad_name": ad_name,
            "identity_type": identity_type,
            "identity_id": identity_id,
            "tiktok_item_id": tiktok_item_id,
            "call_to_action": call_to_action,
            "dark_post_status": "OFF" if show_on_profile else "ON",
        }
        if landing_page_url:
            creative["landing_page_url"] = landing_page_url

        payload = {
            "advertiser_id": self.advertiser_id,
            "adgroup_id": adgroup_id,
            "creatives": [creative],
        }
        if dry_run:
            return {"dry_run": True, "endpoint": "ad/create", "payload": payload}
        return self.client.post("ad/create", payload)
