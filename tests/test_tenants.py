"""Registro de operações — a base da replicabilidade."""

import pytest

from tiktok_ops.tenants import NomeInvalido, TenantRegistry


def test_cria_operacao_com_arquivo_proprio(tmp_path):
    reg = TenantRegistry(tmp_path)
    t = reg.create("agencia-zebra", app_id="123", bc_id="999")
    assert t.existe
    conteudo = t.env_file.read_text(encoding="utf-8")
    assert "TIKTOK_APP_ID=123" in conteudo
    assert "TIKTOK_BC_ID=999" in conteudo


def test_nao_sobrescreve_operacao_existente(tmp_path):
    reg = TenantRegistry(tmp_path)
    reg.create("cliente-a")
    with pytest.raises(FileExistsError):
        reg.create("cliente-a")


def test_nomes_invalidos_sao_recusados(tmp_path):
    reg = TenantRegistry(tmp_path)
    for ruim in ("Agencia", "com espaco", "a", "../escapa", "acentuação"):
        with pytest.raises(NomeInvalido):
            reg.get(ruim)


def test_lista_operacoes_em_ordem(tmp_path):
    reg = TenantRegistry(tmp_path)
    reg.create("zeta")
    reg.create("alfa")
    assert [t.nome for t in reg.list()] == ["alfa", "zeta"]


def test_operacao_inexistente_da_erro_com_sugestao(tmp_path):
    reg = TenantRegistry(tmp_path)
    reg.create("existe")
    with pytest.raises(FileNotFoundError, match="existe"):
        reg.resolve_env_file("nao-existe")


def test_sem_tenant_usa_o_env_da_raiz(tmp_path):
    assert TenantRegistry(tmp_path).resolve_env_file(None) is None
