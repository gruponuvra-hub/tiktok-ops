"""Persistência de tokens em disco.

Arquivo por operação (`tenant`), para que o mesmo código sirva várias contas.
O diretório fica no .gitignore — token nunca entra no repositório.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class TokenStore:
    def __init__(self, data_dir: Path, tenant: str = "default"):
        self.path = Path(data_dir) / "tokens" / f"{tenant}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, **valores: Any) -> dict[str, Any]:
        atual = self.read()
        atual.update(valores)
        self.path.write_text(json.dumps(atual, indent=2), encoding="utf-8")
        # Permissão restrita onde o SO suportar.
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return atual

    def save_token_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Grava a resposta do OAuth calculando o vencimento absoluto."""
        agora = datetime.now(timezone.utc)
        expires_in = int(data.get("expires_in", 0) or 0)
        refresh_expires_in = int(data.get("refresh_expires_in", 0) or 0)
        return self.write(
            access_token=data.get("access_token", ""),
            # A TikTok pode devolver um refresh token diferente do enviado.
            # Guardar o novo é obrigatório, senão o refresh quebra depois.
            refresh_token=data.get("refresh_token", ""),
            open_id=data.get("open_id", ""),
            scope=data.get("scope", ""),
            expires_at=(agora + timedelta(seconds=expires_in)).isoformat() if expires_in else "",
            refresh_expires_at=(
                (agora + timedelta(seconds=refresh_expires_in)).isoformat()
                if refresh_expires_in else ""
            ),
        )

    def is_expired(self, *, margem_segundos: int = 300) -> bool:
        expires_at = self.read().get("expires_at")
        if not expires_at:
            return True
        venc = datetime.fromisoformat(expires_at)
        return datetime.now(timezone.utc) >= venc - timedelta(seconds=margem_segundos)
