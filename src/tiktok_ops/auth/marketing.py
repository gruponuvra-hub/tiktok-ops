"""OAuth do Marketing API — autorização de contas de anúncio.

Diferente do orgânico: o `auth_code` vale 1 hora, e o access token resultante
**não expira e não tem refresh token**. Tentar dar refresh nele devolve o erro
40107.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import BUSINESS_API_BASE, Settings
from ..errors import TikTokError
from .store import TokenStore


class MarketingAuth:
    def __init__(self, settings: Settings, tenant: str | None = None):
        self.s = settings
        # Tokens ficam separados por operação para não se misturarem entre clientes.
        self.store = TokenStore(
            settings.data_dir, f"{tenant or settings.token_namespace}-marketing"
        )

    def exchange_code(self, auth_code: str) -> dict[str, Any]:
        self.s.require("tiktok_app_id", "tiktok_app_secret")
        url = f"{BUSINESS_API_BASE}/oauth2/access_token/"
        resp = httpx.post(
            url,
            json={
                "app_id": self.s.tiktok_app_id,
                "secret": self.s.tiktok_app_secret,
                "auth_code": auth_code,
            },
            timeout=30.0,
        )
        body = resp.json()
        if int(body.get("code", -1)) != 0:
            raise TikTokError(int(body.get("code", -1)), body.get("message", ""))
        data = body.get("data") or {}
        self.store.write(
            access_token=data.get("access_token", ""),
            advertiser_ids=data.get("advertiser_ids", []),
            scope=data.get("scope", []),
        )
        return data

    def access_token(self) -> str:
        tok = self.store.read().get("access_token") or self.s.tiktok_marketing_access_token
        if not tok:
            raise TikTokError(
                40001, "sem token do Marketing API — rode `tiktok-ops auth marketing`"
            )
        return tok

    def advertiser_ids(self) -> list[str]:
        """Lista as contas de anúncio que o token alcança.

        Peculiaridade documentada: este endpoint exige `app_id` e `secret` na
        query string *além* do header de token.
        """
        url = f"{BUSINESS_API_BASE}/oauth2/advertiser/get/"
        resp = httpx.get(
            url,
            headers={"Access-Token": self.access_token()},
            params={"app_id": self.s.tiktok_app_id, "secret": self.s.tiktok_app_secret},
            timeout=30.0,
        )
        body = resp.json()
        if int(body.get("code", -1)) != 0:
            raise TikTokError(int(body.get("code", -1)), body.get("message", ""))
        return [a["advertiser_id"] for a in (body.get("data") or {}).get("list", [])]
