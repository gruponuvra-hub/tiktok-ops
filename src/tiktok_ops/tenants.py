"""Registro de operações (tenants).

O projeto foi feito para ser replicado: a mesma instalação atende várias
agências e vários clientes. Cada operação é um arquivo `tenants/<nome>.env` e um
arquivo de token próprio — nada de conta fica no código.

    tiktok-ops --tenant agencia-x ads list
    tiktok-ops --tenant cliente-y organic settings
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

NOME_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")

TEMPLATE = """# Operação: {nome}
# Gerado por `tiktok-ops init`. Este arquivo nunca vai para o Git.

# --- App de desenvolvedor (compartilhado entre as operações que você atende) ---
TIKTOK_APP_ID={app_id}
TIKTOK_APP_SECRET={app_secret}

# --- Business Center desta operação ---
# Agências operam por BC: as contas de anúncio ficam penduradas nele.
# Descubra com: tiktok-ops --tenant {nome} bc list
TIKTOK_BC_ID={bc_id}

# Conta de anúncio padrão. Deixe vazio para escolher a cada comando com
# --advertiser, ou descubra com: tiktok-ops --tenant {nome} bc advertisers
TIKTOK_ADVERTISER_ID=
TIKTOK_MARKETING_ACCESS_TOKEN=

# --- Conta TikTok para publicação orgânica ---
TIKTOK_BUSINESS_ID=
TIKTOK_ACCOUNTS_ACCESS_TOKEN=
TIKTOK_ACCOUNTS_REFRESH_TOKEN=

# --- Mídia ---
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=tiktok-media
R2_PUBLIC_BASE_URL=

GOOGLE_SERVICE_ACCOUNT_FILE=./data/google-service-account.json
GOOGLE_DRIVE_FOLDER_ID=

TIKTOK_OPS_DRY_RUN=true
"""


class NomeInvalido(ValueError):
    pass


@dataclass(slots=True)
class Tenant:
    nome: str
    env_file: Path

    @property
    def existe(self) -> bool:
        return self.env_file.exists()


class TenantRegistry:
    def __init__(self, root: Path | str = "tenants"):
        self.root = Path(root)

    def _validar(self, nome: str) -> str:
        if not NOME_VALIDO.match(nome):
            raise NomeInvalido(
                f"'{nome}' não serve como nome de operação. Use minúsculas, números e "
                "hífens, de 2 a 41 caracteres — por exemplo: agencia-zebra."
            )
        return nome

    def get(self, nome: str) -> Tenant:
        self._validar(nome)
        return Tenant(nome=nome, env_file=self.root / f"{nome}.env")

    def list(self) -> list[Tenant]:
        if not self.root.exists():
            return []
        return [
            Tenant(nome=p.stem, env_file=p)
            for p in sorted(self.root.glob("*.env"))
        ]

    def create(
        self, nome: str, *, app_id: str = "", app_secret: str = "", bc_id: str = ""
    ) -> Tenant:
        tenant = self.get(nome)
        if tenant.existe:
            raise FileExistsError(
                f"a operação '{nome}' já existe em {tenant.env_file}. "
                "Edite o arquivo ou escolha outro nome."
            )
        self.root.mkdir(parents=True, exist_ok=True)
        tenant.env_file.write_text(
            TEMPLATE.format(
                nome=nome, app_id=app_id, app_secret=app_secret, bc_id=bc_id
            ),
            encoding="utf-8",
        )
        return tenant

    def resolve_env_file(self, nome: str | None) -> Path | None:
        """Arquivo de ambiente a carregar. `None` significa usar o `.env` da raiz."""
        if not nome:
            return None
        tenant = self.get(nome)
        if not tenant.existe:
            disponiveis = ", ".join(t.nome for t in self.list()) or "nenhuma"
            raise FileNotFoundError(
                f"operação '{nome}' não encontrada. Disponíveis: {disponiveis}.\n"
                f"Crie com: tiktok-ops init {nome}"
            )
        return tenant.env_file
