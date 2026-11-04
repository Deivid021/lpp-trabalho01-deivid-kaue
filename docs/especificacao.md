# Especificação – Cafezal em Tempo Real

Trabalho 01 – Programação Orientada a Eventos · Linguagem de Programação e Paradigmas · 2026/2
Dupla: Deivid Sestren e Kaue Gorges · Tipo de vila sorteado: **23 – Cafezal**

## 1. Visão geral

Vários jogadores cuidam do mesmo cafezal ao mesmo tempo. O **Mestre** abre e encerra a safra. Os **Jogadores** constroem plantações, terreiros e torrefações e levam os lotes de grãos ao terreiro antes que mofem. O servidor guarda o estado, decide cada pedido e avisa os jogadores com fatos. O cliente só pede e mostra.

Cadeia de recursos: **café colhido** (primário) → **café seco** (depois do terreiro) → **café torrado** (refinado, na torrefação).

## 2. Regras

### Estado inicial

| Item | Valor |
|---|---|
| Fase | aguardando (→ aberta → encerrada) |
| Café colhido | 150 |
| Café seco / café torrado | 0 / 0 |
| Colhedores ocupados / limite | 0 / 3 |
| Colheita automática | +10 café a cada 5 s (120/min) |
| Construções prontas | 1 plantação e 1 terreiro |

### Construções

| Construção | Custo | Tempo de obra | Efeito ao concluir |
|---|---|---|---|
| Plantação | 40 café | 6 s | +5 café em cada colheita automática |
| Terreiro | 60 café | 8 s | +1 lote pode secar ao mesmo tempo |
| Torrefação | 80 café | 10 s | a cada colheita torra até 10 café seco → 10 café torrado |

- Cada obra ocupa **1 colhedor** do início ao fim; ao concluir, o colhedor fica livre.
- O pedido de construção é recusado se: a safra não está aberta; falta café; não há colhedor livre; quem pediu é o Mestre.
- Validação e débito acontecem juntos: dois pedidos simultâneos são decididos um de cada vez.

### Lotes de grãos (o que expira: "o grão mofa se não secar")

- Com a safra aberta, a cada **15 s** um lote de **30 grãos** fica pronto no pé.
- O lote precisa ser levado ao terreiro em até **12 s**; senão ele **mofa** e é perdido.
- A secagem leva **6 s** e transforma o lote em **30 café seco**.
- Cada terreiro pronto seca **1 lote por vez**.
- O pedido de secagem é recusado se: a safra não está aberta; o lote não existe mais; o lote já está no terreiro; todos os terreiros estão ocupados; quem pediu é o Mestre.

### Safra

- Só o Mestre abre (se a fase for aguardando) e encerra (se a fase for aberta).
- Ao abrir, começam a colheita automática e o ciclo de lotes.
- Ao encerrar, colheita, lotes, obras e secagens param; qualquer novo pedido é recusado.

## 3. Tabela de eventos

Padrão: `objeto.acao_solicitada` para pedidos do cliente e `objeto.acao_no_passado` para fatos confirmados pelo servidor.

| Evento | Emite | Recebe | Causa | O que muda |
|---|---|---|---|---|
| estado.sincronizado | Servidor | Só quem conectou | conexão | O cliente recebe o estado atual e desenha o cafezal |
| safra.abertura_solicitada | Mestre | Servidor | clique | Pedido para abrir a safra |
| safra.iniciada | Servidor | Todos | safra.abertura_solicitada | Fase = aberta; colheita e ciclo de lotes começam |
| construcao.solicitada | Jogador | Servidor | clique | Pedido para construir (tipo: plantação, terreiro ou torrefação) |
| construcao.iniciada | Servidor | Todos | construcao.solicitada | Debita o custo, ocupa 1 colhedor e cria o canteiro de obras |
| operacao.recusada | Servidor | Só quem pediu | o pedido recusado | Nada muda; mostra o motivo |
| recurso.produzido | Servidor | Todos | temporizador | Café colhido sobe; torrefações transformam café seco em torrado |
| construcao.concluida | Servidor | Todos | construcao.iniciada (temporizador) | Libera o colhedor e aplica o efeito da construção |
| lote.colhido | Servidor | Todos | temporizador | Um lote de 30 grãos aparece no pé com prazo de 12 s |
| secagem.solicitada | Jogador | Servidor | clique | Pedido para levar um lote ao terreiro |
| secagem.iniciada | Servidor | Todos | secagem.solicitada | O lote passa a secar e ocupa um terreiro |
| secagem.concluida | Servidor | Todos | secagem.iniciada (temporizador) | Café seco +30; o terreiro fica livre |
| lote.mofado | Servidor | Todos | lote.colhido (temporizador) | O lote é perdido; contador de mofados +1 |
| safra.encerramento_solicitado | Mestre | Servidor | clique | Pedido para encerrar a safra |
| safra.encerrada | Servidor | Todos | safra.encerramento_solicitado | Fase = encerrada; novos pedidos são recusados |

## 4. Cenários de teste

### Cenário 1 – Recusa
**Dado que** a safra está na fase aguardando,
**quando** o Jogador A emite `construcao.solicitada` (plantação),
**então** o servidor emite `operacao.recusada` com o motivo "A safra não está aberta" **apenas para A**, e o café continua em 150 para todos.

### Cenário 2 – Passagem do tempo
**Dado que** a safra está aberta, há 150 de café e o Jogador A emitiu `construcao.solicitada` (plantação),
**quando** o servidor emite `construcao.iniciada` (café 110, colhedores 1/3),
**então** a cada 5 s o servidor emite `recurso.produzido` (causa: temporizador) com +10 café para todos, e após 6 s emite `construcao.concluida` (causa: construcao.iniciada (temporizador)): colhedores voltam a 0/3 e a colheita passa a +15.

### Cenário 3 – Disputa entre dois jogadores
**Dado que** a safra está aberta e há 2 de 3 colhedores ocupados,
**quando** os Jogadores A e B emitem `construcao.solicitada` ao mesmo tempo,
**então** o servidor emite `construcao.iniciada` para todos por causa de um deles (3/3) e `operacao.recusada` ("Nenhum colhedor livre") **apenas para o outro**. Os colhedores nunca passam de 3.

### Cenário 4 – Grão mofa (evento próprio)
**Dado que** a safra está aberta e o servidor emitiu `lote.colhido` (lote #7, prazo 12 s),
**quando** nenhum jogador emite `secagem.solicitada` para o lote #7 em 12 s,
**então** o servidor emite `lote.mofado` (causa: lote.colhido (temporizador)) para todos, o lote some e o contador de mofados sobe 1.
Variação: se A e B emitem `secagem.solicitada` para o mesmo lote ao mesmo tempo, o servidor emite `secagem.iniciada` por causa de um deles e `operacao.recusada` ("Esse lote já está no terreiro") só para o outro.
