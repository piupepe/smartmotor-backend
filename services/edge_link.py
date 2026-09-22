"""Authenticated MQTT transport. No serial port and no simulated telemetry."""
import json
import os
import ssl
import threading
import time
import uuid
import paho.mqtt.client as mqtt


class EdgeLink:
    def __init__(self):
        self.topic = os.getenv('MQTT_TOPIC_BASE', 'smartmotor/SM-001')
        self.client = None
        self.connected = False
        self.latest = None
        self.received_at = 0.0
        self.lock = threading.Lock()
        self.pending = {}
        self.stop_event = threading.Event()
        self.worker = None
        self.error = 'not_started'
        self.received_count = 0     # telemetria aceita
        self.rejected_count = 0     # chegou no topico mas foi descartada (formato/retained/duplicada)

    def snapshot(self):
        with self.lock:
            if not self.connected or self.latest is None or time.monotonic() - self.received_at > 4:
                return None
            return dict(self.latest)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = reason_code == 0
        self.error = '' if self.connected else str(reason_code)
        if self.connected:
            client.subscribe([(self.topic + '/telemetry', 1), (self.topic + '/ack', 1)])

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        with self.lock:
            self.latest = None

    def on_message(self, client, userdata, message):
        # Retained telemetry/acks cannot prove this boot is alive.
        if message.retain:
            self.rejected_count += 1
            return
        try:
            data = json.loads(message.payload)
            if not isinstance(data, dict):
                return
            if message.topic == self.topic + '/telemetry':
                if data.get('source') != 'tm221' or not isinstance(data.get('boot'), str):
                    self.rejected_count += 1
                    return
                if not isinstance(data.get('uptime_ms'), int):
                    self.rejected_count += 1
                    return
                with self.lock:
                    # Duplicates from QoS replay must not renew freshness.
                    if self.latest and (data['boot'], data['uptime_ms']) == (
                        self.latest.get('boot'), self.latest.get('uptime_ms')):
                        return
                    self.latest = data
                    self.received_at = time.monotonic()
                    self.received_count += 1
            elif message.topic == self.topic + '/ack':
                with self.lock:
                    waiter = self.pending.get(data.get('id'))
                    if waiter and data.get('boot') == waiter['boot']:
                        if data.get('status') in ('accepted', 'rejected', 'duplicate'):
                            waiter['reply'] = data
                            waiter['event'].set()
        except (ValueError, TypeError, UnicodeError):
            return

    def envelope(self, raw):
        # Deadline is in the ESP32 uptime domain, including elapsed local time.
        with self.lock:
            age_ms = int((time.monotonic() - self.received_at) * 1000)
        return {'boot': raw['boot'], 'deadline_ms': (raw['uptime_ms'] + age_ms + 5000) & 0xffffffff}

    def publish(self, suffix, data):
        if not self.client or not self.connected:
            raise ConnectionError('MQTT desconectado')
        result = self.client.publish(self.topic + suffix, json.dumps(data), qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError('Falha ao enviar para o broker')

    # freq/ramp nao usam a caixa postal de comando (reg 6/18) do ESP32, mas ele os
    # recusa com "command_pending" enquanto o CLP nao confirmou o comando anterior.
    # Isso acontece quando o operador solta o slider logo depois de LIGAR: em vez de
    # devolver erro, repete ate o CLP confirmar (normalmente < 1 s).
    RETRY_WHILE_PENDING = ('freq', 'ramp')
    PENDING_RETRY_S = 3.0

    def command(self, action, **parameters):
        limit = time.monotonic() + self.PENDING_RETRY_S
        while True:
            try:
                return self._command_once(action, **parameters)
            except ValueError as e:
                if (action in self.RETRY_WHILE_PENDING and str(e) == 'command_pending'
                        and time.monotonic() < limit):
                    time.sleep(0.3)
                    continue
                raise

    def _command_once(self, action, **parameters):
        raw = self.snapshot()
        if not raw:
            raise ConnectionError('ESP32 sem telemetria recente')
        if action == 'start' and not (raw.get('plc_ok') and raw.get('cfw500_ok') and raw.get('commissioned')):
            raise ValueError('CLP/inversor indisponível ou comissionamento pendente')
        command_id = uuid.uuid4().hex
        waiter = {'event': threading.Event(), 'reply': None, 'boot': raw['boot']}
        with self.lock:
            self.pending[command_id] = waiter
        try:
            envelope = self.envelope(raw)
            self.publish('/lease', envelope)
            self.publish('/command', {'id': command_id, 'action': action, **parameters, **envelope})
            if not waiter['event'].wait(3):
                raise TimeoutError('Sem confirmação do ESP32; estado do motor deve ser conferido pela telemetria')
            reply = waiter['reply']
            if reply['status'] != 'accepted':
                raise ValueError(reply.get('reason', 'Comando recusado'))
            return {'status': 'accepted', 'command_id': command_id, 'motor_confirmed': False}
        finally:
            with self.lock:
                self.pending.pop(command_id, None)

    def start(self):
        host, user, password = (os.getenv(k, '') for k in ('MQTT_HOST', 'MQTT_USER', 'MQTT_PASS'))
        if not all((host, user, password)):
            self.error = 'Configure MQTT_HOST, MQTT_USER e MQTT_PASS para o broker privado'
            return
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='smartmotor-render-' + uuid.uuid4().hex[:8])
        self.client.username_pw_set(user, password)
        self.client.tls_set(ca_certs=os.getenv('MQTT_CA_FILE') or None, cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect, self.client.on_disconnect = self.on_connect, self.on_disconnect
        self.client.on_message = self.on_message
        self.client.connect_async(host, int(os.getenv('MQTT_PORT', '8883')), keepalive=15)
        self.client.loop_start()
        self.stop_event.clear()

        def heartbeat():
            while not self.stop_event.wait(2):
                raw = self.snapshot()
                if raw:
                    try:
                        self.publish('/lease', self.envelope(raw))
                    except ConnectionError:
                        pass
        self.worker = threading.Thread(target=heartbeat, daemon=True)
        self.worker.start()

    def close(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=3)
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()
        self.connected = False


def frontend_payload(raw):
    if not raw:
        return {'source': 'offline', 'estado': 'OFFLINE', 'running': None, 'plc_ok': False,
                'cfw500_ok': False, **{k: None for k in ('temp', 'ax', 'ay', 'az', 'vibRMS',
                'freq', 'rpm', 'corrente', 'tensao', 'hours', 'score')}}
    return {**raw, 'temp': raw.get('temperatura'), 'ax': raw.get('vibration_x'),
            'ay': raw.get('vibration_y'), 'az': raw.get('vibration_z'),
            'vibRMS': raw.get('vibration_rms'), 'freq': raw.get('freq_real'),
            'freqSP': raw.get('freq_setpoint'), 'rampa': raw.get('rampa_s'),
            'tensao': raw.get('tensao_saida'), 'hours': raw.get('horas_operacao'),
            'score': raw.get('saude_score')}
