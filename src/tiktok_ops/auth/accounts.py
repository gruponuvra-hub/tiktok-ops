"""OAuth da Accounts API — autorização de uma conta TikTok (orgânico).

Ciclo de vida: `auth_code` vale 10 minutos e é de uso único; o access token vale
24 horas; o refresh token vale 1 ano. Passado 1 ano, o dono da conta precisa
reautorizar do zero — não há como estender.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import BUSINESS_API_BASE, Settings
from ..errors import TikTokError
from .store import TokenStore


class AccountsAuth:
    def __init__(self, settings: Settings, tenant: str | None = None):
        self.s = settings
        # Tokens ficam separados por operação para não se misturarem entre clientes.
        self.store = TokenStore(settings.data_dir, tenant or settings.token_namespace)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{BUSINESS_API_BASE}/{path.strip('/')}/"
        resp = httpx.post(url, json=payload, timeout=30.0)
        body = resp.json()
        if int(body.get("code", -1)) != 0:
            raise TikTokError(
                int(body.get("code", -1)), body.get("message", ""), path=path
            )
        return body.get("data") or {}

    def exchange_code(self, auth_code: str) -> dict[str, Any]:
        """Troca o `auth_code` do callback pelo primeiro par de tokens."""
        self.s.require("tiktok_app_id", "tiktok_app_secret")
        data = self._post(
            "tt_user/oauth2/token",
            {
                "app_id": self.s.tiktok_app_id,
                "secret": self.s.tiktok_app_secret,
                "auth_code": auth_code,
                "grant_type": "authorization_code",
            },
        )
        return self.store.save_token_response(data)

    def refresh(self) -> dict[str, Any]:
        refresh_token = self.store.read().get("refresh_token") or self.s.tiktok_accounts_refresh_token
        if not refresh_token:
            raise TikTokError(40001, "sem refresh token — refaça a autorização da conta")
        data = self._post(
            "tt_user/oauth2/refresh_token",
            {
                "app_id": self.s.tiktok_app_id,
                "secret": self.s.tiktok_app_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        return self.store.save_token_response(data)

    def access_token(self) -> str:
        """Token válido, renovando de forma transparente quando perto de vencer."""
        guardado = self.store.read()
        if guardado.get("access_token") and not self.store.is_expired():
            return guardado["access_token"]
        if guardado.get("refresh_token") or self.s.tiktok_accounts_refresh_token:
            return self.refresh()["access_token"]
        if self.s.tiktok_accounts_access_token:
            return self.s.tiktok_accounts_access_token
        raise TikTokError(40001, "nenhuma conta TikTok autorizada — rode `tiktok-ops auth accounts`")

    def business_id(self) -> str:
        return self.store.read().get("open_id") or self.s.tiktok_business_id
