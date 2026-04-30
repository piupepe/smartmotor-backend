"""
main.py — SmartMotor Backend
"""
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from services.mqtt_reader    import start_mqtt_client, stop_mqtt_client
from routes.sensor import router as sensor_router
from routes.alerts import router as alerts_router
from routes.ws     import router as ws_router, ws_broadcaster

# Só importa controle/modbus se não estiver no Render
RENDER = os.getenv("RENDER", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔥 SmartMotor iniciando...")
    Base.metadata.create_all(bind=engine)

    # MQTT — sempre ativo (ESP32 via HiveMQ)
    start_mqtt_client()

    # Daemon de controle + Modbus — só local
    if not RENDER:
        from services.control_daemon import start_control_loop
        start_control_loop()

    task = asyncio.create_task(ws_broadcaster())
    yield

    task.cancel()
    stop_mqtt_client()

    if not RENDER:
        from services.control_daemon import stop_control_loop
        from services.modbus_reader  import close_connection
        stop_control_loop()
        close_connection()

    print("🛑 SmartMotor encerrado")


app = FastAPI(
    title="SmartMotor Backend",
    version="1.0.0",
    description="Monitoramento preditivo — SM-001",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensor_router)
app.include_router(alerts_router)
app.include_router(ws_router)


@app.get("/")
def home():
    return {"status": "online", "service": "SmartMotor v1.0", "render": RENDER}


@app.get("/health")
def health():
    from services.mqtt_reader import is_connected, get_latest
    return {
        "status": "ok",
        "mqtt_connected": is_connected(),
        "mqtt_latest":    get_latest() is not None,
        "render_mode":    RENDER,
    }


@app.get("/mqtt/status")
def mqtt_status():
    from services.mqtt_reader import is_connected, get_latest
    return {"connected": is_connected(), "latest": get_latest()}


@app.get("/modbus/test")
def modbus_test():
    if RENDER:
        return {"status": "disabled", "message": "Modbus não disponível no Render"}
    from services.modbus_reader import read_smartmotor_registers
    data = read_smartmotor_registers()
    if not data:
        return {"status": "error", "message": "Modbus indisponível"}
    return {"status": "ok", "data": data}


@app.get("/control/status")
def control_status():
    if RENDER:
        return {"status": "disabled", "message": "Controle não disponível no Render"}
    from services.control_daemon import get_status
    return get_status()


@app.post("/control/setpoint")
def change_setpoint(value: float = Query(..., ge=0, le=1800)):
    if RENDER:
        return {"status": "disabled"}
    from services.control_daemon import set_setpoint
    set_setpoint(value)
    return {"status": "ok", "setpoint_rpm": value}


@app.get("/debug/routes")
def list_routes():
    return sorted(r.path for r in app.routes)
