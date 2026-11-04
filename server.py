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

# Catálogo de construções: custo em café, tempo de obra e efeito.
CONSTRUCOES = {
    "plantacao": {"nome": "Plantação", "emoji": "🌿", "custo": 40, "tempo": 6,
                  "efeito": "+5 café por colheita"},
}

estado = {
    "fase": "aguardando",      # aguardando -> aberta -> encerrada
    "cafe": 150,               # café colhido (recurso primário)
    "colhedores": 0,           # colhedores ocupados agora
    "limite": LIMITE_COLHEDORES,
    "producao": PRODUCAO_INICIAL,
    "intervalo": INTERVALO,
    "em_obra": 0,
    "concluidas": {            # construções prontas, por tipo
        "plantacao": 1,
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










