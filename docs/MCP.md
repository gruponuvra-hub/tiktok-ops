# Gestão de campanhas pelo MCP oficial da TikTok

A TikTok publicou em **28/08/2026** um servidor MCP oficial para gestão de
anúncios. Ele é o caminho mais curto para a metade "campanhas" deste projeto, e
tem uma vantagem decisiva sobre a API REST:

> **É público. Não exige app de desenvolvedor, nem e-mail corporativo, nem
> aprovação.** Basta uma conta TikTok for Business.

Texto literal da documentação: *"Você não precisa registrar uma conta de
desenvolvedor nem criar um app de desenvolvedor para se conectar."*

Na prática: enquanto o cadastro de desenvolvedor (necessário para a publicação
orgânica) está na fila, a operação de mídia paga já roda.

---

## Conectar

O arquivo `.mcp.json` já está no repositório. Quem clonar o projeto e abrir no
Claude Code só precisa rodar:

```
/mcp
```

e autenticar com a conta da operação. O OAuth acontece no navegador; nenhuma
credencial entra no repositório.

Para adicionar manualmente, fora deste projeto:

```bash
claude mcp add --transport http tiktok-ads \
  https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat
```

### Duas versões do servidor

| Versão | URL | Quando usar |
|---|---|---|
| **Completa** | `.../open_mcp/tt-ads-mcp-flat` | ~400 ferramentas carregadas de uma vez. **É a recomendada pela própria TikTok para o Claude.** |
| Em camadas | `.../open_mcp/tt-ads-mcp-layer` | ~40 ferramentas iniciais, o resto sob demanda. Útil se o contexto estiver apertado. |

⚠️ **O token é escopado por caminho.** Um token obtido para o `-layer` não
autentica no `-flat`. Trocar de versão exige reautenticar.

---

## Operando como agência

A carteira de uma agência vive no Business Center, e o MCP cobre isso: há um
grupo inteiro de ferramentas de **Business Center**, além de **Advertiser**,
**Campaign**, **Ad Group**, **Ad**, **Reporting**, **Identity**, **Spark Ads** e
mais trinta categorias.

Fluxo típico de conversa com o agente:

1. *"Liste meus Business Centers"* → escolhe o BC da agência
2. *"Quais contas de anúncio estão nesse BC?"* → a carteira de clientes
3. *"Como a conta da Clínica Vida performou nos últimos 14 dias?"*
4. *"Pause os ad groups dessa conta com CPA acima de R$ 40"*

O `CLAUDE.md` na raiz do projeto é lido a cada sessão e carrega as regras de
operação — pisos de orçamento, limites, o que nunca fazer. É ele que impede o
agente de inventar política.

---

## O que ele cobre, e o que não

**Cobre:** campanhas, ad groups, ads, criativos, identidades, Spark Ads,
audiências, catálogos, pixels, leads, Business Center, pagamentos, relatórios,
Smart+, GMV Max, regras automatizadas, testes A/B. São 377 ferramentas mapeadas
para endpoints, mais um agente de diagnóstico de performance
(`tiktok_ads_diagnosis_agent`).

**Não cobre: publicação orgânica.** Não há nenhum endpoint `/business/*` nem
`/tt_user/*` na lista — buscar por "publish" nas ferramentas devolve zero
resultados. Publicar vídeo no perfil continua sendo trabalho dos comandos
`tiktok-ops organic`, e esses exigem o cadastro de desenvolvedor.

---

## Limites

| | |
|---|---|
| Token de acesso | **24 horas** |
| Token de refresh | 30 dias |
| Autorização do usuário | **30 dias** — depois disso, reautorizar |
| Rate limit | **3 QPS por ferramenta, por usuário** |
| Smart+ | no máximo uma operação a cada 5 segundos por anúncio |

O limite ser *por ferramenta* (e não um balde compartilhado do app, como na API
REST) é uma diferença relevante: chamadas a ferramentas diferentes não competem
entre si.

A disponibilidade de ferramentas pode variar por região e configuração de conta —
a TikTok não publica a lista de regiões.

---

## Quando ainda vale usar a API REST

O MCP é para trabalho conduzido por um agente, com uma pessoa por perto. A API
REST (módulo `ads/` deste projeto) continua sendo o caminho para:

- rotinas agendadas sem ninguém na frente do terminal (cron, fila, worker)
- lógica determinística que precisa ser versionada e testada
- volume alto, onde o controle de backoff e paginação é seu

Ela exige o app de desenvolvedor aprovado. Ver [../SETUP.md](../SETUP.md).
