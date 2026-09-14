"""Publicação orgânica no perfil via Accounts API.

Rota escolhida: `business-api.tiktok.com`, não `developers.tiktok.com`. O
endpoint aqui publica público direto — ele nem tem parâmetro `privacy_level` —
e não existe a restrição de "cliente não auditado" que force tudo a `SELF_ONLY`.
Ver CLAUDE.md > Decisão de arquitetura travada.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from ..errors import MediaError
from ..http import TikTokClient

CAPTION_MAX_CHARS = 2200
CAPTION_MAX_MENTIONS = 30

StatusFinal = Literal["PUBLISH_COMPLETE", "FAILED", "PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD"]


@dataclass(slots=True)
class AccountSettings:
    """Resposta de `/business/video/settings/` — o pré-voo obrigatório.

    Publicar sem consultar isso é o erro mais comum: vídeo mais longo que
    `max_video_post_duration_sec` simplesmente falha, e tentar habilitar um
    recurso que a conta desativou é rejeitado.
    """

    privacy_level_options: list[str] = field(default_factory=list)
    comment_disabled: bool = False
    duet_disabled: bool = False
    stitch_disabled: bool = False
    max_video_post_duration_sec: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AccountSettings":
        return cls(
            privacy_level_options=data.get("privacy_level_options", []),
            comment_disabled=bool(data.get("comment_disabled", False)),
            duet_disabled=bool(data.get("duet_disabled", False)),
            stitch_disabled=bool(data.get("stitch_disabled", False)),
            max_video_post_duration_sec=int(data.get("max_video_post_duration_sec", 0) or 0),
        )


@dataclass(slots=True)
class PostOptions:
    """Opções de um post.

    Os defaults aqui divergem de propósito dos defaults da API, em dois pontos
    onde o default da API produz um resultado que ninguém quer:

    - volumes de áudio: a API usa 0 (post mudo); o app TikTok usa 50.
    - rótulos comerciais: a API exige os dois campos, então ficam explícitos.
    """

    caption: str = ""
    is_brand_organic: bool = False
    is_branded_content: bool = False
    disable_comment: bool = False
    disable_duet: bool = False
    disable_stitch: bool = False
    thumbnail_offset_ms: int | None = None
    is_ai_generated: bool = False  # irreversível depois de publicado
    upload_to_draft: bool = False
    is_ads_only: bool = False
    music_sound_volume: int = 50
    video_original_sound_volume: int = 50
    location_id: str | None = None
    location_name: str | None = None

    def validate(self, settings: AccountSettings) -> None:
        if len(self.caption) > CAPTION_MAX_CHARS:
            raise MediaError(
                f"legenda com {len(self.caption)} caracteres; o máximo é {CAPTION_MAX_CHARS}"
            )
        if self.caption.count("@") > CAPTION_MAX_MENTIONS:
            raise MediaError(f"máximo de {CAPTION_MAX_MENTIONS} menções por legenda")
        # Só se pode desligar o que a conta já permite.
        if settings.comment_disabled and not self.disable_comment:
            raise MediaError(
                "a conta tem comentários desativados; disable_comment precisa ser True"
            )
        if settings.duet_disabled and not self.disable_duet:
            raise MediaError("a conta tem duetos desativados; disable_duet precisa ser True")
        if settings.stitch_disabled and not self.disable_stitch:
            raise MediaError("a conta tem stitch desativado; disable_stitch precisa ser True")

    def to_post_info(self) -> dict[str, Any]:
        if self.upload_to_draft:
            # Documentado: com upload_to_draft todos os outros campos de
            # post_info são ignorados. Mandar só ele evita confusão no log.
            return {"upload_to_draft": True}

        info: dict[str, Any] = {
            "caption": self.caption,
            "is_brand_organic": self.is_brand_organic,
            "is_branded_content": self.is_branded_content,
            "disable_comment": self.disable_comment,
            "disable_duet": self.disable_duet,
            "disable_stitch": self.disable_stitch,
            "is_ai_generated": self.is_ai_generated,
            "is_ads_only": self.is_ads_only,
            "music_sound_info": {
                "music_sound_volume": self.music_sound_volume,
                "video_original_sound_volume": self.video_original_sound_volume,
            },
        }
        if self.thumbnail_offset_ms is not None:
            info["thumbnail_offset"] = self.thumbnail_offset_ms
        if self.location_id:
            info["location_id"] = self.location_id
            info["location_name"] = self.location_name
        return info


class OrganicPublisher:
    """Fluxo completo: pré-voo → publicação → acompanhamento de status."""

    def __init__(self, client: TikTokClient, business_id: str):
        self.client = client
        self.business_id = business_id

    def get_settings(self) -> AccountSettings:
        data = self.client.get("business/video/settings", business_id=self.business_id)
        return AccountSettings.from_api(data)

    def publish_video(
        self,
        video_url: str,
        options: PostOptions,
        *,
        custom_thumbnail_url: str | None = None,
        duration_sec: float | None = None,
        settings: AccountSettings | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        settings = settings or self.get_settings()
        options.validate(settings)

        if (
            duration_sec is not None
            and settings.max_video_post_duration_sec
            and duration_sec > settings.max_video_post_duration_sec
        ):
            raise MediaError(
                f"vídeo tem {duration_sec:.0f}s; esta conta aceita no máximo "
                f"{settings.max_video_post_duration_sec}s"
            )

        payload: dict[str, Any] = {
            "business_id": self.business_id,
            "video_url": video_url,
            "post_info": options.to_post_info(),
        }
        if custom_thumbnail_url:
            payload["custom_thumbnail_url"] = custom_thumbnail_url

        if dry_run:
            return {"dry_run": True, "payload": payload}

        return self.client.post("business/video/publish", payload)

    def get_status(self, share_id: str) -> dict[str, Any]:
        return self.client.get(
            "business/publish/status", business_id=self.business_id, share_id=share_id
        )

    def wait_for_publish(
        self, share_id: str, *, timeout_sec: int = 600, intervalo_sec: int = 10
    ) -> dict[str, Any]:
        """Acompanha até um estado terminal.

        Não há webhook de publicação garantido para todos os casos, então o
        polling é o caminho confiável.
        """
        limite = time.monotonic() + timeout_sec
        ultimo: dict[str, Any] = {}
        while time.monotonic() < limite:
            ultimo = self.get_status(share_id)
            status = str(ultimo.get("status", "")).upper()
            if status in {"PUBLISH_COMPLETE", "FAILED"}:
                return ultimo
            time.sleep(intervalo_sec)
        return {**ultimo, "status": "TIMEOUT"}
