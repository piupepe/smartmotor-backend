"""Production entry point for the physical PLC: uvicorn main_tm221:app."""
import asyncio
import hmac
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()
from services.edge_link import EdgeLink, env, frontend_payload
from services.auth import router as auth_router, session_user

edge = EdgeLink()

@asynccontextmanager
async def lifespan(app):
    edge.start()
    yield
    edge.close()

app = FastAPI(title='SmartMotor TM221 físico', version='3.0.0', lifespan=lifespan)
app.include_router(auth_router)
app.add_middleware(CORSMiddleware,
    # .strip() por origem: um espaco depois da virgula no painel do Render derruba
    # o CORS sem nenhuma mensagem de erro no log.
    allow_origins=[o.strip() for o in env('CORS_ORIGINS', 'https://smartmotor-frontend.vercel.app,http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()],
    # Previews e dominio de producao do Vercel mudam de nome; o regex cobre todos os
    # projetos "smartmotor*". CORS nao e a barreira de seguranca aqui — o Bearer token e.
    allow_origin_regex=env('CORS_ORIGIN_REGEX', r'https://smartmotor[a-z0-9-]*\.vercel\.app'),
    allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])

# Esquema de seguranca declarado (e nao um Header comum): o Swagger em /docs ignora
# parametros de cabecalho chamados "Authorization" pela especificacao OpenAPI, entao
# ali o token nunca era enviado e toda chamada dava 401. Com HTTPBearer, o /docs ganha
# o botao "Authorize" e o token vai em todas as requisicoes.
bearer = HTTPBearer(auto_error=False, description='MOTOR_API_TOKEN configurado no Render')

def authorize(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
    token = env('MOTOR_API_TOKEN')
    # Keep the service credential for integrations; dashboard uses user sessions.
    if cred and token and hmac.compare_digest(cred.credentials.encode(), token.encode()):
        return
    if not env('AUTH_DB_PATH'):
        raise HTTPException(401, 'Entre com uma conta cadastrada no servidor')
    user = session_user(cred)
    if user['role'] not in ('admin', 'operador'):
        raise HTTPException(403, 'Perfil sem permissão para operar o motor')

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
    # broker e topico entram aqui de proposito: quando o ESP32 publica e o backend nao
    # recebe, a causa quase sempre e cluster ou topico diferente, e sem isso so resta adivinhar.
    return {'status': 'ok', 'mqtt_connected': edge.connected,
            'telemetry_fresh': edge.snapshot() is not None, 'configuration': edge.error,
            'broker': env('MQTT_HOST'), 'porta': env('MQTT_PORT', '8883'),
            'usuario': env('MQTT_USER'),
            'topico_telemetria': edge.topic + '/telemetry',
            # o que realmente trafega no cluster: se o ESP32 estiver publicando em
            # outro topico, ele aparece aqui e o diagnostico acaba em uma requisicao.
            'topicos_observados': sorted(edge.topics_seen),
            'ultima_telemetria_ha_s': (None if not edge.received_at
                                       else round(time.monotonic() - edge.received_at, 1)),
            'mensagens_recebidas': edge.received_count,
            'mensagens_descartadas': edge.rejected_count}

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
