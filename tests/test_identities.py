"""Resolução de identidade — de qual conta o anúncio sai."""

import pytest

from tiktok_ops.ads.identities import Identities, IdentityInfo


class FakeIdentities(Identities):
    def __init__(self, itens):
        self._itens = itens

    def list(self, identity_type="TT_USER", *, page_size=100):  # type: ignore[override]
        return self._itens


TT = lambda i, n: IdentityInfo(i, "TT_USER", n)  # noqa: E731


def test_so_tipos_de_spark_sao_elegiveis():
    assert IdentityInfo("1", "TT_USER", "x").serve_para_spark
    assert IdentityInfo("1", "BC_AUTH_TT", "x").serve_para_spark
    # Desde 15/01/2026 a Custom Identity não serve para feed.
    assert not IdentityInfo("1", "CUSTOMIZED_USER", "x").serve_para_spark


def test_identidade_unica_e_escolhida_sem_referencia():
    assert FakeIdentities([TT("9", "Padaria")]).resolver().identity_id == "9"


def test_com_varias_identidades_exige_escolha_explicita():
    # Anunciar pela conta errada é pior que pedir para a pessoa dizer qual.
    with pytest.raises(LookupError, match="mais de uma"):
        FakeIdentities([TT("1", "Padaria"), TT("2", "Clínica")]).resolver()


def test_resolve_por_id_e_por_nome():
    ids = FakeIdentities([TT("1", "Padaria do Zé"), TT("2", "Clínica Vida")])
    assert ids.resolver("2").display_name == "Clínica Vida"
    assert ids.resolver("padaria").identity_id == "1"


def test_nome_ambiguo_falha_listando_as_opcoes():
    ids = FakeIdentities([TT("1", "Clínica Vida"), TT("2", "Clínica Bem Estar")])
    with pytest.raises(LookupError, match="ambíguo"):
        ids.resolver("clínica")


def test_sem_identidade_elegivel_explica_o_que_fazer():
    with pytest.raises(LookupError, match="Vincule a conta"):
        FakeIdentities([]).resolver()
