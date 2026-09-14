"""Hospedagem das mídias no Cloudflare R2.

A TikTok exige que a URL seja HTTPS, esteja em domínio verificado e **não
redirecione** — qualquer `3xx` invalida. Por isso servimos de um domínio
customizado apontado para o bucket, não de URL assinada.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

# A TikTok pede TTL mínimo de 30 minutos na URL; uma hora dá folga confortável.
CACHE_CONTROL = "public, max-age=3600"


class R2Storage:
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str,
    ):
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self._account_id = account_id
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=f"https://{self._account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
                region_name="auto",
            )
        return self._client

    def upload(self, caminho_local: Path, key: str | None = None) -> str:
        """Sobe o arquivo e devolve a URL pública (a que vai para a TikTok)."""
        caminho_local = Path(caminho_local)
        key = key or caminho_local.name
        content_type = mimetypes.guess_type(caminho_local.name)[0] or "application/octet-stream"

        self._get_client().upload_file(
            str(caminho_local),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type, "CacheControl": CACHE_CONTROL},
        )
        return self.public_url(key)

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key.lstrip('/')}"

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._get_client().head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
