"""Testes das regras de campanha."""

import pytest

from tiktok_ops.ads.campaigns import AdGroupSpec, CampaignSpec


def test_infinite_e_o_default_por_causa_da_contradicao_de_piso():
    spec = CampaignSpec(campaign_name="teste")
    assert spec.budget_mode == "BUDGET_MODE_INFINITE"
    spec.validate()  # não exige budget


def test_infinite_nao_convive_com_cbo():
    with pytest.raises(ValueError, match="CBO"):
        CampaignSpec(campaign_name="t", budget_optimize_on=True).validate()


def test_orcamento_de_campanha_abaixo_do_piso_seguro_e_barrado():
    with pytest.raises(ValueError, match="piso seguro"):
        CampaignSpec(campaign_name="t", budget_mode="BUDGET_MODE_DAY", budget=30).validate()


def test_orcamento_de_ad_group_respeita_o_piso_de_20():
    with pytest.raises(ValueError, match="mínimo"):
        AdGroupSpec(campaign_id="1", adgroup_name="g", budget=19).validate()
    AdGroupSpec(campaign_id="1", adgroup_name="g", budget=20).validate()


def test_request_id_e_gerado_para_idempotencia():
    payload = CampaignSpec(campaign_name="t").to_payload("adv123")
    assert payload["request_id"]
    assert payload["advertiser_id"] == "adv123"
