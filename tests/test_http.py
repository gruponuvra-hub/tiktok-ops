"""O cliente HTTP precisa tratar HTTP 200 com falha no corpo."""

import httpx
import pytest

from tiktok_ops.errors import RateLimited, TikTokError
from tiktok_ops.http import TikTokClient


def _resposta(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://x/"))


def test_code_zero_e_sucesso():
    data = TikTokClient._unwrap(_resposta({"code": 0, "data": {"ok": True}}), "x")
    assert data == {"ok": True}


def test_http_200_com_code_de_erro_vira_excecao():
    # A armadilha central da API: status 200, operação falhada.
    with pytest.raises(TikTokError) as exc:
        TikTokClient._unwrap(_resposta({"code": 40002, "message": "param invalido"}), "x")
    assert exc.value.code == 40002


def test_codigo_de_throttle_vira_rate_limited():
    with pytest.raises(RateLimited) as exc:
        TikTokClient._unwrap(_resposta({"code": 40100, "message": "limite"}), "x")
    assert exc.value.retry_after == 300


def test_resposta_nao_json_tem_mensagem_util():
    resp = httpx.Response(404, text="404 page not found", request=httpx.Request("GET", "https://x/"))
    with pytest.raises(TikTokError, match="não-JSON"):
        TikTokClient._unwrap(resp, "campaign/get")


def test_url_sempre_termina_com_barra():
    # Sem a barra final a TikTok devolve 404 em texto puro.
    c = TikTokClient("token")
    assert c._url("campaign/get").endswith("/campaign/get/")
    assert c._url("/campaign/get/").endswith("/campaign/get/")
