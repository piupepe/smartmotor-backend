from typing import Optional, Dict, Any
from pymodbus.client import ModbusTcpClient


def read_smartmotor_registers() -> Optional[Dict[str, Any]]:
    client = ModbusTcpClient(host="127.0.0.1", port=502)  # use 502 se configurou 502

    try:
        print("Tentando conectar no Modbus TCP...")
        ok = client.connect()
        print(f"connect() = {ok}")

        if not ok:
            print("Falha ao conectar no Modbus TCP")
            return None

        print("Lendo holding registers...")
        result = client.read_holding_registers(address=0, count=11, device_id=1)
        print(f"Resultado bruto: {result}")

        if result.isError():
            print(f"Erro Modbus TCP: {result}")
            return None

        regs = result.registers
        print(f"Registradores lidos: {regs}")

        return {
            "status_motor": regs[0],
            "frequencia_hz": regs[1] / 10.0,
            "rpm": regs[2],
            "temperatura": regs[3] / 10.0,
            "vibration_x": regs[4] / 100.0,
            "vibration_y": regs[5] / 100.0,
            "vibration_z": regs[6] / 100.0,
            "vibration_rms": regs[7] / 100.0,
            "saude_score": regs[8],
            "codigo_falha": regs[9],
            "horas_operacao": regs[10] / 10.0,
        }

    except Exception as e:
        print(f"Exceção Modbus TCP: {e}")
        return None

    finally:
        client.close()