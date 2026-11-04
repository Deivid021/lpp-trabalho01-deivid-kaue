"""
Cafezal em Tempo Real - servidor
Trabalho 01 - Linguagem de Programação e Paradigmas - 2026/2

O servidor é a FONTE DA VERDADE: guarda o estado do cafezal na memória,
escuta os PEDIDOS dos clientes (eventos *_solicitada / *_solicitado),
decide o que acontece e emite os FATOS (eventos no passado) para os
clientes. Os temporizadores do servidor também são fontes de eventos.

Execução: uvicorn server:app --reload
"""

import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
})











