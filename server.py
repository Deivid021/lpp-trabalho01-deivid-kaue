"""
Cafezal em Tempo Real - servidor
Trabalho 01 - Linguagem de Programação e Paradigmas - 2026/2

O servidor é a FONTE DA VERDADE: guarda o estado do cafezal na memória,
escuta os PEDIDOS dos clientes (eventos *_solicitada / *_solicitado),
decide o que acontece e emite os FATOS (eventos no passado) para os
clientes. Os temporizadores do servidor também são fontes de eventos.

Execução: uvicorn server:app --reload
"""
import copy
import time

import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
})

# ---------------------------------------------------------------------------
# Regras do cafezal (ver docs/especificacao.md)
# ---------------------------------------------------------------------------
INTERVALO = 5            # segundos entre uma colheita automática e outra
PRODUCAO_INICIAL = 10    # café colhido a cada INTERVALO
GANHO_PLANTACAO = 5      # cada plantação concluída aumenta a colheita em 5
LIMITE_COLHEDORES = 3    # máximo de colhedores trabalhando ao mesmo tempo
INTERVALO_LOTE = 15      # a cada 15 s um lote de grãos fica pronto no pé
TAMANHO_LOTE = 30        # grãos por lote
PRAZO_LOTE = 12          # segundos para levar o lote ao terreiro antes de mofar
TEMPO_SECAGEM = 6        # segundos que o lote passa secando no terreiro
TORRA_POR_TORREFACAO = 10  # café seco torrado por torrefação a cada INTERVALO

# Catálogo de construções: custo em café, tempo de obra e efeito.
CONSTRUCOES = {
    "plantacao": {"nome": "Plantação", "emoji": "🌿", "custo": 40, "tempo": 6,
                  "efeito": "+5 café por colheita"},
    "terreiro": {"nome": "Terreiro", "emoji": "🟫", "custo": 60, "tempo": 8,
                 "efeito": "+1 vaga de secagem"},
    "torrefacao": {"nome": "Torrefação", "emoji": "🏭", "custo": 80, "tempo": 10,
                   "efeito": "torra 10 café seco por colheita"},
}

estado = {
    "fase": "aguardando",      # aguardando -> aberta -> encerrada
    "cafe": 150,               # café colhido (recurso primário)
    "cafe_seco": 0,            # café que já passou pelo terreiro
    "cafe_torrado": 0,         # recurso refinado
    "lotes": [],               # lotes no pé ou secando no terreiro
    "mofados": 0,              # lotes perdidos por não secarem a tempo
    "colhedores": 0,           # colhedores ocupados agora
    "limite": LIMITE_COLHEDORES,
    "producao": PRODUCAO_INICIAL,
    "intervalo": INTERVALO,
    "em_obra": 0,
    "concluidas": {            # construções prontas, por tipo
        "plantacao": 1,
        "terreiro": 1,
        "torrefacao": 0,
    },
    "obras": [],               # tudo o que está desenhado no mapa
    "tipos": CONSTRUCOES,
}

jogadores = {}  # sid -> {"nome": ..., "papel": ...}
_ultimo_id = 0


def novo_id():
    global _ultimo_id
    _ultimo_id += 1
    return _ultimo_id


def agora_ms():
    return int(time.time() * 1000)


# O cafezal já começa com as construções iniciais desenhadas no mapa.
for _tipo, _qtd in estado["concluidas"].items():
    for _ in range(_qtd):
        estado["obras"].append({"id": novo_id(), "tipo": _tipo, "status": "pronta"})


def fato(causa, **extras):
    """Monta o payload de um FATO: cópia do estado atual, a CAUSA (o pedido
    ou o temporizador que gerou o fato), o horário do servidor e extras."""
    return {"estado": copy.deepcopy(estado), "causa": causa,
            "agora": agora_ms(), **extras}


@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    jogadores[sid] = {
        "nome": (auth.get("nome") or "Anônimo")[:20],
        "papel": "mestre" if auth.get("papel") == "mestre" else "jogador",
    }
    # EMIT servidor -> UM cliente: só quem acabou de chegar precisa do
    # estado completo; quem já estava conectado já o tem.
    await sio.emit("estado.sincronizado", fato("conexao"), to=sid)


@sio.event
async def disconnect(sid, *args):
    jogadores.pop(sid, None)


async def recusar(sid, motivo, causa, **extras):
    """EMIT servidor -> SÓ quem pediu: a recusa também é um evento, mas
    não muda o estado, então os outros jogadores não precisam saber."""
    await sio.emit("operacao.recusada",
                   {"motivo": motivo, "causa": causa, **extras}, to=sid)


# ON pedido do Mestre: abrir a safra.
@sio.on("safra.abertura_solicitada")
async def abrir_safra(sid, dados=None):
    pedido = "safra.abertura_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir a safra", pedido)
        return
    if estado["fase"] != "aguardando":
        await recusar(sid, "A safra já foi aberta", pedido)
        return
    estado["fase"] = "aberta"
    # Os temporizadores passam a ser fontes de eventos a partir daqui.
    sio.start_background_task(colheita)
    sio.start_background_task(ciclo_de_lotes)
    # EMIT servidor -> TODOS: a mudança de fase vale para o cafezal inteiro.
    await sio.emit("safra.iniciada", fato(pedido, por=jogadores[sid]["nome"]))


# ON pedido do Jogador: construir (plantação, terreiro ou torrefação).
@sio.on("construcao.solicitada")
async def construir(sid, dados=None):
    pedido = "construcao.solicitada"
    tipo = (dados or {}).get("tipo", "plantacao")
    info = CONSTRUCOES.get(tipo)
    # Valida TUDO antes de alterar o estado e SEM await no meio: o servidor
    # trata um evento por vez, então dois pedidos simultâneos são decididos
    # em sequência (um vence e o outro recebe a recusa).
    if info is None:
        motivo = "Tipo de construção desconhecido"
    elif jogadores[sid]["papel"] == "mestre":
        motivo = "O Mestre não constrói, só abre e encerra a safra"
    elif estado["fase"] != "aberta":
        motivo = "A safra não está aberta"
    elif estado["cafe"] < info["custo"]:
        motivo = f"Café insuficiente (precisa de {info['custo']})"
    elif estado["colhedores"] >= estado["limite"]:
        motivo = "Nenhum colhedor livre"
    else:
        motivo = None
    if motivo:
        await recusar(sid, motivo, pedido, tipo=tipo)
        return
    estado["cafe"] -= info["custo"]
    estado["colhedores"] += 1
    estado["em_obra"] += 1
    obra = {"id": novo_id(), "tipo": tipo, "status": "obra",
            "inicio": agora_ms(), "duracao": info["tempo"]}
    estado["obras"].append(obra)
    nome = jogadores[sid]["nome"]
    # EMIT servidor -> TODOS: o pedido foi aceito e o estoque mudou para todos.
    await sio.emit("construcao.iniciada", fato(pedido, por=nome, obra=obra))
    # A obra termina sozinha: um temporizador vai gerar construcao.concluida.
    sio.start_background_task(concluir_obra, obra, nome)


async def colheita():
    """Temporizador: a cada INTERVALO o cafezal produz café sozinho."""
    while estado["fase"] == "aberta":
        await sio.sleep(INTERVALO)  # sio.sleep não trava o servidor
        if estado["fase"] != "aberta":
            break
        colhido = estado["producao"]
        estado["cafe"] += colhido
        extras = {"colhido": colhido}
        # Recurso refinado: cada torrefação transforma café seco em torrado.
        capacidade = estado["concluidas"]["torrefacao"] * TORRA_POR_TORREFACAO
        torrado = min(estado["cafe_seco"], capacidade)
        estado["cafe_seco"] -= torrado
        estado["cafe_torrado"] += torrado
        extras["torrado"] = torrado
        # EMIT servidor -> TODOS, sem ninguém pedir: a causa é o temporizador.
        await sio.emit("recurso.produzido", fato("temporizador", **extras))


async def concluir_obra(obra, nome):
    """Temporizador da obra: depois de alguns segundos ela fica pronta."""
    await sio.sleep(obra["duracao"])
    if estado["fase"] != "aberta":
        return
    estado["colhedores"] -= 1
    estado["em_obra"] -= 1
    estado["concluidas"][obra["tipo"]] += 1
    obra["status"] = "pronta"
    if obra["tipo"] == "plantacao":
        estado["producao"] += GANHO_PLANTACAO
    # EMIT servidor -> TODOS: o colhedor ficou livre e a construção apareceu.
    await sio.emit("construcao.concluida",
                   fato("construcao.iniciada (temporizador)", por=nome, obra=obra))


# ON pedido do Mestre: encerrar a safra.
@sio.on("safra.encerramento_solicitado")
async def encerrar_safra(sid, dados=None):
    pedido = "safra.encerramento_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode encerrar a safra", pedido)
        return
    if estado["fase"] != "aberta":
        await recusar(sid, "A safra não está aberta", pedido)
        return
    estado["fase"] = "encerrada"
    # EMIT servidor -> TODOS: a partir daqui novos pedidos serão recusados
    # e os temporizadores param no próximo ciclo.
    await sio.emit("safra.encerrada", fato(pedido, por=jogadores[sid]["nome"]))


# ---------------------------------------------------------------------------
# Evento próprio do cafezal: o grão MOFA se não for levado ao terreiro a tempo
# ---------------------------------------------------------------------------
async def ciclo_de_lotes():
    """Temporizador: de tempos em tempos um lote de grãos fica pronto no pé."""
    while estado["fase"] == "aberta":
        await sio.sleep(INTERVALO_LOTE)
        if estado["fase"] != "aberta":
            break
        lote = {"id": novo_id(), "qtd": TAMANHO_LOTE, "status": "aguardando",
                "inicio": agora_ms(), "prazo": PRAZO_LOTE}
        estado["lotes"].append(lote)
        # EMIT servidor -> TODOS: qualquer jogador pode levar o lote ao terreiro.
        await sio.emit("lote.colhido", fato("temporizador", lote=lote))
        # Cada lote tem o seu próprio temporizador de prazo.
        sio.start_background_task(vigiar_lote, lote)


async def vigiar_lote(lote):
    """Temporizador do prazo: se ninguém levou o lote ao terreiro, ele mofa."""
    await sio.sleep(lote["prazo"])
    if estado["fase"] != "aberta" or lote["status"] != "aguardando":
        return
    estado["lotes"].remove(lote)
    estado["mofados"] += 1
    # EMIT servidor -> TODOS: o lote se perdeu para o cafezal inteiro.
    await sio.emit("lote.mofado", fato("lote.colhido (temporizador)", lote=lote))


def terreiros_ocupados():
    return sum(1 for l in estado["lotes"] if l["status"] == "secando")


# ON pedido do Jogador: levar um lote ao terreiro para secar.
@sio.on("secagem.solicitada")
async def secar(sid, dados=None):
    pedido = "secagem.solicitada"
    lote_id = (dados or {}).get("lote")
    lote = next((l for l in estado["lotes"] if l["id"] == lote_id), None)
    # Mesma regra da construção: validar e alterar sem await no meio, então
    # se dois jogadores pedirem o mesmo lote, só o primeiro consegue.
    if jogadores[sid]["papel"] == "mestre":
        motivo = "O Mestre não leva lotes ao terreiro"
    elif estado["fase"] != "aberta":
        motivo = "A safra não está aberta"
    elif lote is None:
        motivo = "Esse lote não existe mais (secou ou mofou)"
    elif lote["status"] != "aguardando":
        motivo = "Esse lote já está no terreiro"
    elif terreiros_ocupados() >= estado["concluidas"]["terreiro"]:
        motivo = "Todos os terreiros estão ocupados"
    else:
        motivo = None
    if motivo:
        await recusar(sid, motivo, pedido, lote=lote_id)
        return
    lote["status"] = "secando"
    lote["inicio"] = agora_ms()
    lote["duracao"] = TEMPO_SECAGEM
    nome = jogadores[sid]["nome"]
    # EMIT servidor -> TODOS: o lote saiu do pé e ocupa um terreiro.
    await sio.emit("secagem.iniciada", fato(pedido, por=nome, lote=lote))
    sio.start_background_task(concluir_secagem, lote, nome)


async def concluir_secagem(lote, nome):
    """Temporizador da secagem: o lote vira café seco."""
    await sio.sleep(TEMPO_SECAGEM)
    if estado["fase"] != "aberta":
        return
    estado["lotes"].remove(lote)
    estado["cafe_seco"] += lote["qtd"]
    # EMIT servidor -> TODOS: o terreiro ficou livre e o estoque mudou.
    await sio.emit("secagem.concluida",
                   fato("secagem.iniciada (temporizador)", por=nome, lote=lote))
