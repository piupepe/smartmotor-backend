from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import SessionLocal
from models import Alert
from schemas import AlertResponse, MessageResponse

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(db: Session = Depends(get_db)):
    stmt = select(Alert).order_by(Alert.id.desc())
    alerts = db.execute(stmt).scalars().all()
    return alerts


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
def get_alert_by_id(alert_id: int, db: Session = Depends(get_db)):
    stmt = select(Alert).where(Alert.id == alert_id)
    alert = db.execute(stmt).scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    return alert


@router.get("/machines/{machine_id}/alerts", response_model=list[AlertResponse])
def get_alerts_by_machine(machine_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(Alert)
        .where(Alert.machine_id == machine_id)
        .order_by(Alert.id.desc())
    )
    alerts = db.execute(stmt).scalars().all()
    return alerts


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    stmt = select(Alert).where(Alert.id == alert_id)
    alert = db.execute(stmt).scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    alert.resolved = True
    db.commit()
    db.refresh(alert)

    return alert


@router.delete("/alerts/{alert_id}", response_model=MessageResponse)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    stmt = select(Alert).where(Alert.id == alert_id)
    alert = db.execute(stmt).scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    db.delete(alert)
    db.commit()

    return {"message": f"Alerta {alert_id} deletado com sucesso"}