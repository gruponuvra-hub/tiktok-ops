"""Origem das mídias: uma pasta do Google Drive.

Regra de ouro: **os bytes do vídeo nunca passam pelo contexto do agente nem por
MCP.** O `download_file_content` do Google Drive MCP devolve o conteúdo como
string base64 dentro da resposta da ferramenta e quebra muito abaixo do tamanho
de um vídeo. Aqui o download é resumível, direto para disco.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

MIME_VIDEO = "video/"
MIME_IMAGE = "image/"


@dataclass(slots=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    size_bytes: int
    modified_time: str

    @property
    def is_video(self) -> bool:
        return self.mime_type.startswith(MIME_VIDEO)

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith(MIME_IMAGE)


class DriveSource:
    def __init__(self, service_account_file: Path, folder_id: str):
        self.service_account_file = Path(service_account_file)
        self.folder_id = folder_id
        self._service: Any | None = None

    def _get_service(self) -> Any:
        if self._service is None:
            from google.oauth2 import service_account  # import tardio: dependência pesada
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(self.service_account_file), scopes=SCOPES
            )
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def list_media(self, *, apenas_video: bool = False) -> Iterator[DriveFile]:
        """Lista os arquivos da pasta — só metadados, nunca conteúdo."""
        service = self._get_service()
        query = f"'{self.folder_id}' in parents and trashed = false"
        page_token: str | None = None

        while True:
            resp = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                arquivo = DriveFile(
                    id=f["id"],
                    name=f["name"],
                    mime_type=f.get("mimeType", ""),
                    size_bytes=int(f.get("size", 0) or 0),
                    modified_time=f.get("modifiedTime", ""),
                )
                if apenas_video and not arquivo.is_video:
                    continue
                yield arquivo
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    def download(self, file: DriveFile, destino_dir: Path, *, chunk_mb: int = 16) -> Path:
        """Baixa para disco em blocos. Retorna o caminho local."""
        from googleapiclient.http import MediaIoBaseDownload

        destino_dir = Path(destino_dir)
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / file.name

        if destino.exists() and destino.stat().st_size == file.size_bytes:
            return destino  # já baixado e íntegro

        service = self._get_service()
        request = service.files().get_media(fileId=file.id)
        with io.FileIO(destino, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=chunk_mb * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return destino
