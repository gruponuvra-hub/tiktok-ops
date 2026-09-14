"""Testes das regras de publicação orgânica — rodam sem credencial nenhuma."""

import pytest

from tiktok_ops.errors import MediaError
from tiktok_ops.organic.publish import AccountSettings, PostOptions


def conta(**kw) -> AccountSettings:
    base = dict(
        privacy_level_options=["PUBLIC_TO_EVERYONE"],
        comment_disabled=False,
        duet_disabled=False,
        stitch_disabled=False,
        max_video_post_duration_sec=600,
    )
    base.update(kw)
    return AccountSettings(**base)


def test_volume_de_audio_nao_fica_no_default_da_api():
    # A API usa 0 (post mudo); o app TikTok usa 50. O default aqui acompanha o app.
    info = PostOptions().to_post_info()
    assert info["music_sound_info"]["music_sound_volume"] == 50
    assert info["music_sound_info"]["video_original_sound_volume"] == 50


def test_rascunho_ignora_os_demais_campos():
    info = PostOptions(caption="oi", upload_to_draft=True).to_post_info()
    assert info == {"upload_to_draft": True}


def test_legenda_longa_demais_e_rejeitada_antes_da_chamada():
    with pytest.raises(MediaError, match="legenda"):
        PostOptions(caption="x" * 2201).validate(conta())


def test_excesso_de_mencoes_e_rejeitado():
    with pytest.raises(MediaError, match="menções"):
        PostOptions(caption="@a " * 31).validate(conta())


def test_nao_da_para_habilitar_o_que_a_conta_desativou():
    with pytest.raises(MediaError, match="comentários"):
        PostOptions(disable_comment=False).validate(conta(comment_disabled=True))
    with pytest.raises(MediaError, match="duetos"):
        PostOptions(disable_duet=False).validate(conta(duet_disabled=True))


def test_opcoes_validas_passam():
    PostOptions(caption="tudo certo").validate(conta())
