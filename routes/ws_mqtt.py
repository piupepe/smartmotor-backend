"""
routes/ws.py  — WebSocket broadcaster com fonte MQTT (ESP32) + fallback simulação
Prioridade: MQTT (ESP32 real) > Modbus TCP (simulador local) > simulação embutida
"""

import asyncio
import json
import math
import random
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

LIM = {
    "vib":  {"w": 4.5, "c": 7.1},
    "temp": {"w": 75.0, "c": 90.0},
}

# ── Simulação embutida (último recurso) ───────────────────────────────────────
_sim = {
    "temp": 62.0, "vib_x": 1.4, "vib_y": 1.2,
    "vib_z": 1.7, "rpm": 1735.0, "hours": 1248.5, "degrad": 0.2,
}

def _sim_tick() -> dict:
    d = _sim["degrad"]
    spike = 0.4 * d if random.random() < 0.05 else 0.0
    _sim["temp"]  = max(28, min(98,   _sim["temp"]  + (random.random()-0.5)*0.36 + 0.02*d))
    _sim["vib_x"] = max(0.02, min(6,  _sim["vib_x"] + (random.random()-0.5)*0.06 + 0.015*d + spike))
    _sim["vib_y"] = max(0.02, min(6,  _sim["vib_y"] + (random.random()-0.5)*0.06 + 0.014*d + spike))
    _sim["vib_z"] = max(0.02, min(6,  _sim["vib_z"] + (random.random()-0.5)*0.08 + 0.018*d + spike))
    _sim["rpm"]   = max(0,    min(1800, _sim["rpm"] + (random.random()-0.5)*6))
    _sim["hours"] = round(_sim["hours"] + 0.000556, 3)
    rms = math.sqrt((_sim["vib_x"]**2 + _sim["vib_y"]**2 + _sim["vib_z"]**2) / 3)
    sv  = max(0, 60 * (1 - min(rms / 7.1, 1)))
    st  = max(0, 40 * (1 - min((_sim["temp"] - 35) / 55, 1)))
    return {
        "temperatura":   round(_sim["temp"],  2),
        "vibration_x":   round(_sim["vib_x"], 3),
        "vibration_y":   round(_sim["vib_y"], 3),
        "vibration_z":   round(_sim["vib_z"], 3),
        "vibration_rms": round(rms, 3),
        "rpm":           round(_sim["rpm"]),
        "frequencia_hz": 60.0,
        "saude_score":   int(sv + st),
        "horas_operacao":_sim["hours"],
        "status_motor":  1,
        "codigo_falha":  0,
        "source":        "sim",
    }


# ── Enriquece payload para o frontend ─────────────────────────────────────────
def _enrich(raw: dict) -> dict:
    temp = raw.get("temperatura", 0)
    rms  = raw.get("vibration_rms", 0)
    if not rms:
        ax, ay, az = raw.get("vibration_x",0), raw.get("vibration_y",0), raw.get("vibration_z",0)
        rms = round(math.sqrt((ax**2 + ay**2 + az**2) / 3), 3)
    return {
        **raw,
        "temp":   round(temp, 2),
        "ax":     round(raw.get("vibration_x", 0), 3),
        "ay":     round(raw.get("vibration_y", 0), 3),
        "az":     round(raw.get("vibration_z", 0), 3),
        "vibRMS": round(rms, 3),
        "freq":   raw.get("frequencia_hz", 0),
        "rpm":    raw.get("rpm", 0),
        "hours":  raw.get("horas_operacao", 0),
        "score":  raw.get("saude_score", 0),
        "bat":    100.0,
        "t":      datetime.now().strftime("%H:%M:%S"),
    }


# ── Gerenciador de conexões ────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self._conns: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._conns.append(ws)
        print(f"[WS] +cliente  total={len(self._conns)}")

    def disconnect(self, ws: WebSocket):
        if ws in self._conns:
            self._conns.remove(ws)
        print(f"[WS] -cliente  total={len(self._conns)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self._conns:
                self._conns.remove(ws)

    @property
    def count(self): return len(self._conns)


manager = ConnectionManager()


# ── Broadcaster ───────────────────────────────────────────────────────────────
async def ws_broadcaster():
    """
    Ordem de prioridade a cada ciclo de 2s:
      1. MQTT (ESP32 real via HiveMQ)
      2. Modbus TCP (simulador local)
      3. Simulação embutida (fallback final)
    """
    print("[WS] Broadcaster iniciado")

    while True:
        await asyncio.sleep(2)
        if manager.count == 0:
            continue

        raw = None
        source = "sim"

        # ── Tenta MQTT primeiro ───────────────────────────────────────────────
        try:
            from services.mqtt_reader import get_latest, is_connected
            if is_connected():
                raw = get_latest()
                if raw:
                    source = "mqtt"
        except ImportError:
            pass

        # ── Fallback: Modbus TCP ──────────────────────────────────────────────
        if not raw:
            try:
                raw = await asyncio.get_event_loop().run_in_executor(
                    None,
                    __import__("services.modbus_reader", fromlist=["read_smartmotor_registers"])
                    .read_smartmotor_registers
                )
                if raw:
                    source = "modbus"
            except Exception:
                pass

        # ── Fallback final: simulação ─────────────────────────────────────────
        if not raw:
            raw = _sim_tick()
            source = "sim"

        payload = _enrich({**raw, "source": source})
        await manager.broadcast(payload)


# ── Endpoint WebSocket ─────────────────────────────────────────────────────────
@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_text()
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
