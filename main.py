"""
main.py — com WebSocket broadcaster no lifespan
"""
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from services.modbus_reader  import read_smartmotor_registers, close_connection
from services.control        import control_step
from services.control_daemon import start_control_loop, stop_control_loop, set_setpoint, get_status, pid
from routes.sensor import router as sensor_router
from routes.alerts import router as alerts_router
from routes.ws     import router as ws_router, ws_broadcaster

import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔥 SmartMotor iniciando...")
    Base.metadata.create_all(bind=engine)
    start_control_loop()
    # Inicia o broadcaster WebSocket como task assíncrona
    task = asyncio.create_task(ws_broadcaster())
    yield
    task.cancel()
    stop_control_loop()
    close_connection()
    print("🛑 SmartMotor encerrado")


app = FastAPI(
    title="SmartMotor Backend",
    version="1.0.0",
    description="Monitoramento preditivo de motores trifásicos — SM-001",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://smartmotor-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensor_router)
app.include_router(alerts_router)
app.include_router(ws_router)


@app.get("/", tags=["health"])
def home():
    return {"status": "online", "service": "SmartMotor Backend v1.0"}

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", **get_status()}

@app.get("/modbus/test", tags=["modbus"])
def modbus_test():
    data = read_smartmotor_registers()
    if not data:
        return {"status": "error", "message": "Falha ao ler dados do Modbus"}
    return {"status": "ok", "data": data}

@app.get("/control/status", tags=["control"])
def control_status():
    return get_status()

@app.post("/control/setpoint", tags=["control"])
def change_setpoint(value: float = Query(..., ge=0, le=1800)):
    set_setpoint(value)
    return {"status": "ok", "setpoint_rpm": value}

@app.get("/control/run", tags=["control"])
def run_control_step(setpoint: float = Query(1200, ge=0, le=1800)):
    if get_status()["running"]:
        return {"status": "warning", "message": "Daemon ativo — use /control/status"}
    result = control_step(setpoint)
    if not result:
        return {"status": "error", "message": "Sem dados Modbus"}
    return {"status": "ok", "data": result}

@app.post("/control/tune", tags=["control"])
def tune_pid(
    kp: float = Query(None, ge=0),
    ki: float = Query(None, ge=0),
    kd: float = Query(None, ge=0),
):
    pid.tune(kp=kp, ki=ki, kd=kd)
    return {"status": "ok", "params": pid.params()}

@app.get("/debug/routes", tags=["debug"])
def list_routes():
    return sorted(route.path for route in app.routes)