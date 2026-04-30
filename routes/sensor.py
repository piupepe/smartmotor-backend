import math
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from config import settings
from dependencies import get_db
from models import SensorReading, Alert
from schemas import SensorDataResponse
from services.modbus_reader import read_smartmotor_registers

router = APIRouter(tags=["sensors"])

LIMITS = {
    "temperature":   {"warning": settings.TEMP_WARNING,  "critical": settings.TEMP_CRITICAL},
    "vibration_rms": {"warning": settings.VIB_WARNING,   "critical": settings.VIB_CRITICAL},
}


def _maybe_alert(db: Session, machine_id: int, field: str, value: float) -> None:
    """Cria alerta se value ultrapassar os limites definidos."""
    lim = LIMITS.get(field, {})
    if value >= lim.get("critical", float("inf")):
        severity = "critical"
    elif value >= lim.get("warning", float("inf")):
        severity = "warning"
    else:
        return
    db.add(Alert(
        machine_id=machine_id,
        alert_type=field,
        severity=severity,
        message=f"{field} {severity}: {value:.2f} (limite {lim[severity]})",
        resolved=False,
        timestamp=datetime.now(timezone.utc),
    ))


@router.get("/status")
def status():
    return {"status": "online", "service": "smartmotor-backend"}


@router.post("/modbus/collect", response_model=SensorDataResponse, status_code=201)
def collect_modbus_data(machine_id: int = Query(1, ge=1), db: Session = Depends(get_db)):
    """Dispara leitura ao vivo do Modbus, persiste e gera alertas automáticos."""
    data = read_smartmotor_registers()
    if data is None:
        raise HTTPException(status_code=503, detail="Modbus indisponível")

    vib_rms = data.get("vibration_rms") or round(
        math.sqrt(
            (data["vibration_x"] ** 2 + data["vibration_y"] ** 2 + data["vibration_z"] ** 2) / 3
        ),
        4,
    )

    reading = SensorReading(
        machine_id=machine_id,
        temperature=data["temperatura"],      # chave Modbus → coluna ORM
        vibration_x=data["vibration_x"],
        vibration_y=data["vibration_y"],
        vibration_z=data["vibration_z"],
        vibration_rms=vib_rms,
        status_motor=data["status_motor"],
        frequencia_hz=data["frequencia_hz"],
        rpm=data["rpm"],
        saude_score=data["saude_score"],
        codigo_falha=data["codigo_falha"],
        horas_operacao=data["horas_operacao"],
        timestamp=datetime.now(timezone.utc),
    )
    db.add(reading)
    db.flush()  # gera id sem commitar

    _maybe_alert(db, machine_id, "temperature",   data["temperatura"])
    _maybe_alert(db, machine_id, "vibration_rms", vib_rms)

    db.commit()
    db.refresh(reading)
    return reading


@router.get("/sensor-data", response_model=List[SensorDataResponse])
def list_sensor_data(
    machine_id: int = Query(None),
    limit:      int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(SensorReading).order_by(desc(SensorReading.id)).limit(limit)
    if machine_id is not None:
        stmt = stmt.where(SensorReading.machine_id == machine_id)
    return db.execute(stmt).scalars().all()


@router.get("/machines/{machine_id}/latest", response_model=SensorDataResponse)
def get_latest_sensor_data(machine_id: int, db: Session = Depends(get_db)):
    reading = db.execute(
        select(SensorReading)
        .where(SensorReading.machine_id == machine_id)
        .order_by(desc(SensorReading.id))
    ).scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="Nenhuma leitura encontrada para esta máquina")
    return reading