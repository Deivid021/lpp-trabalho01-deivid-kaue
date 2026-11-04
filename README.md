# ☕ Cafezal em Tempo Real

Trabalho 01 – Programação Orientada a Eventos · Linguagem de Programação e Paradigmas · 2026/2
Tipo de vila: **23 – Cafezal** (café → café torrado)

## Integrantes

| Nome | GitHub |
|---|---|
| Deivid Sestren | [@Deivid021](https://github.com/Deivid021) |
| Kaue Gorges | [@Gorgesw](https://github.com/Gorgesw) |

## Tecnologias

- Servidor: Python 3, python-socketio e uvicorn (estado na memória do servidor)
- Comunicação em tempo real: Socket.IO
- Tela: Vue 3 (painel, botões e avisos) e Phaser 3 (cafezal desenhado), carregados por CDN

## Como instalar e executar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux ou macOS
pip install -r requirements.txt
uvicorn server:app --reload
```

Abra **http://localhost:8000** (não abra o arquivo direto com `file://`).

## Como testar com duas abas (ou mais)

1. Aba 1: digite um nome, escolha **Mestre** e entre. Aba 2 (e 3): escolha **Jogador**.
2. No Jogador, clique em **Construir Plantação** antes de abrir a safra → recusa só nessa aba (tela treme, aviso vermelho).
3. No Mestre, clique em **Abrir safra** → todas as abas mudam para "Safra aberta" sem recarregar.
4. No Jogador, construa: o café cai, os colhedores sobem e aparece o canteiro 🚧 em todas as abas. Após o tempo de obra ele vira a construção pronta.
5. Observe o café subindo sozinho a cada 5 s (`recurso.produzido`, causa: temporizador).
6. A cada 15 s aparece um lote 🍒 no pé. Clique em **Levar ao terreiro** antes de 12 s; se ninguém levar, o servidor emite `lote.mofado`.
7. Disputa: com 2/3 colhedores ocupados, clique em **Construir** em dois Jogadores ao mesmo tempo: só um consegue; o outro recebe "Nenhum colhedor livre". O mesmo vale para dois jogadores pedindo o mesmo lote.
8. Construa uma **Torrefação**: a cada colheita ela transforma café seco em café torrado.
9. No Mestre, clique em **Encerrar safra**: o cafezal escurece e qualquer pedido novo é recusado.

Obs.: o estado fica na memória. Ao reiniciar o servidor (ou salvar com `--reload`), o cafezal volta ao início; recarregue as abas.

## Eventos

A tabela completa, as regras e os cenários de teste estão em [docs/especificacao.md](docs/especificacao.md).

## Respostas às perguntas

**1. Quais eventos o seu sistema emite e escuta?**

- O cliente **emite** (pedidos): `safra.abertura_solicitada`, `construcao.solicitada`, `secagem.solicitada` e `safra.encerramento_solicitado`.
- O servidor **escuta** esses pedidos e **emite** os fatos: `estado.sincronizado` (só para quem conectou), `safra.iniciada`, `construcao.iniciada`, `recurso.produzido`, `construcao.concluida`, `lote.colhido`, `secagem.iniciada`, `secagem.concluida`, `lote.mofado`, `safra.encerrada` (para todos) e `operacao.recusada` (só para quem pediu).
- O cliente **escuta** todos esses fatos com `ouvir(...)` e reage atualizando o estado, o painel e o desenho.

**2. Como o sistema sabe quando deve atualizar os outros jogadores?**

O cliente nunca muda o estado sozinho e nunca fica perguntando se algo mudou. Sempre que o servidor aceita um pedido, ou que um temporizador dispara, ele altera o estado e emite um fato com `sio.emit(evento, dados)` para todos os clientes conectados. Cada cliente tem um handler (`ouvir`) para esse evento e redesenha a tela ao recebê-lo. Quando só quem pediu precisa saber (recusa ou sincronização ao conectar), o servidor emite com `to=sid`.

**3. Que parte do código mostra claramente o uso do paradigma orientado a eventos?**

- `server.py`: os handlers `@sio.on("construcao.solicitada")` e `@sio.on("secagem.solicitada")`, que validam e alteram o estado sem `await` no meio e respondem com `construcao.iniciada`/`secagem.iniciada` para todos ou `operacao.recusada` só para quem pediu.
- `server.py`: os temporizadores `colheita()`, `concluir_obra()`, `ciclo_de_lotes()`, `vigiar_lote()` e `concluir_secagem()`, que emitem fatos sem nenhum clique (causa: temporizador).
- `client/index.html`: a região **ESCUTAS**, em que cada `ouvir("evento", "reação", função)` liga um fato do servidor a uma reação na tela, e as funções da região **PEDIDOS**, que só usam `pedir(...)`.

## Extras e adaptações ao Cafezal

- Três tipos de construção (plantação, terreiro e torrefação), cada uma com custo, tempo e efeito próprios.
- Recurso refinado: café colhido → café seco (terreiro) → café torrado (torrefação).
- Evento próprio com prazo: `lote.colhido` → `secagem.solicitada`/`secagem.iniciada`/`secagem.concluida` ou `lote.mofado`.
- Segunda disputa: dois jogadores pedindo o mesmo lote.
- Contadores por evento no Painel de eventos (requisito da dupla).

## Créditos visuais

Nenhuma arte de terceiros: o cafezal é desenhado com formas do Phaser e emojis do sistema.

## Uso de IA

Usamos o Claude (Anthropic) para montar o pacote de etapas do projeto e para publicar os commits no repositório, além de testar cada etapa. A especificação, as decisões do jogo e a revisão do código foram feitas por nós.
