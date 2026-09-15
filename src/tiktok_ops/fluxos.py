"""Fluxos — as sequências que o Claude Code encadeia no terminal.

Cada função aqui orquestra passos que já existem nos módulos, e nada mais. Elas
ficam fora da CLI de propósito: assim dá para testá-las com dublês, sem rede e
sem credencial.

Dois fluxos cobrem a operação inteira:

    publicar    Drive → R2 → pré-voo → publica → acompanha
    impulsionar post no perfil → autoriza para anúncio → campanha → Spark Ad

E `publicar(..., impulsionar=...)` encadeia os dois, que é o pedido mais comum:
"publica esse vídeo e sobe uma campanha de tráfego em cima dele".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .ads.campaigns import AdGroupSpec, CampaignSpec
from .errors import MediaError, TikTokError

# A publicação devolve um `share_id`, mas o anúncio precisa do id público do post.
# A documentação não deixa claro em qual campo do status ele volta, então
# aceitamos os nomes plausíveis e falhamos com mensagem clara se nenhum vier.
CHAVES_ITEM_ID = ("item_id", "post_id", "tiktok_item_id", "video_id", "share_id")


def extrair_item_id(status: dict[str, Any]) -> str | None:
    for chave in CHAVES_ITEM_ID:
        valor = status.get(chave)
        if valor:
            return str(valor)
    return None


# --------------------------------------------------------------------- tipos

class SuportaPreparar(Protocol):
    def preparar(self, arquivo: Any, *, validar: bool = True) -> tuple[str, Any]: ...


class SuportaPublicar(Protocol):
    def get_settings(self) -> Any: ...
    def publish_video(self, video_url: str, options: Any, **kw: Any) -> dict[str, Any]: ...
    def wait_for_publish(self, share_id: str, **kw: Any) -> dict[str, Any]: ...


@dataclass(slots=True)
class ResultadoPublicacao:
    arquivo: str
    video_url: str = ""
    share_id: str = ""
    item_id: str = ""
    status: str = ""
    dry_run: bool = False
    passos: list[str] = field(default_factory=list)
    payload: dict[str, Any] | None = None

    @property
    def publicado(self) -> bool:
        return self.status == "PUBLISH_COMPLETE"


@dataclass(slots=True)
class ResultadoImpulsionamento:
    item_id: str
    campaign_id: str = ""
    adgroup_id: str = ""
    ad_id: str = ""
    identity_id: str = ""
    dry_run: bool = False
    passos: list[str] = field(default_factory=list)
    payloads: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ publicar

def publicar(
    *,
    drive: Any,
    pipeline: SuportaPreparar,
    publisher: SuportaPublicar,
    nome_arquivo: str,
    opcoes: Any,
    dry_run: bool = True,
    aguardar: bool = True,
) -> ResultadoPublicacao:
    """Leva um arquivo do Drive até o perfil."""
    resultado = ResultadoPublicacao(arquivo=nome_arquivo, dry_run=dry_run)

    alvo = next((f for f in drive.list_media() if f.name == nome_arquivo), None)
    if alvo is None:
        raise MediaError(f"'{nome_arquivo}' não está na pasta do Drive configurada")
    resultado.passos.append(f"encontrado no Drive: {nome_arquivo}")

    video_url, info = pipeline.preparar(alvo)
    resultado.video_url = video_url
    resultado.passos.append(f"mídia validada e publicada em {video_url}")

    # Pré-voo: é aqui que a duração é conferida contra o máximo da conta.
    settings = publisher.get_settings()
    resultado.passos.append("pré-voo da conta consultado")

    resposta = publisher.publish_video(
        video_url,
        opcoes,
        duration_sec=getattr(info, "duration_sec", None),
        settings=settings,
        dry_run=dry_run,
    )

    if dry_run:
        resultado.payload = resposta.get("payload")
        resultado.passos.append("dry-run: nada foi publicado")
        return resultado

    resultado.share_id = str(resposta.get("share_id", ""))
    resultado.passos.append(f"publicação iniciada (share_id {resultado.share_id})")

    if not aguardar:
        return resultado

    status = publisher.wait_for_publish(resultado.share_id)
    resultado.status = str(status.get("status", ""))
    resultado.item_id = extrair_item_id(status) or ""
    resultado.passos.append(f"status final: {resultado.status}")
    return resultado


# --------------------------------------------------------------- impulsionar

def impulsionar(
    *,
    bridge: Any,
    campaigns: Any,
    identities: Any,
    item_id: str,
    nome_campanha: str,
    orcamento_diario: float,
    identidade: str | None = None,
    campaign_id: str | None = None,
    objetivo: str = "TRAFFIC",
    landing_page_url: str | None = None,
    dias_autorizacao: int = 30,
    dry_run: bool = True,
) -> ResultadoImpulsionamento:
    """Transforma um post do perfil em Spark Ad.

    A ordem importa: sem autorizar o post para anúncio, o `tiktok_item_id` não é
    aceito na criação do anúncio.
    """
    resultado = ResultadoImpulsionamento(item_id=item_id, dry_run=dry_run)

    autorizacao = bridge.autorizar_para_anuncio(item_id, dias=dias_autorizacao, dry_run=dry_run)
    resultado.payloads["autorizacao"] = autorizacao
    resultado.passos.append(f"post autorizado para anúncio por {dias_autorizacao} dias")

    identidade_info = identities.resolver(identidade)
    resultado.identity_id = identidade_info.identity_id
    resultado.passos.append(f"identidade: {identidade_info.display_name}")

    if campaign_id:
        resultado.campaign_id = campaign_id
        resultado.passos.append(f"usando campanha existente {campaign_id}")
    else:
        # INFINITE na campanha e o gasto controlado no ad group: a documentação
        # da TikTok se contradiz no piso de campanha, mas o de ad group é claro.
        spec = CampaignSpec(campaign_name=nome_campanha, objective_type=objetivo)
        criacao = campaigns.create(spec, dry_run=dry_run)
        resultado.payloads["campanha"] = criacao
        resultado.campaign_id = str(criacao.get("campaign_id", "")) if not dry_run else ""
        resultado.passos.append(f"campanha '{nome_campanha}' criada")

    grupo = AdGroupSpec(
        campaign_id=resultado.campaign_id or "<campanha>",
        adgroup_name=f"{nome_campanha} — grupo",
        budget=orcamento_diario,
    )
    criacao_grupo = campaigns.create_adgroup(grupo, dry_run=dry_run)
    resultado.payloads["adgroup"] = criacao_grupo
    resultado.adgroup_id = str(criacao_grupo.get("adgroup_id", "")) if not dry_run else ""
    resultado.passos.append(f"ad group criado com orçamento diário de {orcamento_diario:.2f}")

    anuncio = campaigns.create_spark_ad(
        resultado.adgroup_id or "<adgroup>",
        f"{nome_campanha} — anúncio",
        resultado.identity_id,
        item_id,
        landing_page_url=landing_page_url,
        show_on_profile=True,  # dark_post_status OFF: o post continua visível no perfil
        dry_run=dry_run,
    )
    resultado.payloads["anuncio"] = anuncio
    resultado.ad_id = str(anuncio.get("ad_ids", [""])[0]) if not dry_run else ""
    resultado.passos.append("Spark Ad criado")

    return resultado


# ------------------------------------------------------------------ completo

def publicar_e_impulsionar(
    *,
    drive: Any,
    pipeline: SuportaPreparar,
    publisher: SuportaPublicar,
    bridge: Any,
    campaigns: Any,
    identities: Any,
    nome_arquivo: str,
    opcoes: Any,
    nome_campanha: str,
    orcamento_diario: float,
    dry_run: bool = True,
    **kw: Any,
) -> dict[str, Any]:
    """O pedido mais comum: publica e sobe campanha em cima do que publicou."""
    pub = publicar(
        drive=drive, pipeline=pipeline, publisher=publisher,
        nome_arquivo=nome_arquivo, opcoes=opcoes, dry_run=dry_run, aguardar=True,
    )

    if dry_run:
        return {"publicacao": pub, "impulsionamento": None,
                "aviso": "dry-run: o impulsionamento só é simulado com um post real"}

    if not pub.publicado:
        raise TikTokError(
            -1,
            f"publicação terminou em '{pub.status}' — nada foi impulsionado. "
            "Verifique o status antes de tentar de novo.",
        )
    if not pub.item_id:
        raise TikTokError(
            -1,
            "o post foi publicado, mas a resposta de status não trouxe o id do post. "
            f"share_id {pub.share_id}. Rode `bridge candidatos` para achar o id e "
            "impulsione com `fluxo impulsionar`.",
        )

    imp = impulsionar(
        bridge=bridge, campaigns=campaigns, identities=identities,
        item_id=pub.item_id, nome_campanha=nome_campanha,
        orcamento_diario=orcamento_diario, dry_run=dry_run, **kw,
    )
    return {"publicacao": pub, "impulsionamento": imp}
