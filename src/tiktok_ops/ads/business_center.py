"""Business Center — o ponto de entrada de quem opera como agência.

Agência não trabalha com uma conta de anúncio solta: trabalha com um Business
Center que pendura várias contas de clientes. Por isso nada aqui assume um
`advertiser_id` fixo — as contas são descobertas a partir do BC.

Tipos de BC devolvidos pela API: `NORMAL`, `DIRECT`, `AGENCY`, `SELF_SERVICE`,
`SELF_SERVICE_AGENCY`. Os dois últimos e o `AGENCY` são os que podem criar e
gerenciar contas de clientes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..http import TikTokClient

TIPOS_AGENCIA = {"AGENCY", "SELF_SERVICE_AGENCY"}


@dataclass(slots=True)
class BusinessCenterInfo:
    bc_id: str
    name: str
    company: str
    bc_type: str
    status: str

    @property
    def e_agencia(self) -> bool:
        return self.bc_type in TIPOS_AGENCIA

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "BusinessCenterInfo":
        # A API aninha os dados do BC em `bc_info` na listagem.
        info = item.get("bc_info", item)
        return cls(
            bc_id=str(info.get("bc_id", "")),
            name=info.get("name", ""),
            company=info.get("company", ""),
            bc_type=info.get("bc_type", info.get("type", "")),
            status=info.get("status", ""),
        )


@dataclass(slots=True)
class AdvertiserInfo:
    advertiser_id: str
    name: str
    currency: str
    timezone: str
    status: str

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "AdvertiserInfo":
        info = item.get("advertiser_info", item)
        return cls(
            advertiser_id=str(info.get("advertiser_id", "")),
            name=info.get("name", info.get("advertiser_name", "")),
            currency=info.get("currency", ""),
            timezone=info.get("timezone", ""),
            status=info.get("status", ""),
        )


class BusinessCenter:
    def __init__(self, client: TikTokClient):
        self.client = client

    def list_bcs(self, *, page: int = 1, page_size: int = 50) -> list[BusinessCenterInfo]:
        """Todos os Business Centers que este token alcança."""
        data = self.client.get("bc/get", page=page, page_size=page_size)
        return [BusinessCenterInfo.from_api(i) for i in data.get("list", [])]

    def list_advertisers(
        self, bc_id: str, *, page: int = 1, page_size: int = 100
    ) -> list[AdvertiserInfo]:
        """Contas de anúncio penduradas em um BC — a carteira da agência."""
        data = self.client.get(
            "bc/advertiser/get", bc_id=bc_id, page=page, page_size=page_size
        )
        return [AdvertiserInfo.from_api(i) for i in data.get("list", [])]

    def list_all_advertisers(self, bc_id: str) -> list[AdvertiserInfo]:
        """Pagina até o fim. Carteiras grandes passam de uma página."""
        todos: list[AdvertiserInfo] = []
        page = 1
        while True:
            lote = self.list_advertisers(bc_id, page=page, page_size=100)
            todos.extend(lote)
            if len(lote) < 100:
                return todos
            page += 1

    def list_assets(
        self, bc_id: str, asset_type: str = "ADVERTISER", *, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """Ativos do BC: contas de anúncio, pixels, catálogos, contas TikTok."""
        data = self.client.get(
            "bc/asset/get", bc_id=bc_id, asset_type=asset_type, page_size=page_size
        )
        return data.get("list", [])

    def resolver_advertiser(
        self, bc_id: str, referencia: str
    ) -> AdvertiserInfo:
        """Aceita um `advertiser_id` ou um trecho do nome da conta.

        Na operação de agência ninguém decora IDs — deixar procurar por nome
        evita copiar e colar errado entre contas de clientes diferentes.
        """
        contas = self.list_all_advertisers(bc_id)
        por_id = {c.advertiser_id: c for c in contas}
        if referencia in por_id:
            return por_id[referencia]

        alvo = referencia.casefold()
        parciais = [c for c in contas if alvo in c.name.casefold()]
        if len(parciais) == 1:
            return parciais[0]
        if not parciais:
            raise LookupError(
                f"nenhuma conta do BC {bc_id} corresponde a '{referencia}'. "
                f"Contas disponíveis: {', '.join(c.name for c in contas) or 'nenhuma'}"
            )
        raise LookupError(
            f"'{referencia}' é ambíguo — corresponde a: "
            + ", ".join(f"{c.name} ({c.advertiser_id})" for c in parciais)
        )
