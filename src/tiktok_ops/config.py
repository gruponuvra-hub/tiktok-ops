"""Configuração por operação (tenant).

Nenhum valor de conta é hardcoded. A mesma instalação atende várias agências e
vários clientes: cada operação é um arquivo em `tenants/<nome>.env`, e o `.env`
da raiz serve como padrão para quem opera uma conta só.

Precedência: `--tenant` na CLI > `TIKTOK_OPS_TENANT` > `TIKTOK_OPS_ENV_FILE` > `.env`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigError
from .tenants import TenantRegistry

# URL de teste oficial da TikTok: aceita sem verificação de propriedade de URL.
# Serve para exercitar o fluxo de publicação antes de ter domínio verificado.
TIKTOK_TEST_VIDEO_URL = (
    "https://sf16-va.tiktokcdn.com/obj/eden-va2/"
    "uvpapzpbxjH-aulauvJ-WV[[/ljhwZthlaukjlkulzlp/3min.mp4"
)

BUSINESS_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

# Servidor MCP oficial da TikTok para anúncios. Público: não exige app de
# desenvolvedor nem e-mail corporativo, só uma conta TikTok for Business.
TIKTOK_ADS_MCP_URL = "https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat"
TIKTOK_ADS_MCP_URL_LAYERED = "https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Identidade da operação — preenchida pelo carregador, não pelo arquivo.
    tenant: str = ""

    # App de desenvolvedor
    tiktok_app_id: str = ""
    tiktok_app_secret: str = ""

    # Business Center — o ponto de entrada de quem opera como agência
    tiktok_bc_id: str = ""

    # Marketing API (anúncios)
    tiktok_advertiser_id: str = ""
    tiktok_marketing_access_token: str = ""

    # Accounts API (orgânico)
    tiktok_business_id: str = ""
    tiktok_accounts_access_token: str = ""
    tiktok_accounts_refresh_token: str = ""

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "tiktok-media"
    r2_public_base_url: str = ""

    # Google Drive
    google_service_account_file: Path = Path("./data/google-service-account.json")
    google_drive_folder_id: str = ""

    # Operação
    tiktok_ops_env: str = "dev"
    tiktok_ops_dry_run: bool = True
    data_dir: Path = Field(default=Path("./data"))

    def require(self, *names: str) -> None:
        """Falha cedo e com mensagem útil quando falta configuração."""
        faltando = [n for n in names if not getattr(self, n, "")]
        if not faltando:
            return
        onde = f"tenants/{self.tenant}.env" if self.tenant else ".env"
        raise ConfigError(
            "Faltam variáveis em " + onde + ": " + ", ".join(sorted(faltando)) +
            "\nVeja .env.example e o checklist em CLAUDE.md."
        )

    @property
    def media_base_url(self) -> str:
        return self.r2_public_base_url.rstrip("/")

    @property
    def token_namespace(self) -> str:
        """Separa os tokens por operação, para que não se misturem."""
        return self.tenant or "default"


@lru_cache
def get_settings(tenant: str | None = None) -> Settings:
    nome = tenant or os.getenv("TIKTOK_OPS_TENANT") or ""
    env_file = TenantRegistry().resolve_env_file(nome) if nome else None
    if env_file is None:
        env_file = os.getenv("TIKTOK_OPS_ENV_FILE", ".env")
    s = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
    s.tenant = nome
    return s
