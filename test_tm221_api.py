import json
import time
from types import SimpleNamespace
from fastapi.testclient import TestClient
from main_tm221 import app, edge
from services.edge_link import EdgeLink, frontend_payload

def test_auth_and_bounds(monkeypatch):
    monkeypatch.setenv('MOTOR_API_TOKEN', 'test-only')
    client = TestClient(app)
    assert client.post('/motor/start').status_code == 401
    assert client.post('/motor/start?freq=100', headers={'Authorization':'Bearer test-only'}).status_code == 422
    assert client.post('/motor/start', headers={'Authorization':'Bearer test-only'}).status_code == 503

def test_accepted_is_not_motor_running(monkeypatch):
    monkeypatch.setenv('MOTOR_API_TOKEN', 'test-only')
    monkeypatch.setattr(edge, 'command', lambda *args, **kwargs: {'status':'accepted', 'motor_confirmed':False})
    r = TestClient(app).post('/motor/start', headers={'Authorization':'Bearer test-only'})
    assert r.status_code == 202 and r.json()['motor_confirmed'] is False

def test_no_fallback_data():
    data = frontend_payload(None)
    assert data['source'] == 'offline' and data['corrente'] is None and data['running'] is None

def test_websocket_distinguishes_offline_from_fresh_telemetry(monkeypatch):
    telemetry = {
        'source':'tm221', 'boot':'test-boot', 'uptime_ms':1234,
        'temperatura':42.5, 'vibration_x':0.1, 'vibration_y':0.2,
        'vibration_z':0.3, 'vibration_rms':0.25, 'freq_real':30.0,
        'freq_setpoint':30.0, 'rpm':900, 'corrente':1.2,
        'tensao_saida':220, 'saude_score':88, 'plc_ok':True,
        'cfw500_ok':True, 'commissioned':True, 'running':True, 'estado':'RODANDO',
    }
    monkeypatch.setattr(edge, 'snapshot', lambda: None)
    with TestClient(app) as client:
        with client.websocket_connect('/ws') as ws:
            offline = ws.receive_json()
            assert offline['source'] == 'offline'
            assert offline['temp'] is None and offline['corrente'] is None

            monkeypatch.setattr(edge, 'snapshot', lambda: telemetry)
            live = ws.receive_json()
            assert live['source'] == 'tm221'
            assert live['temp'] == 42.5 and live['vibRMS'] == 0.25
            assert live['freq'] == 30.0 and live['corrente'] == 1.2
            assert live['plc_ok'] is True and live['cfw500_ok'] is True
            assert live['commissioned'] is True

def test_stale_retained_and_duplicate_rejected():
    link = EdgeLink(); link.connected = True
    raw = {'source':'tm221', 'boot':'test', 'uptime_ms':123, 'corrente':1.2}
    msg = SimpleNamespace(topic=link.topic+'/telemetry', payload=json.dumps(raw).encode(), retain=True)
    link.on_message(None,None,msg); assert link.snapshot() is None
    msg.retain = False; link.on_message(None,None,msg); assert link.snapshot()['corrente'] == 1.2
    link.received_at -= 5
    link.on_message(None,None,msg)
    assert link.snapshot() is None

def test_start_interlock():
    link = EdgeLink(); link.connected = True; link.latest = {'boot':'test', 'uptime_ms':123, 'plc_ok':False}
    link.received_at = time.monotonic()
    try: link.command('start')
    except ValueError: pass
    else: raise AssertionError('offline PLC accepted START')
