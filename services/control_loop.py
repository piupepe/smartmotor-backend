from services.control_engine import PIDController
from services.modbus_reader import read_smartmotor_registers

pid = PIDController()

command_rpm = 0


def control_step(setpoint_rpm):
    global command_rpm

    data = read_smartmotor_registers()
    if not data:
        return None

    measured_rpm = data["rpm"]

    dt = 1.0

    correction = pid.compute(setpoint_rpm, measured_rpm, dt)

    command_rpm += correction

    # limites de segurança industrial
    command_rpm = max(0, min(1800, command_rpm))

    return {
        "setpoint": setpoint_rpm,
        "measured": measured_rpm,
        "command": command_rpm,
        "error": setpoint_rpm - measured_rpm
    }