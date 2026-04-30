# services/control.py
import time
from typing import Optional, Dict, Any

from services.modbus_reader  import read_smartmotor_registers
from services.control_daemon import pid   # PID singleton compartilhado


def control_step(setpoint_rpm: float) -> Optional[Dict[str, Any]]:
    t_start = time.perf_counter()

    data = read_smartmotor_registers()
    if not data:
        return None

    measured = data["rpm"]
    dt = max(time.perf_counter() - t_start, 0.01)
    command = pid.compute(setpoint_rpm, measured, dt=dt)

    return {
        "setpoint":  setpoint_rpm,
        "measured":  round(measured, 1),
        "command":   round(command,  1),
        "error":     round(setpoint_rpm - measured, 1),
        "dt_ms":     round(dt * 1000, 2),
        **{k: v for k, v in data.items() if k != "rpm"},
    }