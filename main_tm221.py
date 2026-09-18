"""Production entry point for the physical PLC: uvicorn main_tm221:app."""
import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
from services.edge_link import EdgeLink, frontend_payload

edge = EdgeLink()

@asynccontextmanager
async def lifespan(app):
    edge.start()
    yield
    edge.close()

app = FastAPI(title='SmartMotor TM221 físico', version='3.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', 'https://smartmotor-frontend.vercel.app,http://localhost:5173,http://127.0.0.1:5173').split(','),
    allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])

def authorize(authorization: str = Header(default='')):
    token = os.getenv('MOTOR_API_TOKEN', '')
    if not token:
        raise HTTPException(503, 'Controle remoto ainda não configurado')
    if not hmac.compare_digest(authorization, 'Bearer ' + token):
        raise HTTPException(401, 'Chave de operação inválida')

def send(action, **parameters):
    try:
        return edge.command(action, **parameters)
    except ConnectionError as e:
        raise HTTPException(503, str(e)) from e
    except TimeoutError as e:
        raise HTTPException(504, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e

@app.get('/')
def home():
    return {'status': 'online', 'service': 'SmartMotor TM221', 'version': '3.0.0'}

@app.get('/health')
def health():
    return {'status': 'ok', 'mqtt_connected': edge.connected,
            'telemetry_fresh': edge.snapshot() is not None, 'configuration': edge.error}

@app.get('/motor/status')
def motor_status():
    return frontend_payload(edge.snapshot())

@app.post('/motor/start', dependencies=[Depends(authorize)], status_code=202)
def start(freq: float = Query(30, ge=10, le=60), ramp: int = Query(10, ge=1, le=30)):
    return send('start', freq=freq, ramp=ramp)

@app.post('/motor/stop', dependencies=[Depends(authorize)], status_code=202)
def stop():
    return send('stop')

@app.post('/motor/reset', dependencies=[Depends(authorize)], status_code=202)
def reset():
    return send('reset')

@app.post('/motor/manutencao', dependencies=[Depends(authorize)], status_code=202)
def maintenance(ativo: bool):
    return send('maintenance', value=int(ativo))

@app.post('/motor/freq', dependencies=[Depends(authorize)], status_code=202)
def frequency(value: float = Query(..., ge=10, le=60)):
    return send('freq', value=value)

@app.post('/motor/ramp', dependencies=[Depends(authorize)], status_code=202)
def ramp(value: int = Query(..., ge=1, le=30)):
    return send('ramp', value=value)

@app.websocket('/ws')
async def websocket(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(frontend_payload(edge.snapshot()))
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        return
