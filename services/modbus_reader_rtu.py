"""
services/modbus_reader_rtu.py
Cliente Modbus RTU via RS485 (serial) — ESP32 Módulo A.

Configuração:
  - Adaptador USB-RS485 conectado ao PC
  - Windows: porta COM3, COM4, etc  → MODBUS_PORT=COM3
  - Linux:   /dev/ttyUSB0           → MODBUS_PORT=/dev/ttyUSB0

Variáveis de ambiente:
  MODBUS_PORT      porta serial   (padrão: COM3)
  MODBUS_BAUD      baud rate      (padrão: 9600)
  MODBUS_DEVICE_ID device ID      (padrão: 1)

Mapa de registradores — idêntico ao TCP (modbus_reader.py):
  [0]  status_motor    [6]  vibration_z  ×100
  [1]  frequencia_hz ×10   [7]  vibration_rms ×100
  [2]  rpm             [8]  saude_score
  [3]  temperatura ×10 [9]  codigo_falha
  [4]  vibration_x ×100   [10] horas_operacao ×10
  [5]  vibration_y ×100
"""

import os
import threading
from typing import Any, Dict, Optional

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

# ── Configuração ──────────────────────────────────────────────────────────────
MODBUS_PORT      = os.getenv("MODBUS_PORT",      "COM3")
MODBUS_BAUD      = int(os.getenv("MODBUS_BAUD",  "9600"))
DEVICE_ID        = int(os.getenv("MODBUS_DEVICE_ID", "1"))
REG_START        = 0
REG_COUNT        = 11

# ── Singleton ─────────────────────────────────────────────────────────────────
_client: Optional[ModbusSerialClient] = None
_lock   = threading.Lock()


def _get_client() -> ModbusSerialClient:
    global _client
    if _client is None:
        _client = ModbusSerialClient(
            port=MODBUS_PORT,
            baudrate=MODBUS_BAUD,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=1,
        )

    if not _client.is_socket_open():
        print(f"[ModbusRTU] Conectando em {MODBUS_PORT} @ {MODBUS_BAUD} baud...")
        if not _client.connect():
            _client = None
            raise ConnectionError(f"Falha ao abrir {MODBUS_PORT}")
        print("[ModbusRTU] ✅ Porta serial aberta")

    return _client


def _parse(regs: list) -> Dict[str, Any]:
    return {
        "status_motor":   regs[0],
        "frequencia_hz":  regs[1] / 10.0,
        "rpm":            float(regs[2]),
        "temperatura":    regs[3] / 10.0,
        "vibration_x":    regs[4] / 100.0,
        "vibration_y":    regs[5] / 100.0,
        "vibration_z":    regs[6] / 100.0,
        "vibration_rms":  regs[7] / 100.0,
        "saude_score":    regs[8],
        "codigo_falha":   regs[9],
        "horas_operacao": regs[10] / 10.0,
    }


def read_smartmotor_registers() -> Optional[Dict[str, Any]]:
    with _lock:
        try:
            client = _get_client()
            result = client.read_holding_registers(
                address=REG_START,
                count=REG_COUNT,
                device_id=DEVICE_ID,
            )
            if result.isError():
                print(f"[ModbusRTU] Erro na leitura: {result}")
                return None
            return _parse(result.registers)

        except (ModbusException, ConnectionError) as e:
            print(f"[ModbusRTU] {e} — reconectando no próximo ciclo")
            if _client:
                _client.close()
            return None
        except Exception as e:
            print(f"[ModbusRTU] Erro inesperado: {e}")
            return None


def close_connection() -> None:
    global _client
    with _lock:
        if _client and _client.is_socket_open():
            _client.close()
        _client = None
        print("[ModbusRTU] Porta serial encerrada")
