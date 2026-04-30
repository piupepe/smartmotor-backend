"""
modbus_simulator.py — SmartMotor SM-001
Servidor Modbus TCP puro (sem dependência de versão do pymodbus).
Funciona com qualquer versão do Python 3.8+.

Uso:
    python modbus_simulator.py              # porta 5020
    python modbus_simulator.py --port 502   # requer admin
"""

import argparse
import math
import random
import socket
import struct
import threading
import time

# ── Estado simulado ───────────────────────────────────────────────────────────
_lock = threading.Lock()
_s = {
    "running": True,
    "degrad":  0.20,
    "temp":    95.0,
    "vib_x":   1.42,
    "vib_y":   1.20,
    "vib_z":   1.70,
    "rpm":     1940.0,
    "freq":    40.0,
    "horas":   1248.5,
    "falha":   0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _rnd(s): return (random.random() - 0.5) * 2 * s
def _clamp(v, lo, hi): return max(lo, min(hi, v))
def _rms(x, y, z): return math.sqrt((x**2 + y**2 + z**2) / 3)

def _score(temp, rms):
    return int(
        max(0, 60 * (1 - _clamp(rms / 7.1, 0, 1))) +
        max(0, 40 * (1 - _clamp((temp - 35) / 55, 0, 1)))
    )

def _get_registers():
    """Retorna os 11 holding registers como lista de ints."""
    with _lock:
        rms = _rms(_s["vib_x"], _s["vib_y"], _s["vib_z"])
        return [
            int(_s["running"]),           # [0]  status_motor
            int(_s["freq"]  * 10),        # [1]  frequencia_hz ×10
            int(_s["rpm"]),               # [2]  rpm
            int(_s["temp"]  * 10),        # [3]  temperatura ×10
            int(_s["vib_x"] * 100),       # [4]  vibration_x ×100
            int(_s["vib_y"] * 100),       # [5]  vibration_y ×100
            int(_s["vib_z"] * 100),       # [6]  vibration_z ×100
            int(rms         * 100),       # [7]  vibration_rms ×100
            _score(_s["temp"], rms),      # [8]  saude_score
            int(_s["falha"]),             # [9]  codigo_falha
            int(_s["horas"] * 10),        # [10] horas_operacao ×10
        ]


# ── Protocolo Modbus TCP ──────────────────────────────────────────────────────
def _handle_request(data: bytes, all_regs: list) -> bytes | None:
    """
    Interpreta um frame Modbus TCP e retorna a resposta.
    Suporta apenas FC=03 (Read Holding Registers).
    """
    if len(data) < 12:
        return None

    # MBAP Header: Transaction(2) Protocol(2) Length(2) UnitID(1)
    transaction_id, protocol_id, length, unit_id = struct.unpack('>HHHB', data[:7])
    # PDU: FC(1) StartAddr(2) Quantity(2)
    fc, start_addr, quantity = struct.unpack('>BHH', data[7:12])

    if fc != 0x03:
        # Exceção: função não suportada
        exc_pdu = struct.pack('>BB', fc | 0x80, 0x01)
        mbap = struct.pack('>HHHB', transaction_id, 0, len(exc_pdu) + 1, unit_id)
        return mbap + exc_pdu

    # Lê os registradores solicitados
    end = start_addr + quantity
    if end > len(all_regs):
        # Exceção: endereço inválido
        exc_pdu = struct.pack('>BB', fc | 0x80, 0x02)
        mbap = struct.pack('>HHHB', transaction_id, 0, len(exc_pdu) + 1, unit_id)
        return mbap + exc_pdu

    regs = all_regs[start_addr:end]
    byte_count = len(regs) * 2
    pdu = struct.pack('>BB', 0x03, byte_count)
    for r in regs:
        pdu += struct.pack('>H', int(r) & 0xFFFF)

    mbap = struct.pack('>HHHB', transaction_id, 0, len(pdu) + 1, unit_id)
    return mbap + pdu


def _handle_client(conn: socket.socket, addr):
    """Thread por conexão TCP."""
    print(f"[Modbus] Cliente conectado: {addr}")
    try:
        while True:
            data = conn.recv(256)
            if not data:
                break
            regs = _get_registers()
            response = _handle_request(data, regs)
            if response:
                conn.sendall(response)
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        conn.close()
        print(f"[Modbus] Cliente desconectado: {addr}")


# ── Loop de simulação ─────────────────────────────────────────────────────────
def _sim_loop():
    while True:
        time.sleep(2)
        with _lock:
            d = _s["degrad"]
            if _s["running"]:
                spike = 0.4 * d if random.random() < 0.05 else 0.0
                _s["temp"]  = _clamp(_s["temp"]  + _rnd(0.18) + 0.02 * d, 28, 98)
                _s["vib_x"] = _clamp(_s["vib_x"] + _rnd(0.03) + 0.015 * d + spike, 0.02, 6.0)
                _s["vib_y"] = _clamp(_s["vib_y"] + _rnd(0.03) + 0.014 * d + spike * 0.9, 0.02, 6.0)
                _s["vib_z"] = _clamp(_s["vib_z"] + _rnd(0.04) + 0.018 * d + spike * 1.1, 0.02, 6.0)
                _s["rpm"]   = _clamp(_s["rpm"]   + _rnd(3), 0, 1800)
                _s["horas"] = round(_s["horas"]  + 0.000556, 3)
                _s["degrad"]= _clamp(d + 0.00005, 0, 1.0)
            rms = _rms(_s["vib_x"], _s["vib_y"], _s["vib_z"])
            sc  = _score(_s["temp"], rms)
            snap = (round(_s["temp"], 1), round(rms, 2), int(_s["rpm"]), sc, round(d * 100, 1))

        print(
            f"[Sim] T:{snap[0]}°C  RMS:{snap[1]:.2f}g"
            f"  RPM:{snap[2]}  Score:{snap[3]}  Degrad:{snap[4]}%"
        )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SmartMotor Modbus TCP Simulator")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5020)
    args = parser.parse_args()

    # Thread de simulação
    threading.Thread(target=_sim_loop, daemon=True).start()

    # Servidor TCP
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(5)

    print(f"🔌 SmartMotor Modbus Simulator — {args.host}:{args.port}")
    print(f"   Registradores iniciais: {_get_registers()}")
    print(f"   Ctrl+C para parar\n")

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(target=_handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n🛑 Simulador encerrado")
    finally:
        server.close()


if __name__ == "__main__":
    main()