# smartmotor-backend

FastAPI que expõe telemetria e comandos do motor. **Não abre porta serial** — toda a
conversa com o campo passa por MQTT TLS até o ESP32, que é slave do TM221.

```
uvicorn main_tm221:app --host 0.0.0.0 --port $PORT
```

## Arquivos

| Arquivo | Papel |
|---|---|
| `main_tm221.py` | Entrypoint único. Rotas de motor + WebSocket `/ws`. |
| `services/edge_link.py` | Transporte MQTT: lease, ack, deadline, verificação de frescor da telemetria. |
| `test_tm221_api.py` | `pytest` — autenticação, limites, recusa de telemetria retida/duplicada, interlock de partida. |

## Contrato de segurança

- Todo comando exige `Authorization: Bearer <MOTOR_API_TOKEN>`. Sem token configurado, a API responde **503** e não aceita nada.
- `POST /motor/start` retorna **202 accepted**, não "motor rodando". O campo `motor_confirmed` é sempre `false`: a confirmação real vem da telemetria do inversor.
- Telemetria `retain` do broker é descartada — mensagem retida não prova que este boot está vivo.
- Telemetria mais velha que 4 s é tratada como ausente (`snapshot()` devolve `None`), e comando sem telemetria fresca é recusado com 503.
- O heartbeat de lease (2 s) é o que mantém o motor autorizado a girar. Se o backend cair, o ESP32 manda parar sozinho em até 10 s.

## Variáveis de ambiente

Ver `.env` (ativo) e `.env.tm221.example` (modelo). O broker **precisa** ser privado:
o tópico de comando aceita partida de motor.

## Atenção

Ao rodar `pytest`, o `test_tm221_api.py` importa `main_tm221`, que chama `load_dotenv()`.
Os testes usam `monkeypatch.setenv` e não tocam o broker real.
