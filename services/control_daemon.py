"""
services/control_daemon.py
"""
import time
import threading

from services.control_engine import PIDController
from services.modbus_reader  import read_smartmotor_registers

# PID singleton — compartilhado com control.py
pid = PIDController()

_lock       = threading.Lock()
_running    = False
_setpoint   = 1200.0
_command    = 0.0
_last_data  = None


def _control_loop():
    global _command, _last_data

    print("[Daemon] Control loop iniciado")

    while True:
        with _lock:
            if not _running:
                break
            sp = _setpoint

        t_start = time.perf_counter()
        data = read_smartmotor_registers()

        if not data:
            print("[Daemon] ⚠️  Sem dados Modbus — aguardando...")
            time.sleep(1.0)
            continue

        measured = data["rpm"]
        dt = max(time.perf_counter() - t_start, 0.01)
        cmd = pid.compute(sp, measured, dt=dt)

        with _lock:
            _command   = cmd
            _last_data = data

        print(f"[Daemon] SP:{sp:.0f}  RPM:{measured:.0f}  CMD:{cmd:.0f}  dt:{dt*1000:.1f}ms")

        elapsed = time.perf_counter() - t_start
        time.sleep(max(0.0, 1.0 - elapsed))

    print("[Daemon] Control loop encerrado")


def start_control_loop():
    global _running
    with _lock:
        if _running:
            return
        _running = True
    pid.reset()
    t = threading.Thread(target=_control_loop, daemon=True, name="control-loop")
    t.start()
    print("[Daemon] ✅ Thread iniciada")


def stop_control_loop():
    global _running
    with _lock:
        _running = False
    pid.reset()
    print("[Daemon] 🛑 Sinalizado para parar")


def set_setpoint(value: float):
    global _setpoint
    value = max(0.0, min(1800.0, float(value)))
    with _lock:
        _setpoint = value


def get_status() -> dict:
    with _lock:
        return {
            "running":      _running,
            "setpoint_rpm": _setpoint,
            "command_rpm":  round(_command, 1),
            "last_reading": _last_data,
        }