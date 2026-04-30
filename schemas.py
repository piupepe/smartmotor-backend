from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ── Sensor ───────────────────────────────────────────────────────────────────

class SensorData(BaseModel):
    machine_id:     int   = Field(..., ge=0, description="ID da máquina")
    temperature:    float = Field(..., ge=-50, le=200, description="Temperatura °C")
    vibration_x:    float = Field(..., ge=0)
    vibration_y:    float = Field(..., ge=0)
    vibration_z:    float = Field(..., ge=0)
    vibration_rms:  Optional[float] = Field(None, ge=0)
    status_motor:   Optional[int]   = None
    frequencia_hz:  Optional[float] = None
    rpm:            Optional[float] = None
    saude_score:    Optional[int]   = Field(None, ge=0, le=100)
    codigo_falha:   Optional[int]   = None
    horas_operacao: Optional[float] = None
    timestamp:      Optional[datetime] = None


class SensorDataResponse(BaseModel):
    id:             int
    machine_id:     int
    temperature:    float
    vibration_x:    float
    vibration_y:    float
    vibration_z:    float
    vibration_rms:  Optional[float] = None
    status_motor:   Optional[int]   = None
    frequencia_hz:  Optional[float] = None
    rpm:            Optional[float] = None
    saude_score:    Optional[int]   = None
    codigo_falha:   Optional[int]   = None
    horas_operacao: Optional[float] = None
    timestamp:      datetime

    model_config = {"from_attributes": True}


# ── Alertas ──────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    machine_id: int = Field(..., ge=0)
    alert_type: str = Field(..., description="vibration | temperature | fault")
    severity:   str = Field(..., description="warning | critical")
    message:    str


class AlertResponse(BaseModel):
    id:         int
    machine_id: int
    alert_type: str
    severity:   str
    message:    str
    timestamp:  datetime
    resolved:   bool

    model_config = {"from_attributes": True}


# ── Genérico ─────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str