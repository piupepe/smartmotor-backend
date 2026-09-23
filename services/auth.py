"""Server-owned users and revocable sessions. AUTH_DB_PATH must be persistent."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

router = APIRouter(prefix='/auth', tags=['Autenticação'])
bearer = HTTPBearer(auto_error=False)

@contextmanager
def database():
    path = os.environ.get('AUTH_DB_PATH', '').strip()
    if not path:
        raise HTTPException(503, 'Cadastro de usuários ainda não configurado no servidor')
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE, name TEXT, password TEXT, role TEXT, active INTEGER)')
        db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT, expires REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY, count INTEGER, expires REAL)')
        yield db

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest

def public_user(row):
    return {k: bool(row[k]) if k == 'active' else row[k] for k in ('id', 'username', 'name', 'role', 'active')}

def session_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not cred:
        raise HTTPException(401, 'Entre novamente para enviar comandos')
    digest = hashlib.sha256(cred.credentials.encode()).hexdigest()
    with database() as db:
        row = db.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>? AND active=1', (digest, time.time())).fetchone()
    if not row:
        raise HTTPException(401, 'Sessão expirada ou acesso revogado. Entre novamente')
    return public_user(row)

def admin(user=Depends(session_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Somente administradores gerenciam usuários')
    return user

class Login(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=256)

class NewUser(Login):
    name: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=256)
    role: str = 'operador'

def create_user(data):
    if data.role not in ('admin', 'operador'):
        raise HTTPException(422, 'Perfil inválido')
    user = dict(id=secrets.token_hex(16), username=data.username.strip().lower(), name=data.name.strip(), role=data.role, active=True)
    if len(user['username']) < 3 or len(user['name']) < 3:
        raise HTTPException(422, 'Nome e usuário devem ter pelo menos 3 caracteres')
    with database() as db:
        try:
            db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (user['id'], user['username'], user['name'], password_hash(data.password), user['role'], 1))
        except sqlite3.IntegrityError as e:
            raise HTTPException(409, 'Usuário já cadastrado') from e
    return user

@router.post('/login')
def login(data: Login):
    username = data.username.strip().lower()
    # Reserve an attempt before password verification; persists across workers.
    with database() as db:
        db.execute('DELETE FROM login_attempts WHERE expires<=?', (time.time(),))
        db.execute('INSERT INTO login_attempts VALUES (?,1,?) ON CONFLICT(username) DO UPDATE SET count=count+1', (username, time.time()+60))
        count = db.execute('SELECT count FROM login_attempts WHERE username=?', (username,)).fetchone()[0]
    if count > 5:
        raise HTTPException(429, 'Muitas tentativas. Aguarde um minuto para tentar novamente')
    with database() as db:
        row = db.execute('SELECT * FROM users WHERE username=? AND active=1', (username,)).fetchone()
        stored = row['password'] if row else '00' * 16 + ':' + '00' * 32
        if not hmac.compare_digest(password_hash(data.password, stored.split(':')[0]), stored) or not row:
            raise HTTPException(401, 'Usuário ou senha inválidos')
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM login_attempts WHERE username=?', (username,))
        db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], time.time() + 8 * 3600))
        return {'access_token': token, 'user': public_user(row)}

@router.get('/me')
def me(user=Depends(session_user)):
    return user

@router.post('/logout')
def logout(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if cred:
        with database() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(cred.credentials.encode()).hexdigest(),))
    return {'status': 'ok'}

@router.get('/users')
def users(user=Depends(admin)):
    with database() as db:
        return [public_user(row) for row in db.execute('SELECT * FROM users ORDER BY name')]

@router.post('/users', status_code=201)
def add_user(data: NewUser, user=Depends(admin)):
    return create_user(data)

@router.post('/users/{user_id}/active')
def active(user_id: str, active: bool, user=Depends(admin)):
    if user_id == user['id']:
        raise HTTPException(409, 'Você não pode desativar o próprio acesso')
    with database() as db:
        if not db.execute('UPDATE users SET active=? WHERE id=?', (int(active), user_id)).rowcount:
            raise HTTPException(404, 'Usuário não encontrado')
        db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
    return {'status': 'ok'}

@router.post('/users/{user_id}/remove')
def remove(user_id: str, user=Depends(admin)):
    if user_id == user['id']:
        raise HTTPException(409, 'Você não pode remover o próprio acesso')
    with database() as db:
        db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM users WHERE id=?', (user_id,))
    return {'status': 'ok'}
