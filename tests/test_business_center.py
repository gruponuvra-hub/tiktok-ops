"""Resolução de contas de anúncio a partir do Business Center."""

import pytest

from tiktok_ops.ads.business_center import AdvertiserInfo, BusinessCenter, BusinessCenterInfo


class FakeBC(BusinessCenter):
    """Substitui a chamada de rede por uma carteira fixa."""

    def __init__(self, contas):
        self._contas = contas

    def list_all_advertisers(self, bc_id):  # type: ignore[override]
        return self._contas


CARTEIRA = [
    AdvertiserInfo("111", "Padaria do Zé", "BRL", "America/Sao_Paulo", "STATUS_ENABLE"),
    AdvertiserInfo("222", "Clínica Vida", "BRL", "America/Sao_Paulo", "STATUS_ENABLE"),
    AdvertiserInfo("333", "Clínica Bem Estar", "BRL", "America/Sao_Paulo", "STATUS_ENABLE"),
]


def test_tipo_agencia_e_reconhecido():
    assert BusinessCenterInfo("1", "n", "c", "AGENCY", "ok").e_agencia
    assert BusinessCenterInfo("1", "n", "c", "SELF_SERVICE_AGENCY", "ok").e_agencia
    assert not BusinessCenterInfo("1", "n", "c", "DIRECT", "ok").e_agencia


def test_resolve_por_id():
    assert FakeBC(CARTEIRA).resolver_advertiser("bc", "222").name == "Clínica Vida"


def test_resolve_por_trecho_do_nome():
    assert FakeBC(CARTEIRA).resolver_advertiser("bc", "padaria").advertiser_id == "111"


def test_nome_ambiguo_falha_em_vez_de_escolher():
    # Errar a conta de um cliente é pior que pedir para a pessoa ser específica.
    with pytest.raises(LookupError, match="ambíguo"):
        FakeBC(CARTEIRA).resolver_advertiser("bc", "clínica")


def test_nome_inexistente_lista_as_opcoes():
    with pytest.raises(LookupError, match="Padaria do Zé"):
        FakeBC(CARTEIRA).resolver_advertiser("bc", "farmácia")


def test_parse_da_resposta_aninhada():
    bc = BusinessCenterInfo.from_api({"bc_info": {"bc_id": 7, "name": "X", "bc_type": "AGENCY"}})
    assert bc.bc_id == "7" and bc.e_agencia
    adv = AdvertiserInfo.from_api({"advertiser_info": {"advertiser_id": 9, "name": "Y"}})
    assert adv.advertiser_id == "9" and adv.name == "Y"
