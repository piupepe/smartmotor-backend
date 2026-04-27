from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone

from database import SessionLocal
from models import SensorReading, Alert
from services.modbus_reader import read_smartmotor_registers

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/status")
def status():
    return {
        "status": "online",
        "service": "smartmotor-backend",
        "module": "sensor-routes"
    }


@router.post("/modbus/collect")
def collect_modbus_data(db: Session = Depends(get_db)):
    data = read_smartmotor_registers()

    if data is None:
        raise HTTPException(status_code=500, detail="Falha ao ler dados do Modbus")

    reading = SensorReading(
        machine_id=1,
        temperature=data["temperatura"],
        vibration_x=data["vibration_x"],
        vibration_y=data["vibration_y"],
        vibration_z=data["vibration_z"],
        vibration_rms=data["vibration_rms"],
        status_motor=data["status_motor"],
        frequencia_hz=data["frequencia_hz"],
        rpm=data["rpm"],
        saude_score=data["saude_score"],
        codigo_falha=data["codigo_falha"],
        horas_operacao=data["horas_operacao"],
        timestamp=datetime.now(timezone.utc),
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    # Regras de alerta
    if data["temperatura"] >= 90 or data["vibration_rms"] >= 7.1:
        alert = Alert(
            machine_id=1,
            alert_type="critical_condition",
            severity="critical",
            message=f"Condição crítica: Temp={data['temperatura']}°C | VibRMS={data['vibration_rms']}g",
            resolved=False,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(alert)
        db.commit()

    elif data["temperatura"] >= 75 or data["vibration_rms"] >= 4.5:
        alert = Alert(
            machine_id=1,
            alert_type="warning_condition",
            severity="warning",
            message=f"Condição de alerta: Temp={data['temperatura']}°C | VibRMS={data['vibration_rms']}g",
            resolved=False,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(alert)
        db.commit()

    return {
        "status": "ok",
        "message": "Leitura coletada e salva com sucesso",
        "reading_id": reading.id
    }


@router.get("/sensor-data")
def list_sensor_data(db: Session = Depends(get_db)):
    stmt = select(SensorReading).order_by(SensorReading.id.desc())
    results = db.execute(stmt).scalars().all()
    return results


@router.get("/machines/{machine_id}/latest")
def get_latest_sensor_data(machine_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(SensorReading)
        .where(SensorReading.machine_id == machine_id)
        .order_by(SensorReading.id.desc())
    )
    reading = db.execute(stmt).scalars().first()

    if not reading:
        raise HTTPException(status_code=404, detail="Nenhuma leitura encontrada para esta máquina")

    return reading