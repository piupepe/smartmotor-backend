"""
services/modbus_reader.py
"""
import threading
from typing import Any, Dict, Optional

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from config import settings

MODBUS_HOST = settings.MODBUS_HOST
MODBUS_PORT = settings.MODBUS_PORT
DEVICE_ID   = settings.MODBUS_DEVICE_ID
TIMEOUT_S   = settings.MODBUS_TIMEOUT_S
REG_START   = 0
REG_COUNT   = 11

_client: Optional[ModbusTcpClient] = None
_lock   = threading.Lock()


def _get_client() -> ModbusTcpClient:
    global _client
    if _client is None:
        _client = ModbusTcpClient(host=MODBUS_HOST, port=MODBUS_PORT, timeout=TIMEOUT_S)
    if not _client.is_socket_open():
        print(f"[Modbus] Conectando em {MODBUS_HOST}:{MODBUS_PORT}...")
        if not _client.connect():
            _client = None
            raise ConnectionError("Falha na conexão Modbus TCP")
        print("[Modbus] ✅ Conectado")
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
            # pymodbus 3.13+: parâmetro renomeado de 'slave' para 'unit'
            result = client.read_holding_registers(
                address=REG_START,
                count=REG_COUNT,
                device_id=DEVICE_ID,
            )
            if result.isError():
                print(f"[Modbus] Erro na leitura: {result}")
                return None
            return _parse(result.registers)

        except (ModbusException, ConnectionError) as e:
            print(f"[Modbus] {e} — reconectando no próximo ciclo")
            if _client:
                _client.close()
            return None
        except Exception as e:
            print(f"[Modbus] Erro inesperado: {e}")
            return None


def close_connection() -> None:
    global _client
    with _lock:
        if _client and _client.is_socket_open():
            _client.close()
        _client = None
        print("[Modbus] Conexão encerrada")