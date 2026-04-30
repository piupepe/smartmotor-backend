"""
services/mqtt_reader.py
Subscriber MQTT — recebe dados do ESP32 via broker HiveMQ público.

Tópico: smartmotor/SM-001/telemetry
Broker: broker.hivemq.com:1883

Os dados chegam como JSON e ficam disponíveis via get_latest()
para o ws_broadcaster usar no lugar do modbus_reader.
"""

import json
import os
import threading
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

# ── Configuração ──────────────────────────────────────────────────────────────
MQTT_HOST    = os.getenv("MQTT_HOST",    "broker.hivemq.com")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC   = os.getenv("MQTT_TOPIC",   "smartmotor/SM-001/telemetry")
MQTT_CLIENT  = os.getenv("MQTT_CLIENT",  "SmartMotor-Backend-Render")

# ── Estado ────────────────────────────────────────────────────────────────────
_latest:    Optional[Dict[str, Any]] = None
_lock       = threading.Lock()
_connected  = False
_client:    Optional[mqtt.Client]    = None


# ── Callbacks ─────────────────────────────────────────────────────────────────
def _on_connect(client, userdata, flags, rc, properties=None):
    global _connected
    if rc == 0:
        _connected = True
        client.subscribe(MQTT_TOPIC, qos=0)
        print(f"[MQTT] ✅ Conectado ao {MQTT_HOST} — subscrito em {MQTT_TOPIC}")
    else:
        print(f"[MQTT] ❌ Falha na conexão rc={rc}")


def _on_disconnect(client, userdata, rc, properties=None, reasoncode=None):
    global _connected
    _connected = False
    print(f"[MQTT] Desconectado rc={rc} — reconectando...")


def _on_message(client, userdata, msg):
    global _latest
    try:
        data = json.loads(msg.payload.decode())
        with _lock:
            _latest = data
    except Exception as e:
        print(f"[MQTT] Erro ao parsear mensagem: {e}")


# ── API pública ───────────────────────────────────────────────────────────────
def get_latest() -> Optional[Dict[str, Any]]:
    """Retorna o dado mais recente recebido do ESP32."""
    with _lock:
        return _latest


def is_connected() -> bool:
    return _connected


def start_mqtt_client():
    """Inicia o cliente MQTT em thread daemon — chame no lifespan do main.py."""
    global _client

    _client = mqtt.Client(
        client_id=MQTT_CLIENT,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    _client.on_connect    = _on_connect
    _client.on_disconnect = _on_disconnect
    _client.on_message    = _on_message

    def _run():
        while True:
            try:
                print(f"[MQTT] Conectando em {MQTT_HOST}:{MQTT_PORT}...")
                _client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
                _client.loop_forever()
            except Exception as e:
                print(f"[MQTT] Erro: {e} — tentando em 5s")
                time.sleep(5)

    t = threading.Thread(target=_run, daemon=True, name="mqtt-client")
    t.start()
    print("[MQTT] Thread iniciada")


def stop_mqtt_client():
    global _client
    if _client:
        _client.disconnect()
        _client = None
