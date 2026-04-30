"""
routes/ws.py
WebSocket endpoint — empurra dados do motor em tempo real para o frontend.

Fluxo:
  Modbus reader → broadcaster (a cada 2s) → todos os clientes WS conectados

Conexão: ws://localhost:8000/ws
"""

import asyncio
import json
import math
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.modbus_reader import read_smartmotor_registers

router = APIRouter(tags=["websocket"])

LIM = {
    "vib":  {"w": 4.5, "c": 7.1},
    "temp": {"w": 75.0, "c": 90.0},
}


# ── Gerenciador de conexões ───────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        print(f"[WS] Cliente conectado  — total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)
        print(f"[WS] Cliente desconectado — total: {len(self._connections)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self._connections:
                self._connections.remove(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# ── Enriquece dados do Modbus com campos calculados ───────────────────────────
def _enrich(raw: dict) -> dict:
    temp = raw["temperatura"]
    ax   = raw["vibration_x"]
    ay   = raw["vibration_y"]
    az   = raw["vibration_z"]
    rms  = raw.get("vibration_rms") or round(math.sqrt((ax**2 + ay**2 + az**2) / 3), 3)

    s_vib  = max(0, 60 * (1 - min(rms  / LIM["vib"]["c"],  1)))
    s_temp = max(0, 40 * (1 - min((temp - 35) / 55,        1)))
    score  = raw.get("saude_score") or int(s_vib + s_temp)

    from datetime import datetime
    t = datetime.now().strftime("%H:%M:%S")

    return {
        # campos originais do Modbus
        **raw,
        # aliases para o frontend (App.jsx usa esses nomes)
        "temp":    round(temp, 2),
        "ax":      round(ax,   3),
        "ay":      round(ay,   3),
        "az":      round(az,   3),
        "vibRMS":  round(rms,  3),
        "freq":    raw["frequencia_hz"],
        "rpm":     raw["rpm"],
        "hours":   raw["horas_operacao"],
        "score":   score,
        "bat":     100.0,       # ESP32 — implementar quando sensor estiver disponível
        "t":       t,
        # status da conexão
        "source":  "modbus",
    }


# ── Broadcaster assíncrono — chamado no lifespan do main.py ──────────────────
async def ws_broadcaster():
    """Lê Modbus a cada 2s e empurra para todos os clientes WS conectados."""
    print("[WS] Broadcaster iniciado")
    while True:
        await asyncio.sleep(2)
        if manager.count == 0:
            continue
        try:
            raw = await asyncio.get_event_loop().run_in_executor(
                None, read_smartmotor_registers
            )
            if raw:
                payload = _enrich(raw)
                await manager.broadcast(payload)
        except Exception as e:
            print(f"[WS] Erro no broadcaster: {e}")


# ── Endpoint WebSocket ────────────────────────────────────────────────────────
@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Mantém a conexão viva; aceita mensagens de controle futuras
            msg = await ws.receive_text()
            # ex: cliente envia {"cmd":"setpoint","value":1500}
            try:
                data = json.loads(msg)
                if data.get("cmd") == "setpoint":
                    from services.control_daemon import set_setpoint
                    set_setpoint(float(data["value"]))
                    await ws.send_json({"ack": "setpoint", "value": data["value"]})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(ws)