from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from models import Base

from services.modbus_reader import read_smartmotor_registers
from services.control_loop import control_step

from routes.sensor import router as sensor_router
from routes.alerts import router as alerts_router

# -------------------------------------------------
# INIT DB
# -------------------------------------------------
Base.metadata.create_all(bind=engine)

# -------------------------------------------------
# APP
# -------------------------------------------------
app = FastAPI(
    title="SmartMotor Backend",
    version="1.0.0",
    description="Sistema de monitoramento e controle industrial"
)

# -------------------------------------------------
# CORS (modo dev estável)
# -------------------------------------------------
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://smartmotor-frontend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# DEBUG (garante que você está rodando o arquivo certo)
# -------------------------------------------------
print("🔥 SmartMotor backend carregado com sucesso")

# -------------------------------------------------
# ROUTES BASE
# -------------------------------------------------
@app.get("/")
def home():
    return {"message": "SmartMotor backend online"}

# -------------------------------------------------
# MODBUS TEST
# -------------------------------------------------
@app.get("/modbus/test")
def modbus_test():
    data = read_smartmotor_registers()

    if not data:
        return {
            "status": "error",
            "message": "Falha ao ler dados do Modbus"
        }

    return {
        "status": "ok",
        "data": data
    }

# -------------------------------------------------
# CONTROL LOOP (PID / lógica futura)
# -------------------------------------------------
@app.get("/control/run")
def run_control(setpoint: int = Query(1200)):
    result = control_step(setpoint)

    return {
        "status": "ok",
        "setpoint": setpoint,
        "data": result
    }

# -------------------------------------------------
# ROUTERS
# -------------------------------------------------
app.include_router(sensor_router)
app.include_router(alerts_router)

# -------------------------------------------------
# DEBUG ROTAS (opcional mas MUITO útil)
# -------------------------------------------------
@app.get("/debug/routes")
def list_routes():
    return [route.path for route in app.routes]