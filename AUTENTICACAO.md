# Login único para dashboard e comandos

O login antigo usava apenas `localStorage`: o servidor não conhecia seus usuários.
Agora `/auth/login` verifica usuário e senha no servidor e devolve uma sessão de
oito horas. A dashboard envia essa sessão automaticamente em todos os comandos.
Não há solicitação de chave de operação no navegador.

Senhas usam PBKDF2-SHA256 com salt individual; o banco guarda apenas o resumo dos
tokens de sessão. Logout, remoção e desativação revogam sessões. O servidor verifica
o perfil ativo em cada comando. Administradores cadastram e gerenciam operadores.
Login limita tentativas por usuário a cinco por minuto.

## Preparação antes de publicar

1. Disponibilize armazenamento persistente no host do backend. Defina
   `AUTH_DB_PATH` como o caminho absoluto do arquivo SQLite nesse armazenamento.
   Não use a pasta temporária de uma implantação; perder esse arquivo perde as
   contas. Esta implementação usa um banco compartilhado pelos processos do mesmo
   host, não réplicas em máquinas diferentes. Inclua o banco nos backups do serviço.
2. No terminal do backend, com a mesma configuração de ambiente, execute
   `python create_admin.py`. Informe nome, usuário e senha de no mínimo oito
   caracteres. A senha é digitada sem aparecer. Não envie senhas pelo chat.
   Esse cadastro é administrativo, não existe inscrição pública de administradores.
3. Publique o backend e confirme login e `/auth/me` antes de publicar o frontend.
4. Entre novamente na dashboard. O cadastro antigo do navegador não é migrado
   automaticamente porque o servidor não pode confiar em permissões declaradas
   pelo próprio navegador. É possível cadastrar o mesmo nome de usuário.
5. Use o painel Operadores para os demais acessos. Teste autorização em ambiente
   simulado antes de enviar comandos ao equipamento real.

Para desenvolvimento local, `AUTH_DB_PATH=./smartmotor-auth.sqlite3` no `.env`
usa um arquivo local ignorado pelo Git. Sem `AUTH_DB_PATH`, o novo login informa
que o cadastro ainda não foi configurado; não libera comandos sem autenticação.

`MOTOR_API_TOKEN` continua aceito apenas como credencial de integração já existente.
Ele não é incluído no frontend. `LOCAL_API_TOKEN` do ESP32 é outra credencial e
não participa do login da dashboard.

Validação: `python -m pytest -q` no backend e `npm run build` no frontend.
Os testes de comandos substituem o envio ao equipamento por uma função simulada.
