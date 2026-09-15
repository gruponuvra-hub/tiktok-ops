"""Identidades — de quem o anúncio sai.

Desde 15/01/2026 a TikTok não permite mais criar Custom Identity para
posicionamentos TikTok e Automático. Na prática todo anúncio de feed sai de uma
conta real, e é a identidade que amarra o anúncio a essa conta. Sem resolver a
identidade certa não há Spark Ad.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..http import TikTokClient

# Só estes três tipos podem gerar Spark Ads.
TIPOS_SPARK = ("TT_USER", "BC_AUTH_TT", "AUTH_CODE")

IdentityType = Literal["CUSTOMIZED_USER", "AUTH_CODE", "TT_USER", "BC_AUTH_TT", "TTS_TT"]


@dataclass(slots=True)
class IdentityInfo:
    identity_id: str
    identity_type: str
    display_name: str

    @property
    def serve_para_spark(self) -> bool:
        return self.identity_type in TIPOS_SPARK

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "IdentityInfo":
        return cls(
            identity_id=str(item.get("identity_id", "")),
            identity_type=item.get("identity_type", ""),
            display_name=item.get("display_name", item.get("username", "")),
        )


class Identities:
    def __init__(self, client: TikTokClient, advertiser_id: str):
        self.client = client
        self.advertiser_id = advertiser_id

    def list(
        self, identity_type: IdentityType = "TT_USER", *, page_size: int = 100
    ) -> list[IdentityInfo]:
        data = self.client.get(
            "identity/get",
            advertiser_id=self.advertiser_id,
            identity_type=identity_type,
            page_size=page_size,
        )
        return [IdentityInfo.from_api(i) for i in data.get("identity_list", data.get("list", []))]

    def resolver(self, referencia: str | None = None) -> IdentityInfo:
        """Resolve a identidade a usar no anúncio.

        Sem referência, só aceita quando existe exatamente uma candidata — nunca
        escolhe por conta própria entre várias, porque isso significaria anunciar
        pela conta errada.
        """
        candidatas = [i for i in self.list() if i.serve_para_spark]

        if referencia:
            por_id = {i.identity_id: i for i in candidatas}
            if referencia in por_id:
                return por_id[referencia]
            alvo = referencia.casefold()
            parciais = [i for i in candidatas if alvo in i.display_name.casefold()]
            if len(parciais) == 1:
                return parciais[0]
            if not parciais:
                raise LookupError(
                    f"nenhuma identidade corresponde a '{referencia}'. "
                    f"Disponíveis: {', '.join(i.display_name for i in candidatas) or 'nenhuma'}"
                )
            raise LookupError(
                f"'{referencia}' é ambíguo — corresponde a: "
                + ", ".join(f"{i.display_name} ({i.identity_id})" for i in parciais)
            )

        if not candidatas:
            raise LookupError(
                "nenhuma identidade elegível a Spark Ads nesta conta de anúncio. "
                "Vincule a conta TikTok ao anunciante ou ao Business Center primeiro."
            )
        if len(candidatas) > 1:
            raise LookupError(
                "esta conta tem mais de uma identidade; diga qual usar. Disponíveis: "
                + ", ".join(f"{i.display_name} ({i.identity_id})" for i in candidatas)
            )
        return candidatas[0]
