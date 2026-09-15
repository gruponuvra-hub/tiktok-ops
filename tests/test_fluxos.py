"""Fluxos ponta a ponta, com dublês — sem rede, sem credencial."""

import pytest

from tiktok_ops import fluxos
from tiktok_ops.ads.identities import IdentityInfo
from tiktok_ops.errors import MediaError, TikTokError
from tiktok_ops.organic.publish import AccountSettings, PostOptions


class Arquivo:
    def __init__(self, name):
        self.name = name


class FakeDrive:
    def __init__(self, nomes):
        self._nomes = nomes

    def list_media(self, apenas_video=False):
        return [Arquivo(n) for n in self._nomes]


class FakeInfo:
    duration_sec = 30.0


class FakePipeline:
    def preparar(self, arquivo, *, validar=True):
        return f"https://media.exemplo.com/{arquivo.name}", FakeInfo()


class FakePublisher:
    def __init__(self, status="PUBLISH_COMPLETE", item_id="post-1"):
        self._status = status
        self._item_id = item_id
        self.publicou = False

    def get_settings(self):
        return AccountSettings(privacy_level_options=["PUBLIC_TO_EVERYONE"],
                               max_video_post_duration_sec=600)

    def publish_video(self, video_url, options, **kw):
        if kw.get("dry_run", True):
            return {"dry_run": True, "payload": {"video_url": video_url}}
        self.publicou = True
        return {"share_id": "share-1"}

    def wait_for_publish(self, share_id, **kw):
        corpo = {"status": self._status}
        if self._item_id:
            corpo["item_id"] = self._item_id
        return corpo


class FakeBridge:
    def autorizar_para_anuncio(self, item_id, *, dias=30, dry_run=True):
        return {"item_id": item_id, "dias": dias}


class FakeCampaigns:
    def __init__(self):
        self.chamadas = []

    def create(self, spec, *, dry_run=True):
        self.chamadas.append("campanha")
        return {"campaign_id": "camp-1"}

    def create_adgroup(self, spec, *, dry_run=True):
        self.chamadas.append("adgroup")
        self.orcamento = spec.budget
        return {"adgroup_id": "grupo-1"}

    def create_spark_ad(self, adgroup_id, nome, identity_id, item_id, **kw):
        self.chamadas.append("anuncio")
        self.show_on_profile = kw.get("show_on_profile")
        return {"ad_ids": ["ad-1"]}


class FakeIdentities:
    def resolver(self, referencia=None):
        return IdentityInfo("ident-1", "TT_USER", "Padaria")


def _publicar(publisher=None, dry_run=False, arquivo="video.mp4"):
    return fluxos.publicar(
        drive=FakeDrive(["video.mp4"]), pipeline=FakePipeline(),
        publisher=publisher or FakePublisher(), nome_arquivo=arquivo,
        opcoes=PostOptions(caption="oi"), dry_run=dry_run,
    )


# -- extração do id do post ------------------------------------------------

def test_id_do_post_e_procurado_em_varios_campos():
    assert fluxos.extrair_item_id({"item_id": "a"}) == "a"
    assert fluxos.extrair_item_id({"post_id": "b"}) == "b"
    assert fluxos.extrair_item_id({"nada": "x"}) is None


# -- publicar ---------------------------------------------------------------

def test_arquivo_ausente_no_drive_falha_cedo():
    with pytest.raises(MediaError, match="não está na pasta"):
        _publicar(arquivo="inexistente.mp4")


def test_dry_run_nao_publica():
    publisher = FakePublisher()
    r = _publicar(publisher=publisher, dry_run=True)
    assert r.dry_run and not publisher.publicou
    assert r.share_id == ""


def test_publicacao_completa_traz_share_id_e_item_id():
    r = _publicar()
    assert r.publicado
    assert r.share_id == "share-1"
    assert r.item_id == "post-1"
    assert any("status final" in p for p in r.passos)


# -- impulsionar ------------------------------------------------------------

def test_impulsionar_segue_a_ordem_obrigatoria():
    campanhas = FakeCampaigns()
    r = fluxos.impulsionar(
        bridge=FakeBridge(), campaigns=campanhas, identities=FakeIdentities(),
        item_id="post-1", nome_campanha="Outubro", orcamento_diario=50, dry_run=False,
    )
    # Autorizar vem antes de criar o anúncio, senão o item_id é recusado.
    assert campanhas.chamadas == ["campanha", "adgroup", "anuncio"]
    assert r.ad_id == "ad-1"
    assert r.identity_id == "ident-1"


def test_impulsionar_mantem_o_post_visivel_no_perfil():
    # dark_post_status passou a esconder posts por padrão em 27/01/2026.
    campanhas = FakeCampaigns()
    fluxos.impulsionar(
        bridge=FakeBridge(), campaigns=campanhas, identities=FakeIdentities(),
        item_id="post-1", nome_campanha="X", orcamento_diario=20, dry_run=False,
    )
    assert campanhas.show_on_profile is True


def test_campanha_existente_nao_e_recriada():
    campanhas = FakeCampaigns()
    r = fluxos.impulsionar(
        bridge=FakeBridge(), campaigns=campanhas, identities=FakeIdentities(),
        item_id="post-1", nome_campanha="X", orcamento_diario=20,
        campaign_id="camp-existente", dry_run=False,
    )
    assert "campanha" not in campanhas.chamadas
    assert r.campaign_id == "camp-existente"


# -- fluxo completo ---------------------------------------------------------

def _completo(publisher, dry_run=False):
    campanhas = FakeCampaigns()
    return fluxos.publicar_e_impulsionar(
        drive=FakeDrive(["video.mp4"]), pipeline=FakePipeline(), publisher=publisher,
        bridge=FakeBridge(), campaigns=campanhas, identities=FakeIdentities(),
        nome_arquivo="video.mp4", opcoes=PostOptions(), nome_campanha="Outubro",
        orcamento_diario=50, dry_run=dry_run,
    )


def test_completo_encadeia_publicacao_e_campanha():
    r = _completo(FakePublisher())
    assert r["publicacao"].publicado
    assert r["impulsionamento"].ad_id == "ad-1"


def test_publicacao_falhada_nao_gasta_dinheiro():
    with pytest.raises(TikTokError, match="nada foi impulsionado"):
        _completo(FakePublisher(status="FAILED"))


def test_sem_id_do_post_explica_como_seguir_manualmente():
    with pytest.raises(TikTokError, match="bridge candidatos"):
        _completo(FakePublisher(item_id=""))
