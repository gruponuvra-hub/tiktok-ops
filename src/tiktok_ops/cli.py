"""CLI do tiktok-ops.

Duas ideias organizam esta interface:

- **Operação (tenant).** A mesma instalação atende várias agências e clientes.
  `--tenant nome` escolhe qual, e cada uma tem seu próprio `.env` e seus próprios
  tokens. Sem `--tenant`, usa o `.env` da raiz.
- **Dry-run por padrão.** Todo comando que escreve mostra o payload e não envia
  nada. Para valer, `--no-dry-run`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .ads import BusinessCenter, CampaignSpec, Campaigns, Reports
from .auth import AccountsAuth, MarketingAuth
from .config import TIKTOK_ADS_MCP_URL, TIKTOK_TEST_VIDEO_URL, get_settings
from .errors import ConfigError, MediaError, TikTokError
from .http import TikTokClient
from .organic import OrganicPublisher, PostOptions, UrlProperties
from .tenants import NomeInvalido, TenantRegistry

app = typer.Typer(
    help="Publicação orgânica e gestão de campanhas no TikTok", no_args_is_help=True
)
auth_app = typer.Typer(help="Autorização das contas")
bc_app = typer.Typer(help="Business Center — carteira de contas da agência")
organic_app = typer.Typer(help="Publicação no perfil")
ads_app = typer.Typer(help="Campanhas e relatórios")
media_app = typer.Typer(help="Pipeline de mídia (Drive → R2)")
for sub, nome in (
    (auth_app, "auth"), (bc_app, "bc"), (organic_app, "organic"),
    (ads_app, "ads"), (media_app, "media"),
):
    app.add_typer(sub, name=nome)

console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Operação escolhida para esta invocação.
_TENANT: dict[str, Optional[str]] = {"nome": None}


@app.callback()
def main(
    tenant: Optional[str] = typer.Option(
        None, "--tenant", "-t",
        help="operação a usar (arquivo tenants/<nome>.env). Sem isto, usa o .env da raiz.",
    ),
):
    _TENANT["nome"] = tenant


def _cfg():
    return get_settings(_TENANT["nome"])


def _mostrar(dados: object) -> None:
    console.print_json(json.dumps(dados, ensure_ascii=False, default=str))


# ----------------------------------------------------------------- operações

@app.command("init")
def init(
    nome: str = typer.Argument(..., help="nome da operação, ex.: agencia-zebra"),
    app_id: str = typer.Option("", "--app-id"),
    app_secret: str = typer.Option("", "--app-secret"),
    bc_id: str = typer.Option("", "--bc-id", help="Business Center, se já souber"),
):
    """Cria uma operação nova (um arquivo de configuração próprio)."""
    tenant = TenantRegistry().create(nome, app_id=app_id, app_secret=app_secret, bc_id=bc_id)
    console.print(f"[green]operação '{nome}' criada[/] em {tenant.env_file}")
    console.print("Edite o arquivo e depois rode:")
    console.print(f"  tiktok-ops --tenant {nome} bc list")


@app.command("tenants")
def listar_tenants():
    """Lista as operações configuradas."""
    tenants = TenantRegistry().list()
    if not tenants:
        console.print("nenhuma operação configurada. Crie com: tiktok-ops init <nome>")
        return
    tabela = Table("operação", "arquivo")
    for t in tenants:
        tabela.add_row(t.nome, str(t.env_file))
    console.print(tabela)


@app.command("mcp")
def mcp_info():
    """Mostra como plugar o servidor MCP oficial de anúncios da TikTok."""
    console.print(
        "\n[bold]Servidor MCP oficial de anúncios[/]\n"
        f"  {TIKTOK_ADS_MCP_URL}\n\n"
        "É público: não exige app de desenvolvedor nem e-mail corporativo — basta uma\n"
        "conta TikTok for Business. São ~377 ferramentas de gestão de anúncios.\n\n"
        "[bold]No Claude Code, dentro desta pasta:[/]\n"
        "  o arquivo .mcp.json já está no repositório, então basta abrir o projeto\n"
        "  e rodar [cyan]/mcp[/] para autenticar com a conta da operação.\n\n"
        "[bold]Para adicionar manualmente:[/]\n"
        "  claude mcp add --transport http tiktok-ads \\\n"
        f"    {TIKTOK_ADS_MCP_URL}\n\n"
        "[yellow]Limites:[/] token de acesso 24h, autorização 30 dias, 3 QPS por\n"
        "ferramenta. Não cobre publicação orgânica — para isso use os comandos\n"
        "[cyan]organic[/] deste app.\n"
    )


# --------------------------------------------------------------------- auth

@auth_app.command("accounts")
def auth_accounts(auth_code: str = typer.Argument(..., help="auth_code do callback (vale 10 min)")):
    """Troca o auth_code da conta TikTok pelos tokens do orgânico."""
    dados = AccountsAuth(_cfg()).exchange_code(auth_code)
    console.print("[green]conta autorizada[/]")
    _mostrar({k: v for k, v in dados.items() if "token" not in k})


@auth_app.command("marketing")
def auth_marketing(auth_code: str = typer.Argument(..., help="auth_code do anunciante (vale 1h)")):
    """Troca o auth_code do anunciante pelo token de longa duração."""
    dados = MarketingAuth(_cfg()).exchange_code(auth_code)
    console.print("[green]anunciante autorizado[/]")
    _mostrar({"advertiser_ids": dados.get("advertiser_ids", [])})


@auth_app.command("status")
def auth_status():
    """Mostra o que já está autorizado e o que falta nesta operação."""
    s = _cfg()
    tabela = Table("item", "situação")
    tabela.add_row("operação", s.tenant or "(padrão, .env da raiz)")
    tabela.add_row("app_id", "ok" if s.tiktok_app_id else "faltando")
    tabela.add_row("business center", s.tiktok_bc_id or "não configurado")
    tabela.add_row(
        "conta TikTok (orgânico)",
        "ok" if AccountsAuth(s).store.read().get("access_token") else "não autorizada",
    )
    tabela.add_row(
        "anunciante (pago)",
        "ok" if MarketingAuth(s).store.read().get("access_token") else "não autorizado",
    )
    tabela.add_row("domínio de mídia", s.media_base_url or "não configurado")
    console.print(tabela)


# ---------------------------------------------------------- business center

def _bc_client() -> TikTokClient:
    s = _cfg()
    return TikTokClient(MarketingAuth(s).access_token())


@bc_app.command("list")
def bc_list():
    """Lista os Business Centers que este token alcança."""
    tabela = Table("bc_id", "nome", "empresa", "tipo", "agência?")
    for bc in BusinessCenter(_bc_client()).list_bcs():
        tabela.add_row(bc.bc_id, bc.name, bc.company, bc.bc_type, "sim" if bc.e_agencia else "não")
    console.print(tabela)


@bc_app.command("advertisers")
def bc_advertisers(
    bc_id: Optional[str] = typer.Option(None, "--bc-id", help="padrão: o do .env da operação"),
):
    """Lista as contas de anúncio penduradas no Business Center."""
    s = _cfg()
    alvo = bc_id or s.tiktok_bc_id
    if not alvo:
        raise ConfigError("informe --bc-id ou preencha TIKTOK_BC_ID na operação")
    contas = BusinessCenter(_bc_client()).list_all_advertisers(alvo)
    tabela = Table("advertiser_id", "nome", "moeda", "fuso", "status")
    for c in contas:
        tabela.add_row(c.advertiser_id, c.name, c.currency, c.timezone, c.status)
    console.print(tabela)
    console.print(f"[dim]{len(contas)} conta(s)[/]")


# --------------------------------------------------------------------- ads

def _campaigns(advertiser: Optional[str] = None) -> Campaigns:
    """Resolve a conta de anúncio: flag > BC por nome/id > .env da operação."""
    s = _cfg()
    client = TikTokClient(MarketingAuth(s).access_token())
    if advertiser and s.tiktok_bc_id:
        conta = BusinessCenter(client).resolver_advertiser(s.tiktok_bc_id, advertiser)
        return Campaigns(client, conta.advertiser_id)
    alvo = advertiser or s.tiktok_advertiser_id
    if not alvo:
        raise ConfigError(
            "nenhuma conta de anúncio escolhida. Use --advertiser, ou preencha "
            "TIKTOK_ADVERTISER_ID, ou configure TIKTOK_BC_ID e rode `bc advertisers`."
        )
    return Campaigns(client, alvo)


@ads_app.command("list")
def ads_list(
    advertiser: Optional[str] = typer.Option(
        None, "--advertiser", "-a", help="id da conta ou trecho do nome (via BC)"
    ),
):
    """Lista as campanhas de uma conta de anúncio."""
    _mostrar(_campaigns(advertiser).list())


@ads_app.command("create")
def ads_create(
    nome: str = typer.Argument(...),
    advertiser: Optional[str] = typer.Option(None, "--advertiser", "-a"),
    objetivo: str = typer.Option("TRAFFIC", "--objetivo"),
    orcamento: Optional[float] = typer.Option(
        None, "--orcamento",
        help="deixe vazio para BUDGET_MODE_INFINITE e controle o gasto no ad group",
    ),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
):
    """Cria uma campanha."""
    spec = CampaignSpec(
        campaign_name=nome,
        objective_type=objetivo,
        budget_mode="BUDGET_MODE_DAY" if orcamento else "BUDGET_MODE_INFINITE",
        budget=orcamento,
    )
    _mostrar(_campaigns(advertiser).create(spec, dry_run=dry_run))


@ads_app.command("report")
def ads_report(
    advertiser: Optional[str] = typer.Option(None, "--advertiser", "-a"),
    dias: int = typer.Option(30, "--dias", min=1, max=30),
):
    """Relatório básico dos últimos N dias (máximo 30 por requisição)."""
    from datetime import date, timedelta

    campanhas = _campaigns(advertiser)
    rel = Reports(campanhas.client, campanhas.advertiser_id)
    fim = date.today() - timedelta(days=1)
    _mostrar(rel.integrated(start_date=fim - timedelta(days=dias - 1), end_date=fim))


# ----------------------------------------------------------------- organic

def _publisher() -> OrganicPublisher:
    s = _cfg()
    auth = AccountsAuth(s)
    return OrganicPublisher(TikTokClient(auth.access_token()), auth.business_id())


@organic_app.command("settings")
def organic_settings():
    """Pré-voo: o que esta conta permite (duração máxima, comentários, dueto, stitch)."""
    cfg = _publisher().get_settings()
    _mostrar({f: getattr(cfg, f) for f in cfg.__slots__})


@organic_app.command("publish")
def organic_publish(
    video_url: str = typer.Argument(..., help="URL pública em domínio verificado"),
    caption: str = typer.Option("", "--caption", "-c"),
    branded: bool = typer.Option(False, "--branded", help="rotula como parceria paga"),
    promocional: bool = typer.Option(False, "--promocional", help="rotula como conteúdo promocional"),
    rascunho: bool = typer.Option(False, "--rascunho", help="manda para rascunho em vez de publicar"),
    mudo: bool = typer.Option(False, "--mudo", help="publica sem áudio (volumes em 0)"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
):
    """Publica um vídeo no perfil."""
    opcoes = PostOptions(
        caption=caption,
        is_branded_content=branded,
        is_brand_organic=promocional,
        upload_to_draft=rascunho,
        music_sound_volume=0 if mudo else 50,
        video_original_sound_volume=0 if mudo else 50,
    )
    _mostrar(_publisher().publish_video(video_url, opcoes, dry_run=dry_run))


@organic_app.command("test-publish")
def organic_test_publish(dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run")):
    """Exercita o fluxo com a URL de teste oficial da TikTok.

    Útil antes de ter domínio verificado: essa URL é aceita sem verificação de
    propriedade.
    """
    _mostrar(
        _publisher().publish_video(
            TIKTOK_TEST_VIDEO_URL, PostOptions(caption="teste tiktok-ops"), dry_run=dry_run
        )
    )


@organic_app.command("status")
def organic_status(
    share_id: str,
    aguardar: bool = typer.Option(False, "--aguardar", help="espera até um estado terminal"),
):
    """Consulta o status de uma publicação."""
    pub = _publisher()
    _mostrar(pub.wait_for_publish(share_id) if aguardar else pub.get_status(share_id))


@organic_app.command("verify-domain")
def organic_verify_domain(
    dominio: str = typer.Argument(..., help="ex.: media.seudominio.com.br"),
    checar: Optional[str] = typer.Option(None, "--checar", help="property_id para validar"),
):
    """Registra ou valida um domínio como propriedade de URL na TikTok."""
    s = _cfg()
    s.require("tiktok_app_id")
    props = UrlProperties(TikTokClient(AccountsAuth(s).access_token()), s.tiktok_app_id)
    if checar:
        _mostrar(props.check(checar))
    else:
        console.print("[yellow]publique a assinatura abaixo como registro DNS TXT e rode --checar[/]")
        _mostrar(props.add(dominio))


# ------------------------------------------------------------------- media

@media_app.command("list")
def media_list(apenas_video: bool = typer.Option(False, "--apenas-video")):
    """Lista as mídias da pasta do Drive (só metadados)."""
    from .media import DriveSource

    s = _cfg()
    s.require("google_drive_folder_id")
    tabela = Table("nome", "tipo", "tamanho", "modificado")
    drive = DriveSource(s.google_service_account_file, s.google_drive_folder_id)
    for f in drive.list_media(apenas_video=apenas_video):
        tabela.add_row(f.name, f.mime_type, f"{f.size_bytes / 1e6:.1f} MB", f.modified_time)
    console.print(tabela)


@media_app.command("prepare")
def media_prepare(nome: str = typer.Argument(..., help="nome do arquivo no Drive")):
    """Baixa do Drive, valida e sobe para o R2. Devolve a URL para publicar."""
    from .media import DriveSource, MediaPipeline, R2Storage

    s = _cfg()
    s.require("google_drive_folder_id", "r2_account_id", "r2_bucket", "r2_public_base_url")
    drive = DriveSource(s.google_service_account_file, s.google_drive_folder_id)
    storage = R2Storage(
        s.r2_account_id, s.r2_access_key_id, s.r2_secret_access_key,
        s.r2_bucket, s.r2_public_base_url,
    )
    pipeline = MediaPipeline(drive, storage, Path(s.data_dir) / "media")

    alvo = next((f for f in drive.list_media() if f.name == nome), None)
    if alvo is None:
        console.print(f"[red]arquivo '{nome}' não encontrado na pasta do Drive[/]")
        raise typer.Exit(code=1)

    url, info = pipeline.preparar(alvo)
    _mostrar({"url": url, "info": info.__dict__ if info else None})


def run() -> None:
    """Entrada do programa: traduz exceções conhecidas em mensagem e código 1."""
    try:
        app()
    except (
        TikTokError, ConfigError, MediaError, NomeInvalido,
        FileNotFoundError, FileExistsError, LookupError,
    ) as exc:
        console.print(f"[bold red]erro:[/] {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":  # pragma: no cover
    run()
