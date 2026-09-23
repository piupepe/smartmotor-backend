import time
import pytest
from fastapi.testclient import TestClient
from main_tm221 import app, edge
from services.auth import NewUser, create_user, database

@pytest.fixture
def auth(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTH_DB_PATH', str(tmp_path / 'auth.sqlite3'))
    monkeypatch.setenv('MOTOR_API_TOKEN', 'integration-only')
    admin = create_user(NewUser(username='admin', name='Administrador', password='test-password', role='admin'))
    calls = []
    def command(action, **parameters):
        calls.append((action, parameters))
        return {'status': 'accepted'}
    monkeypatch.setattr(edge, 'command', command)
    return TestClient(app), calls, admin

def sign_in(client, username='admin'):
    result = client.post('/auth/login', json={'username': username, 'password': 'test-password'})
    assert result.status_code == 200
    assert 'password' not in result.json()['user']
    return {'Authorization': 'Bearer ' + result.json()['access_token']}

def test_logged_in_user_commands_and_logout(auth):
    client, calls, _ = auth
    assert client.post('/motor/start').status_code == 401
    assert client.post('/motor/start', headers={'Authorization': 'Bearer forged-local-user'}).status_code == 401
    headers = sign_in(client)
    for path in ('start', 'stop', 'reset', 'freq?value=35', 'ramp?value=10', 'manutencao?ativo=true'):
        assert client.post('/motor/' + path, headers=headers).status_code == 202
    assert len(calls) == 6
    assert client.get('/auth/me', headers=headers).status_code == 200
    assert client.post('/auth/logout', headers=headers).status_code == 200
    assert client.post('/motor/start', headers=headers).status_code == 401
    assert len(calls) == 6

def test_roles_disable_and_expiry(auth):
    client, calls, admin = auth
    headers = sign_in(client)
    created = client.post('/auth/users', headers=headers, json={'username':'operator', 'name':'Operador', 'password':'test-password'})
    assert created.status_code == 201
    operator = sign_in(client, 'operator')
    assert client.get('/auth/users', headers=operator).status_code == 403
    assert client.post('/motor/freq?value=32', headers=operator).status_code == 202
    assert client.post('/auth/users/'+admin['id']+'/active?active=false', headers=headers).status_code == 409
    assert client.post('/auth/users/'+created.json()['id']+'/active?active=false', headers=headers).status_code == 200
    assert client.post('/motor/start', headers=operator).status_code == 401
    with database() as db:
        db.execute('UPDATE sessions SET expires=?', (time.time()-1,))
    assert client.post('/motor/start', headers=headers).status_code == 401
    assert len(calls) == 1

def test_invalid_password_rate_limit_and_hashed_storage(auth):
    client, _, _ = auth
    for _ in range(5):
        assert client.post('/auth/login', json={'username':'admin','password':'wrong'}).status_code == 401
    assert client.post('/auth/login', json={'username':'admin','password':'wrong'}).status_code == 429
    with database() as db:
        assert 'test-password' not in db.execute('SELECT password FROM users').fetchone()[0]

def test_user_removal_revokes_session(auth):
    client, _, _ = auth
    headers=sign_in(client)
    user=create_user(NewUser(username='operator',name='Operador',password='test-password'))
    operator=sign_in(client,'operator')
    assert client.post('/auth/users/'+user['id']+'/remove',headers=headers).status_code == 200
    assert client.post('/motor/start',headers=operator).status_code == 401
