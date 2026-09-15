# tiktok-ops

Publicação orgânica no perfil e gestão de campanhas no TikTok, pelas APIs
oficiais. Operado por linha de comando e por agente, feito para ser **replicado**:
a mesma instalação atende várias agências e vários clientes.

---

## Instalação

**Windows (terminal do VS Code):**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Precisa de **Python 3.11 ou superior**. Se não tiver:
`winget install -e --id Python.Python.3.12`, feche e reabra o terminal.

**macOS / Linux:**

```bash
bash scripts/setup.sh
```

O script encontra o Python, cria o ambiente virtual, instala tudo e roda os
testes. O `-ExecutionPolicy Bypass` vale só para aquela execução: o Windows
bloqueia `.ps1` por padrão e isso não muda nada no sistema.

> Uma observação que economiza tempo: o PowerShell 5.1, que é o padrão do
> Windows, **não entende `&&`** entre comandos. Comandos encadeados com `&&`
> falham com *"token '&&' is not a valid statement separator"*. Por isso os
> scripts existem — cada comando em sua própria linha.

---

## Duas metades, dois caminhos

O projeto faz duas coisas que têm pré-requisitos bem diferentes. Vale entender a
divisão antes de começar.

| | **Campanhas (mídia paga)** | **Publicação no perfil (orgânico)** |
|---|---|---|
| Como se opera | MCP oficial da TikTok, conversando com o agente | comandos `tiktok-ops organic` |
| Precisa de app de desenvolvedor? | **não** | sim |
| Precisa de e-mail corporativo e site? | **não** | sim |
| Disponível | **hoje** | depois do cadastro (1–2 semanas) |

**Comece pela metade de campanhas.** Ela não tem fila: basta uma conta TikTok
for Business. Ver [docs/MCP.md](docs/MCP.md).

```
/mcp        # dentro deste projeto, no Claude Code — o .mcp.json já está aqui
```

A metade orgânica depende de um cadastro empresarial na TikTok. O passo a passo
completo está em [SETUP.md](SETUP.md).

---

## Operações (tenants)

Cada agência ou cliente é uma **operação**: um arquivo de configuração próprio e
tokens próprios. Nada de conta mora no código.

```bash
tiktok-ops init agencia-zebra --app-id ... --bc-id ...
tiktok-ops tenants

tiktok-ops --tenant agencia-zebra bc list
tiktok-ops --tenant agencia-zebra bc advertisers
tiktok-ops --tenant agencia-zebra ads report --advertiser "Clínica Vida"
```

Os arquivos ficam em `tenants/<nome>.env` e estão no `.gitignore` — credencial de
cliente nunca entra no repositório.

### Quem opera como agência

Agência não trabalha com uma conta de anúncio solta: trabalha com um **Business
Center** que pendura as contas dos clientes. Por isso nenhum comando assume um
`advertiser_id` fixo — as contas são descobertas a partir do BC, e podem ser
escolhidas por um trecho do nome:

```bash
tiktok-ops --tenant agencia-zebra ads list --advertiser "padaria"
```

Se o trecho for ambíguo, o comando falha e lista as opções em vez de escolher
por conta própria. Errar a conta de um cliente é pior que pedir para a pessoa ser
específica.

---

## Por que a Accounts API, e não a Content Posting API

Existem duas APIs oficiais da TikTok para publicar no perfil. A diferença muda o
projeto inteiro.

| | Content Posting API | **Accounts API** (esta) |
|---|---|---|
| Host | `developers.tiktok.com` | `business-api.tiktok.com` |
| Visibilidade antes da auditoria | **forçada a "Somente eu"** | **público direto** |
| Auditoria de conteúdo | sim — semanas, subjetiva | não existe |
| Aviso quando o post sai privado | **nenhum** | — |

A armadilha da primeira rota: um app não auditado publica *com sucesso*. Tudo
funciona nos seus testes, porque seus próprios posts privados aparecem para você.
Só em produção se descobre que nenhum post de nenhum cliente ficou visível.

O endpoint que usamos — `/business/video/publish/` — nem tem parâmetro
`privacy_level`. Vídeo publicado é vídeo público.

---

## Uso

Todo comando que escreve começa em **dry-run**: mostra o payload que seria
enviado e não envia nada. Para valer, `--no-dry-run`.

```bash
# antes de ter credenciais — a URL de teste oficial da TikTok é aceita sem
# verificação de domínio
tiktok-ops organic test-publish

# pré-voo: o que esta conta permite (duração máxima, comentários, dueto, stitch)
tiktok-ops organic settings

# Drive → validação local → Cloudflare R2 → devolve a URL pública
tiktok-ops media list --apenas-video
tiktok-ops media prepare "campanha-outubro.mp4"

# publicar e acompanhar
tiktok-ops organic publish "<url>" --caption "texto do post" --no-dry-run
tiktok-ops organic status <share_id> --aguardar

# verificar o domínio das mídias (sem isso a TikTok recusa qualquer URL sua)
tiktok-ops organic verify-domain media.seudominio.com.br
tiktok-ops organic verify-domain media.seudominio.com.br --checar <property_id>
```

### Fluxos de ponta a ponta

O caminho completo em um comando — Drive, validação, R2, publicação,
acompanhamento, autorização do post e campanha:

```bash
tiktok-ops fluxo publicar "campanha-outubro.mp4" \
    --caption "texto do post" \
    --impulsionar --campanha "Outubro — Tráfego" --orcamento 50

# só impulsionar um post que já está no perfil
tiktok-ops fluxo impulsionar <item_id> --campanha "Outubro" --orcamento 50

# o que vale a pena impulsionar
tiktok-ops bridge candidatos --min-views 1000 --min-engajamento 0.05
```

Como todo comando de escrita, esses começam em dry-run: mostram o encadeamento
inteiro e não executam nada até você passar `--no-dry-run`.


`tiktok-ops auth status` mostra, a qualquer momento, o que já está no lugar e o
que falta.

---

## Estrutura

```
.mcp.json            servidor MCP oficial de anúncios — quem clonar já recebe
CLAUDE.md            regras de operação lidas pelo agente a cada sessão
src/tiktok_ops/
├── tenants.py       registro de operações — a base da replicabilidade
├── config.py        configuração por operação, nenhuma conta hardcoded
├── errors.py        exceções mapeadas aos códigos de retorno da TikTok
├── http.py          cliente base: trata "HTTP 200 com falha", backoff, barra final
├── auth/            OAuth das duas APIs (ciclos de vida diferentes)
├── ads/
│   ├── business_center.py   carteira da agência: BCs e contas de anúncio
│   ├── campaigns.py         campanhas, ad groups, Spark Ads
│   └── reports.py           relatórios com as janelas já tratadas
├── organic/         pré-voo → publicação → status; verificação de domínio
├── media/           Drive → disco → R2, com validação por ffprobe
├── bridge/          critérios para promover post orgânico a anúncio
├── fluxos.py        encadeamentos de ponta a ponta
└── cli.py           interface de linha de comando
```

---

## Armadilhas já tratadas no código

Cada uma quebra em produção de forma silenciosa. Todas têm teste.

| Armadilha | Onde |
|---|---|
| `HTTP 200` com falha no corpo — o que vale é o campo `code` | `http.py` |
| Barra final obrigatória na URL (sem ela, `404` em texto puro) | `http.py` |
| Volume de áudio com default `0` na API — post sairia mudo | `organic/publish.py` |
| `dark_post_status` com default `ON` desde 01/2026 — post sumiria do perfil | `ads/campaigns.py` |
| Piso de orçamento de campanha contraditório na documentação | `ads/campaigns.py` |
| Janela de 30 dias e teto de 20.000 ads no relatório (truncagem silenciosa) | `ads/reports.py` |
| Domínio verificado casa subdomínio para baixo, nunca para cima | `organic/properties.py` |
| Refresh token pode voltar diferente do enviado e precisa ser regravado | `auth/store.py` |
| Nome de conta ambíguo entre clientes da mesma carteira | `ads/business_center.py` |
| Bytes de mídia nunca passam pelo contexto do agente nem por MCP | `media/drive.py` |

```bash
pytest      # 49 testes, nenhum precisa de credencial
```

---

## Limites operacionais

| Limite | Valor |
|---|---|
| Publicação orgânica | 6 posts/min, **15/dia por conta** |
| Accounts API | 40 QPM por conta autorizada, por endpoint |
| Marketing API (Basic) | 10 QPS / 600 QPM — **por app, não por anunciante** |
| MCP oficial | 3 QPS **por ferramenta**; autorização vale 30 dias |
| Vídeo orgânico | ≤ 1 GB, 3–600 s, ≥ 360×360, 23–60 FPS |
| Legenda | 2.200 caracteres, máx. 30 menções |

Rodar dois processos com as mesmas credenciais estoura o balde do app
silenciosamente. Um processo por app.

---

## Limites de escopo, por decisão

- **Sem automação de navegador.** Bibliotecas que publicam dirigindo um Chrome
  logado violam os Termos de Desenvolvedor da TikTok e o resultado documentado é
  banimento. Fora de escopo permanentemente.
- **Sem agendamento nativo.** Nenhuma das APIs oferece — o agendamento mora do
  seu lado (cron, fila, workflow).
- **Usos proibidos pela TikTok** estão no `CLAUDE.md` e não serão implementados.
  A TikTok revoga o acesso à Accounts API sem aviso prévio.

---

## Licença

MIT. Ver [LICENSE](LICENSE).
