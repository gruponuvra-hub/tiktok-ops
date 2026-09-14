# Setup — do zero até a primeira publicação

Este documento é o caminho completo, incluindo as partes que não são código. A parte
burocrática tem fila e é o que determina o prazo: comece por ela.

---

## Passo 0 — Decidir o modelo de operação

Há duas formas de usar este projeto, e elas exigem coisas diferentes. Decida antes
de começar.

### Modelo A — um app, várias operações *(recomendado para agências)*

Você mantém **um** app de desenvolvedor aprovado. Cada agência ou cliente apenas
**autoriza a conta dele** ao seu app, por um link. Quem é atendido não precisa de
registro de desenvolvedor, domínio próprio nem site.

- Você faz o cadastro **uma vez**
- Cada atendido vira uma operação: `tiktok-ops init <nome>`
- É o modelo "Technology Company" da TikTok, e é para isso que ele existe

```bash
tiktok-ops init agencia-zebra
tiktok-ops --tenant agencia-zebra bc list
```

### Modelo B — o cliente hospeda a própria cópia

Você entrega o repositório; o cliente roda com as credenciais dele.

- **Para a metade de campanhas, funciona imediatamente**: o `.mcp.json` já está
  no repositório e o servidor MCP oficial não exige app de desenvolvedor. O
  cliente clona, roda `/mcp`, autentica com a conta TikTok for Business dele e
  já opera.
- **Para a metade orgânica**, o cliente precisa do próprio cadastro completo:
  CNPJ, domínio, e-mail no domínio, site institucional, aprovação da TikTok.

Se a dúvida for "qual dos dois", é quase sempre o **A** para orgânico e o **B**
para campanhas.

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
