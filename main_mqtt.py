"""
main.py — com MQTT + WebSocket broadcaster
"""
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from services.modbus_reader  import read_smartmotor_registers, close_connection
from services.mqtt_reader    import start_mqtt_client, stop_mqtt_client
from services.control_daemon import start_control_loop, stop_control_loop, set_setpoint, get_status, pid
from services.control        import control_step
from routes.sensor import router as sensor_router
from routes.alerts import router as alerts_router
from routes.ws     import router as ws_router, ws_broadcaster


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔥 SmartMotor iniciando...")
    Base.metadata.create_all(bind=engine)
    start_mqtt_client()          # ESP32 via HiveMQ
    start_control_loop()
    task = asyncio.create_task(ws_broadcaster())
    yield
    task.cancel()
    stop_control_loop()
    stop_mqtt_client()
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
    allow_origins=["*"],   # Vercel + dev local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensor_router)
app.include_router(alerts_router)
app.include_router(ws_router)


@app.get("/")
def home():
    return {"status": "online", "service": "SmartMotor v1.0"}

@app.get("/health")
def health():
    from services.mqtt_reader import is_connected as mqtt_ok
    return {
        "status":      "ok",
        "mqtt":        mqtt_ok(),
        "control":     get_status(),
    }

@app.get("/modbus/test")
def modbus_test():
    data = read_smartmotor_registers()
    if not data:
        return {"status": "error", "message": "Modbus indisponível"}
    return {"status": "ok", "data": data}

@app.get("/mqtt/status")
def mqtt_status():
    from services.mqtt_reader import is_connected, get_latest
    return {"connected": is_connected(), "latest": get_latest()}

@app.get("/control/status")
def control_status():
    return get_status()

@app.post("/control/setpoint")
def change_setpoint(value: float = Query(..., ge=0, le=1800)):
    set_setpoint(value)
    return {"status": "ok", "setpoint_rpm": value}

@app.post("/control/tune")
def tune_pid(
    kp: float = Query(None, ge=0),
    ki: float = Query(None, ge=0),
    kd: float = Query(None, ge=0),
):
    pid.tune(kp=kp, ki=ki, kd=kd)
    return {"status": "ok", "params": pid.params()}

@app.get("/debug/routes")
def list_routes():
    return sorted(r.path for r in app.routes)
