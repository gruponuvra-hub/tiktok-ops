"""Pipeline Drive → disco → R2 → URL pronta para a TikTok.

Também valida as restrições de mídia antes de gastar uma chamada de publicação:
vídeo orgânico aceita até 1 GB, 3 a 600 segundos, mínimo 360×360 e 23 a 60 FPS.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..errors import MediaError
from .drive import DriveFile, DriveSource
from .r2 import R2Storage

MAX_VIDEO_BYTES = 1_073_741_824  # 1 GB
MIN_DURACAO_SEG = 3
MAX_DURACAO_SEG = 600
MIN_DIMENSAO_PX = 360
MIN_FPS = 23
MAX_FPS = 60


@dataclass(slots=True)
class VideoInfo:
    duration_sec: float
    width: int
    height: int
    fps: float
    size_bytes: int


def probe(caminho: Path) -> VideoInfo:
    """Lê metadados com ffprobe. Falha com mensagem clara se não estiver instalado."""
    try:
        saida = subprocess.run(
            [
                "ffprobe", "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(caminho),
            ],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        raise MediaError(
            "ffprobe não encontrado. Instale o ffmpeg para validar mídia localmente."
        ) from None
    except subprocess.CalledProcessError as exc:
        raise MediaError(f"ffprobe falhou em {caminho.name}: {exc.stderr[:200]}") from None

    dados = json.loads(saida)
    stream = next((s for s in dados.get("streams", []) if s.get("codec_type") == "video"), None)
    if stream is None:
        raise MediaError(f"{caminho.name} não tem stream de vídeo")

    num, _, den = stream.get("avg_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0

    return VideoInfo(
        duration_sec=float(dados.get("format", {}).get("duration", 0) or 0),
        width=int(stream.get("width", 0) or 0),
        height=int(stream.get("height", 0) or 0),
        fps=fps,
        size_bytes=caminho.stat().st_size,
    )


def validar_video(info: VideoInfo) -> list[str]:
    """Devolve a lista de problemas. Lista vazia significa aprovado."""
    problemas: list[str] = []
    if info.size_bytes > MAX_VIDEO_BYTES:
        problemas.append(f"tamanho {info.size_bytes / 1e9:.2f} GB excede o limite de 1 GB")
    if not MIN_DURACAO_SEG <= info.duration_sec <= MAX_DURACAO_SEG:
        problemas.append(
            f"duração de {info.duration_sec:.1f}s fora da faixa "
            f"{MIN_DURACAO_SEG}–{MAX_DURACAO_SEG}s"
        )
    if min(info.width, info.height) < MIN_DIMENSAO_PX:
        problemas.append(f"resolução {info.width}x{info.height} abaixo de {MIN_DIMENSAO_PX}px")
    if info.fps and not MIN_FPS <= info.fps <= MAX_FPS:
        problemas.append(f"{info.fps:.1f} FPS fora da faixa {MIN_FPS}–{MAX_FPS}")
    return problemas


class MediaPipeline:
    def __init__(self, drive: DriveSource, storage: R2Storage, work_dir: Path):
        self.drive = drive
        self.storage = storage
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def preparar(self, arquivo: DriveFile, *, validar: bool = True) -> tuple[str, VideoInfo | None]:
        """Baixa, valida e publica no R2. Devolve a URL e os metadados."""
        local = self.drive.download(arquivo, self.work_dir)

        info: VideoInfo | None = None
        if validar and arquivo.is_video:
            info = probe(local)
            problemas = validar_video(info)
            if problemas:
                raise MediaError(f"{arquivo.name}: " + "; ".join(problemas))

        url = self.storage.upload(local)
        return url, info
