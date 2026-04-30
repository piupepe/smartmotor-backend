from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import List, Optional

from dependencies import get_db
from models import Alert
from schemas import AlertCreate, AlertResponse, MessageResponse

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=List[AlertResponse])
def list_alerts(
    machine_id: Optional[int]  = Query(None),
    resolved:   Optional[bool] = Query(None, description="True=resolvidos, False=ativos"),
    limit:      int            = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(Alert).order_by(desc(Alert.id)).limit(limit)
    if machine_id is not None:
        stmt = stmt.where(Alert.machine_id == machine_id)
    if resolved is not None:
        stmt = stmt.where(Alert.resolved == resolved)
    return db.execute(stmt).scalars().all()


@router.post("/alerts", response_model=AlertResponse, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    alert = Alert(**payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
def get_alert_by_id(alert_id: int, db: Session = Depends(get_db)):
    alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return alert


@router.get("/machines/{machine_id}/alerts", response_model=List[AlertResponse])
def get_alerts_by_machine(
    machine_id: int,
    resolved:   Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(Alert).where(Alert.machine_id == machine_id).order_by(desc(Alert.id))
    if resolved is not None:
        stmt = stmt.where(Alert.resolved == resolved)
    return db.execute(stmt).scalars().all()


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    alert.resolved = True
    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/alerts/{alert_id}", response_model=MessageResponse)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    db.delete(alert)
    db.commit()
    return {"message": f"Alerta {alert_id} deletado com sucesso"}