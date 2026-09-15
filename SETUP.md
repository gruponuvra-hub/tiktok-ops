# Setup — do zero até a primeira publicação

Este documento é o caminho completo, incluindo as partes que não são código. A parte
burocrática tem fila e é o que determina o prazo: comece por ela.

---

## Passo 0 — O modelo de operação

**Cada instalação é autônoma.** Quem usa este projeto roda a própria cópia, no
próprio VS Code, com as próprias credenciais. Não há servidor central, painel
web nem serviço hospedado — tudo acontece no terminal, conduzido pelo Claude
Code.

Isso tem uma consequência que precisa estar clara antes de começar, porque as
duas metades do projeto têm exigências bem diferentes:

| | **Campanhas (mídia paga)** | **Publicação no perfil (orgânico)** |
|---|---|---|
| O que usa | MCP oficial da TikTok, já no `.mcp.json` | API própria, com app de desenvolvedor |
| Precisa de app de desenvolvedor? | **não** | **sim** |
| Precisa de CNPJ, domínio e site? | **não** | **sim** |
| Quando funciona | **assim que você clonar** | 1–2 semanas após submeter |

Ou seja: clonar o repositório e rodar o `setup.ps1` já te dá a operação de
campanhas completa, hoje. A publicação no perfil exige que **você** faça o
cadastro de desenvolvedor descrito no Passo 1 — ele é por empresa, não é
transferível, e não dá para usar o de outra pessoa.

Se você atende vários clientes, cada um vira uma **operação** dentro da sua
instalação, com arquivo de configuração e tokens próprios:

```bash
tiktok-ops init cliente-a
tiktok-ops init cliente-b
tiktok-ops --tenant cliente-a bc advertisers
```

Um único cadastro de desenvolvedor seu atende todos eles — os clientes só
autorizam as contas deles ao seu app, por um link, sem precisar de cadastro
próprio.

---
## Passo 1 — Pré-requisitos de cadastro (começa a fila aqui)

A TikTok rejeita cadastro de desenvolvedor com e-mail pessoal. Texto literal da
documentação: *"Você será rejeitado se estiver usando um e-mail pessoal ou temporário."*

Checklist:

- [ ] **CNPJ ativo.** MEI serve — a regra barra pessoa física, não empresa pequena
- [ ] **Domínio próprio.** Nada de subdomínio de hospedagem gratuita, Linktree ou loja de marketplace
- [ ] **E-mail no domínio** (`dev@seudominio.com.br`)
- [ ] **Site institucional** no mesmo domínio: público sem login, descrevendo produto e
      empresa. Não pode ser landing page nem tela de login. Precisa ter **política de
      privacidade** e **termos de uso** visíveis sem abrir menu
- [ ] Nome da empresa coerente com o domínio e o e-mail

O mesmo domínio resolve três coisas: o e-mail do cadastro, o site exigido, e a
**verificação de propriedade de URL** que a API exige para aceitar suas mídias. Um
domínio, três travas.

---

## Passo 2 — Cadastro na TikTok

1. Criar conta em [TikTok for Business](https://business-api.tiktok.com/portal) *(imediato)*
2. Preencher o **Formulário de Acesso à Accounts API** — obrigatório desde 20/03/2026,
   **antes** de submeter o app
3. Registrar como desenvolvedor *(3 dias úteis)*
4. Criar o app com os escopos:
   - Ads Management
   - Reporting
   - Creative Management
   - **TikTok Accounts** (id `18000000`) ← sem este, o link de autorização de conta
     nem aparece no portal
   *(2–3 dias úteis)*
5. Autorizar o anunciante pelo link do portal — o dono da conta recebe um código por
   e-mail *(imediato; a verificação vale 48h)*

**Prazo realista até a primeira chamada autenticada: 1 a 2 semanas**, contando
possíveis rejeições.

---

## Passo 3 — Infraestrutura de mídia

### Cloudflare R2

1. Criar o bucket
2. Apontar um domínio customizado para ele (ex.: `media.seudominio.com.br`).
   **Não use URL assinada** — a TikTok invalida qualquer URL que redirecione
3. Gerar as credenciais de API e preencher `R2_*` no `.env`

### Google Drive

1. Criar uma conta de serviço no Google Cloud, com a Drive API habilitada
2. Baixar o JSON para `data/google-service-account.json` *(já está no `.gitignore`)*
3. **Compartilhar a pasta do Drive com o e-mail da conta de serviço**
4. Preencher `GOOGLE_DRIVE_FOLDER_ID` com o ID da pasta (o trecho da URL após `/folders/`)

### Verificar o domínio na TikTok

```bash
tiktok-ops organic verify-domain media.seudominio.com.br
# publique a assinatura devolvida como registro DNS TXT
tiktok-ops organic verify-domain media.seudominio.com.br --checar <property_id>
```

Cuidado: verificação de domínio casa subdomínios **para baixo**. Verificar
`media.seudominio.com.br` cobre `cdn.media.seudominio.com.br`, mas **não** cobre
`seudominio.com.br`.

---

## Passo 4 — Primeira publicação

```bash
tiktok-ops auth status                    # confere o que já está no lugar
tiktok-ops organic settings               # pré-voo da conta
tiktok-ops media prepare "video.mp4"      # Drive → R2, devolve a URL
tiktok-ops organic publish "<url>" --caption "..." --no-dry-run
tiktok-ops organic status <share_id> --aguardar
```

---

## Enquanto o cadastro não sai

Duas coisas funcionam desde já:

**1. Exercitar o fluxo de publicação** com a URL de teste oficial da TikTok, que é
aceita sem verificação de propriedade:

```bash
tiktok-ops organic test-publish
```

**2. Gerenciar campanhas pelo MCP oficial da TikTok**, que é público e **não exige app
de desenvolvedor nem e-mail corporativo** — basta uma conta TikTok for Business:

```
https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat
```

São ~377 ferramentas de gestão de anúncios, plugáveis direto no Claude Code. O token
vale 24h e a autorização vale 30 dias. Ele **não** cobre publicação orgânica — para
isso, o caminho é o cadastro acima.
