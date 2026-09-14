"""Exceções mapeadas aos códigos de retorno da TikTok Business API.

A TikTok devolve HTTP 200 mesmo quando a operação falhou; o que vale é o campo
`code` do corpo. Todo erro sobe por aqui para que a CLI possa decidir entre
esperar, avisar ou abortar.
"""

from __future__ import annotations

# Códigos que significam "tente de novo depois", não "sua requisição está errada".
THROTTLE_CODES = {
    40100,  # limite de endpoint no nível do app
    40016,  # limite de endpoint no nível do app
    40133,  # limite de QPS no nível do anunciante
    40132,  # limite de QPS por valor de campo
}

# Códigos que indicam credencial/permissão — nunca adianta repetir.
AUTH_CODES = {
    40001,  # token ausente ou inválido
    40002,  # parâmetro inválido (frequentemente escopo/permissão)
    40107,  # refresh em token que não tem refresh
    40113,  # app_id inconsistente com o token
    40119,  # desenvolvedor e anunciante de empresas diferentes
}


class TikTokError(Exception):
    """Erro de aplicação devolvido pela API (HTTP 200 com `code` != 0)."""

    def __init__(self, code: int, message: str, *, path: str = "", request_id: str = ""):
        self.code = code
        self.message = message
        self.path = path
        self.request_id = request_id
        super().__init__(f"[{code}] {message}" + (f" (em {path})" if path else ""))

    @property
    def is_throttle(self) -> bool:
        return self.code in THROTTLE_CODES

    @property
    def is_auth(self) -> bool:
        return self.code in AUTH_CODES


class RateLimited(TikTokError):
    """Limite de requisições atingido.

    Regra da TikTok: QPM estourado espera 5 minutos; QPD estourado espera até
    00:00 UTC. `retry_after` traz o tempo sugerido em segundos.
    """

    def __init__(self, code: int, message: str, *, retry_after: int = 300, **kw):
        self.retry_after = retry_after
        super().__init__(code, message, **kw)


class ConfigError(Exception):
    """Falta configuração obrigatória no .env."""


class MediaError(Exception):
    """Mídia não atende às restrições da TikTok."""


class NotAuthorizedYet(Exception):
    """Operação exige um cadastro/aprovação que ainda não saiu.

    Levantada de propósito para que o app seja utilizável antes do cadastro sair,
    com mensagem explicando o que falta em vez de um 401 opaco.
    """
