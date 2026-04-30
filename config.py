"""
config.py — Configuração centralizada do SmartMotor Backend

Todas as variáveis de ambiente ficam aqui.
Crie um arquivo .env na raiz do backend com os valores desejados.

Uso:
    from config import settings
    print(settings.MODBUS_HOST)
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # ── Modbus ────────────────────────────────────────────────────────────────
    MODBUS_HOST:      str = field(default_factory=lambda: os.getenv("MODBUS_HOST", "127.0.0.1"))
    MODBUS_PORT:      int = field(default_factory=lambda: int(os.getenv("MODBUS_PORT", "502")))
    MODBUS_DEVICE_ID: int = field(default_factory=lambda: int(os.getenv("MODBUS_DEVICE_ID", "1")))
    MODBUS_TIMEOUT_S: int = field(default_factory=lambda: int(os.getenv("MODBUS_TIMEOUT_S", "3")))

    # ── Banco de dados ────────────────────────────────────────────────────────
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./smartmotor.db"))

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list = field(default_factory=lambda: [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ])

    # ── Controle PID ─────────────────────────────────────────────────────────
    PID_KP:          float = field(default_factory=lambda: float(os.getenv("PID_KP",  "0.8")))
    PID_KI:          float = field(default_factory=lambda: float(os.getenv("PID_KI",  "0.2")))
    PID_KD:          float = field(default_factory=lambda: float(os.getenv("PID_KD",  "0.05")))
    PID_DEFAULT_SP:  float = field(default_factory=lambda: float(os.getenv("PID_DEFAULT_SP", "1200.0")))
    PID_MAX_RPM:     float = field(default_factory=lambda: float(os.getenv("PID_MAX_RPM",    "1800.0")))

    # ── WebSocket broadcaster ─────────────────────────────────────────────────
    WS_INTERVAL_S: float = field(default_factory=lambda: float(os.getenv("WS_INTERVAL_S", "2.0")))

    # ── Limites de alerta ─────────────────────────────────────────────────────
    TEMP_WARNING:  float = field(default_factory=lambda: float(os.getenv("TEMP_WARNING",  "75.0")))
    TEMP_CRITICAL: float = field(default_factory=lambda: float(os.getenv("TEMP_CRITICAL", "90.0")))
    VIB_WARNING:   float = field(default_factory=lambda: float(os.getenv("VIB_WARNING",   "4.5")))
    VIB_CRITICAL:  float = field(default_factory=lambda: float(os.getenv("VIB_CRITICAL",  "7.1")))


settings = Settings()
