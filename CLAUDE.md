# tiktok-ops — memória de política do projeto

Este arquivo é lido pelo Claude Code a cada sessão. Ele é a fonte de verdade sobre
**como** operar, não sobre como o código funciona. Regras aqui valem mais que
inferência do agente.

---

## O que este projeto é

App próprio, operado via VS Code, que:

1. publica vídeos e fotos no perfil TikTok (mídias vindas de uma pasta do Google Drive);
2. cria e gerencia campanhas pagas;
3. transforma post orgânico que performou em Spark Ad;
4. gerencia contas e puxa relatórios.

Projeto independente dos demais em `~/projetos`. Repositório GitHub próprio e privado.
Intenção declarada: capitalizar e replicar em outras operações — **modele `tenant`
desde o início, nunca assuma uma conta só**.

---

## Decisão de arquitetura travada

**Publicação orgânica vai pela Accounts API (`business-api.tiktok.com`), não pela
Content Posting API (`developers.tiktok.com`).**

Motivo: `POST /open_api/v1.3/business/video/publish/` publica público direto, sem
parâmetro `privacy_level` e sem restrição de "cliente não auditado". A rota
`developers.tiktok.com` força todo post a `SELF_ONLY` até passar por auditoria de
conteúdo — e **não sinaliza isso pela API**, então tudo parece funcionar em teste e
falha em produção.

Não reintroduzir a rota `developers.tiktok.com` sem decisão explícita.

---

## Regras de compliance que o código deve obedecer

Não são sugestões. Cada uma existe porque quebra em produção de forma silenciosa.

1. **Pré-voo obrigatório.** Sempre chamar `GET /business/video/settings/` antes de
   publicar. Validar `max_video_post_duration_sec` localmente — vídeo mais longo
   falha a publicação. Respeitar `comment_disabled` / `duet_disabled` /
   `stitch_disabled`: só se pode *desligar* o que a conta já permite.

2. **Volume de áudio nunca fica no default.** `music_sound_volume` e
   `video_original_sound_volume` têm default `0` na API (no app o default é 50).
   Setar explicitamente ou o post sai mudo.

3. **`dark_post_status` é sempre explícito.** Desde 27/01/2026 o default virou `ON`,
   o que esconde o post do perfil. Passar `OFF` sempre que o post deva aparecer.

4. **`is_ai_generated` é irreversível.** Uma vez publicado, não muda. Nunca setar
   `true` por inferência — só quando o pipeline souber com certeza.

5. **Rótulos comerciais são obrigatórios e mutuamente excludentes na prática.**
   `is_brand_organic` → "Conteúdo promocional". `is_branded_content` → "Parceria
   paga", e vence se ambos forem `true`. Decidir por política de campanha, não por
   default.

6. **`HTTP 200` não significa sucesso.** A TikTok retorna 200 com falha no corpo.
   Toda resposta passa por `http.py`, que valida o campo `code`. Nunca chamar
   `requests` direto de um módulo de domínio.

7. **Toda URL de mídia precisa estar em propriedade verificada.** HTTPS, sem
   redirect (qualquer `3xx` invalida), TTL ≥ 30 min. Verificação de domínio casa
   subdomínios para baixo, nunca para cima.

---

## Limites operacionais

| Limite | Valor |
|---|---|
| Publicação orgânica | 6 posts/min, **teto de 15/dia por conta** |
| Accounts API | 40 QPM por conta autorizada, por endpoint |
| Marketing API (Basic) | 10 QPS / 600 QPM / 864.000 QPD — **por app, não por anunciante** |
| `/ad/create/` (Basic) | 5 QPS |
| Relatório assíncrono | 2 QPS / 4.500 por dia, em todos os níveis |
| Relatório síncrono | janela de 30 dias com `stat_time_day`; teto de 20.000 ads (trunca silenciosamente) |
| Vídeo orgânico | ≤ 1 GB, 3–600 s, ≥ 360×360, 23–60 FPS |
| Vídeo de anúncio | ≤ 500 MB, timeout de 10 s no upload |
| Legenda | 2.200 caracteres, máx. 30 menções |

Backoff: QPM estourado → esperar 5 min. QPD estourado → esperar até 00:00 UTC.

Rodar dois processos com as mesmas credenciais estoura o balde do app silenciosamente.
Um processo por app.

---

## Regras de orçamento

- Piso de campanha tem contradição ativa na documentação da TikTok (R$ 20 vs R$ 50).
  **Contorno adotado:** criar campanha com `budget_mode = BUDGET_MODE_INFINITE`
  (válido com CBO desligado) e controlar gasto no ad group, onde o piso de R$ 20 é
  inequívoco.
- Atualização de orçamento precisa ser ≥ 105% do gasto atual.
- Nenhuma operação que gasta dinheiro roda sem confirmação explícita. `--dry-run` é
  o default de todo comando de escrita.

---

## Pipeline de mídia

**Bytes de vídeo nunca passam pelo contexto do agente nem por MCP.** O
`download_file_content` do Google Drive MCP devolve base64 na resposta da ferramenta
e quebra bem abaixo do tamanho de um vídeo.

Fluxo correto: Drive API (metadados e IDs) → download resumível para disco →
upload para Cloudflare R2 → servir de domínio verificado → passar a URL para a TikTok.

---

## Usos proibidos pela TikTok

A TikTok reserva o direito de revogar o acesso à Accounts API **sem aviso prévio**.
Não implementar:

- migrar conteúdo do TikTok para outra conta ou outra plataforma;
- baixar vídeos/imagens do TikTok e promover solução de terceiros para salvar mídia;
- agregar dados de perfis de criadores autorizados para montar programa próprio de
  descoberta/ranking de influenciadores (isso é o TikTok One).

Automação por navegador (Selenium/Playwright logado) está **fora de escopo
permanentemente** — viola os Termos de Desenvolvedor e resulta em banimento.

---

## Estado do cadastro

- [ ] CNPJ
- [ ] Domínio próprio
- [ ] E-mail no domínio (gmail é rejeitado no cadastro)
- [ ] Site institucional público (com política de privacidade e termos visíveis sem login)
- [ ] Formulário de Acesso à Accounts API
- [ ] Perfil de desenvolvedor aprovado (3 dias úteis)
- [ ] App aprovado com escopo TikTok Accounts / id 18000000 (2–3 dias úteis)
- [x] Conta TikTok for Business (só isso já libera o MCP oficial de anúncios)

Enquanto os itens acima não estiverem marcados, o módulo `organic/` roda apenas
contra a URL de teste oficial da TikTok e o módulo `ads/` opera via MCP oficial.
