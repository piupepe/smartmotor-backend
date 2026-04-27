from pydantic import BaseModel, Field
from datetime import datetime


class SensorData(BaseModel):
    machine_id: int = Field(..., ge=0, description="ID da máquina")
    temperature: float = Field(..., ge=-50, le=200, description="Temperatura em °C")
    vibration_x: float = Field(..., ge=0, description="Vibração no eixo X")
    vibration_y: float = Field(..., ge=0, description="Vibração no eixo Y")
    vibration_z: float = Field(..., ge=0, description="Vibração no eixo Z")
    timestamp: datetime = Field(..., description="Data e hora da leitura")


class SensorDataResponse(BaseModel):
    id: int
    machine_id: int
    temperature: float
    vibration_x: float
    vibration_y: float
    vibration_z: float
    timestamp: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


class AlertResponse(BaseModel):
    id: int
    machine_id: int
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
    resolved: bool

    model_config = {"from_attributes": True}