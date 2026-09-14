"""Verificação de propriedade de URL.

Sem uma propriedade verificada a TikTok recusa qualquer `video_url` seu. Duas
regras que derrubam integrações:

- verificação de domínio casa subdomínios **para baixo** (verificar
  `media.exemplo.com` cobre `cdn.media.exemplo.com`, mas nunca `exemplo.com`);
- qualquer redirecionamento `HTTP 3xx` invalida a URL, o que elimina URLs
  assinadas que redirecionam.
"""

from __future__ import annotations

from typing import Any, Literal

from ..http import TikTokClient

PropertyType = Literal["DOMAIN", "URL_PREFIX"]


class UrlProperties:
    def __init__(self, client: TikTokClient, app_id: str):
        self.client = client
        self.app_id = app_id

    def add(self, value: str, property_type: PropertyType = "DOMAIN") -> dict[str, Any]:
        """Registra a propriedade e devolve a assinatura a ser publicada.

        DOMAIN → criar registro DNS TXT com o `signature` devolvido.
        URL_PREFIX → subir arquivo com o nome e o conteúdo devolvidos.
        """
        return self.client.post(
            "business/property/add",
            {"app_id": self.app_id, "property_type": property_type, "property_value": value},
        )

    def check(self, property_id: str) -> dict[str, Any]:
        """Pede à TikTok que valide a assinatura publicada."""
        return self.client.post(
            "business/property/check", {"app_id": self.app_id, "property_id": property_id}
        )

    def list(self) -> list[dict[str, Any]]:
        data = self.client.get("business/property/list", app_id=self.app_id)
        return data.get("properties", data.get("list", []))

    def delete(self, property_id: str) -> dict[str, Any]:
        return self.client.post(
            "business/property/delete", {"app_id": self.app_id, "property_id": property_id}
        )

    @staticmethod
    def covers(dominio_verificado: str, url: str) -> bool:
        """Checagem local do casamento de subdomínio, antes de gastar chamada."""
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
        alvo = dominio_verificado.lower().lstrip(".")
        return host == alvo or host.endswith("." + alvo)
