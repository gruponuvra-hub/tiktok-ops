"""Cliente HTTP base da TikTok Business API.

Todo módulo de domínio passa por aqui. Motivo: a TikTok tem duas armadilhas que
não dá para tratar caso a caso.

1. Ela devolve `HTTP 200` em falhas de aplicação. O que vale é o campo `code` do
   corpo (`0` = sucesso). Quem chama `httpx` direto acaba tratando erro como
   sucesso.
2. A barra final na URL é obrigatória. Sem ela a resposta é um `404 page not
   found` em texto puro, que nem sequer é JSON.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

import httpx

from .config import BUSINESS_API_BASE
from .errors import RateLimited, TikTokError, THROTTLE_CODES

log = logging.getLogger("tiktok_ops.http")

# Espera recomendada pela TikTok quando o limite por minuto estoura.
QPM_BACKOFF_SECONDS = 300


class TikTokClient:
    """Wrapper fino sobre httpx com as regras da TikTok embutidas."""

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = BUSINESS_API_BASE,
        timeout: float = 30.0,
        max_retries: int = 3,
        wait_on_throttle: bool = False,
    ):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        # Desligado por padrão: esperar 5 minutos dentro de uma CLI interativa é
        # pior que falhar rápido. Jobs em background ligam isso.
        self.wait_on_throttle = wait_on_throttle
        self._client = httpx.Client(timeout=timeout)

    # -- infraestrutura ----------------------------------------------------

    def _url(self, path: str) -> str:
        path = path.strip("/")
        # A barra final não é estética: sem ela a API devolve 404 em texto puro.
        return f"{self.base_url}/{path}/"

    def _headers(self) -> dict[str, str]:
        return {
            "Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _unwrap(resp: httpx.Response, path: str) -> dict[str, Any]:
        """Extrai `data` validando o `code` do corpo, não o status HTTP."""
        try:
            body = resp.json()
        except ValueError:
            raise TikTokError(
                -1,
                f"resposta não-JSON (HTTP {resp.status_code}): {resp.text[:200]}",
                path=path,
            ) from None

        code = int(body.get("code", -1))
        if code == 0:
            return body.get("data") or {}

        message = body.get("message", "sem mensagem")
        request_id = body.get("request_id", "")
        if code in THROTTLE_CODES:
            raise RateLimited(
                code, message, retry_after=QPM_BACKOFF_SECONDS,
                path=path, request_id=request_id,
            )
        raise TikTokError(code, message, path=path, request_id=request_id)

    def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self._url(path)
        ultima: Exception | None = None

        for tentativa in range(1, self.max_retries + 1):
            try:
                resp = self._client.request(
                    method, url, headers=self._headers(), params=params, json=json
                )
                return self._unwrap(resp, path)
            except RateLimited as exc:
                ultima = exc
                if not self.wait_on_throttle or tentativa == self.max_retries:
                    raise
                log.warning(
                    "throttle em %s (code %s) — aguardando %ss (tentativa %s/%s)",
                    path, exc.code, exc.retry_after, tentativa, self.max_retries,
                )
                time.sleep(exc.retry_after)
            except httpx.TransportError as exc:
                ultima = exc
                if tentativa == self.max_retries:
                    raise
                espera = 2 ** tentativa
                log.warning("erro de transporte em %s: %s — retry em %ss", path, exc, espera)
                time.sleep(espera)

        raise ultima or RuntimeError("estado inalcançável")

    # -- API pública -------------------------------------------------------

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        # A TikTok espera listas/objetos como JSON serializado na query string.
        limpos = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=limpos)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        limpos = {k: v for k, v in payload.items() if v is not None}
        return self._request("POST", path, json=limpos)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TikTokClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
