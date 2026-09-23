"""Run on the backend host, with AUTH_DB_PATH pointing to its persistent database."""
from getpass import getpass
from dotenv import load_dotenv
from services.auth import NewUser, create_user

if __name__ == '__main__':
    load_dotenv()
    name = input('Nome do administrador: ')
    username = input('Usuário: ')
    password = getpass('Senha (mínimo 8 caracteres): ')
    if password != getpass('Confirme a senha: '):
        raise SystemExit('As senhas não conferem')
    create_user(NewUser(name=name, username=username, password=password, role='admin'))
    print('Administrador cadastrado. Entre na dashboard com usuário e senha.')
