from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id               = Column(Integer, primary_key=True, index=True)
    machine_id       = Column(Integer, nullable=False, index=True)
    temperature      = Column(Float,   nullable=False)
    vibration_x      = Column(Float,   nullable=False)
    vibration_y      = Column(Float,   nullable=False)
    vibration_z      = Column(Float,   nullable=False)
    vibration_rms    = Column(Float,   nullable=True)
    status_motor     = Column(Integer, nullable=True)
    frequencia_hz    = Column(Float,   nullable=True)
    rpm              = Column(Float,   nullable=True)
    saude_score      = Column(Integer, nullable=True)
    codigo_falha     = Column(Integer, nullable=True)
    horas_operacao   = Column(Float,   nullable=True)
    timestamp        = Column(DateTime, nullable=False,
                              default=lambda: datetime.now(timezone.utc))


class Alert(Base):
    __tablename__ = "alerts"

    id           = Column(Integer,  primary_key=True, index=True)
    machine_id   = Column(Integer,  nullable=False, index=True)
    alert_type   = Column(String,   nullable=False)          # ex: "vibration", "temperature"
    severity     = Column(String,   nullable=False)          # "warning" | "critical"
    message      = Column(String,   nullable=False)
    resolved     = Column(Boolean,  nullable=False, default=False)
    timestamp    = Column(DateTime, nullable=False,
                          default=lambda: datetime.now(timezone.utc))