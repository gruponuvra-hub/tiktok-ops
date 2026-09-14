"""Casamento de subdomínio na verificação de propriedade de URL."""

from tiktok_ops.organic.properties import UrlProperties


def test_dominio_verificado_cobre_subdominio_abaixo():
    assert UrlProperties.covers("media.exemplo.com", "https://media.exemplo.com/a.mp4")
    assert UrlProperties.covers("media.exemplo.com", "https://cdn.media.exemplo.com/a.mp4")


def test_dominio_verificado_nao_cobre_o_dominio_pai():
    # Erro clássico: verificar o subdomínio e servir da raiz.
    assert not UrlProperties.covers("media.exemplo.com", "https://exemplo.com/a.mp4")
    assert not UrlProperties.covers("media.exemplo.com", "https://outro.com/a.mp4")
