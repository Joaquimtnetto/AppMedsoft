import json
from datetime import date, datetime, time as datetime_time, timedelta
import http.client
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, session
from psycopg2 import sql
from psycopg2.extras import execute_values

import config
from medsoft_core import get_db_connection
from message_log import log_sent_message


baileys_api_bp = Blueprint('baileys_api', __name__)
_baileys_process = None
_baileys_process_lock = threading.Lock()


def _is_local_service():
    hostname = (urlparse(config.BAILEYS_SERVICE_URL).hostname or '').lower()
    return hostname in {'127.0.0.1', 'localhost', '::1'}


def _baileys_directory():
    configured = os.environ.get('MEDSOFT_BAILEYS_DIRECTORY', '').strip()
    candidates = [
        Path(configured) if configured else None,
        Path(__file__).resolve().parent.parent / 'whatsapp-baileys',
        Path(sys.executable).resolve().parent / 'whatsapp-baileys',
    ]
    for candidate in candidates:
        if candidate and (candidate / 'server.js').is_file():
            return candidate
    raise RuntimeError('A pasta do serviço WhatsApp não foi encontrada.')


def _node_executable():
    executable = shutil.which('node')
    if executable:
        return executable
    default = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'nodejs' / 'node.exe'
    if default.is_file():
        return str(default)
    raise RuntimeError('Node.js não foi encontrado. Instale o Node.js 20 ou superior.')


def _service_environment(directory):
    environment = os.environ.copy()
    env_file = directory / '.env'
    if env_file.is_file():
        for raw_line in env_file.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            environment.setdefault(name.strip(), value.strip())
    return environment


def _service_is_healthy():
    try:
        _service_request('GET', '/health', timeout=2)
        return True
    except RuntimeError:
        return False


def _start_local_service(restart=False):
    global _baileys_process
    if not _is_local_service():
        raise RuntimeError('O serviço WhatsApp configurado é remoto e deve ser reiniciado no servidor.')
    with _baileys_process_lock:
        service_is_healthy = _service_is_healthy()
        process_is_managed = _baileys_process and _baileys_process.poll() is None
        if service_is_healthy and not restart:
            return 'O serviço WhatsApp já está disponível.'
        if service_is_healthy and restart and not process_is_managed:
            _service_request('POST', '/service/stop', timeout=5)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and _service_is_healthy():
                time.sleep(0.25)
            if _service_is_healthy():
                raise RuntimeError('O serviço WhatsApp não encerrou para reinicialização.')
        if _baileys_process and _baileys_process.poll() is None:
            _baileys_process.terminate()
            try:
                _baileys_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _baileys_process.kill()
                _baileys_process.wait(timeout=5)

        directory = _baileys_directory()
        logs_directory = directory / 'logs'
        logs_directory.mkdir(parents=True, exist_ok=True)
        stdout = open(logs_directory / 'service.out.log', 'a', encoding='utf-8')
        stderr = open(logs_directory / 'service.err.log', 'a', encoding='utf-8')
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            _baileys_process = subprocess.Popen(
                [_node_executable(), str(directory / 'server.js')],
                cwd=str(directory),
                env=_service_environment(directory),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=creation_flags,
            )
        finally:
            stdout.close()
            stderr.close()

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if _baileys_process.poll() is not None:
                raise RuntimeError('O serviço WhatsApp encerrou durante a inicialização. Consulte o log do serviço.')
            if _service_is_healthy():
                return 'Serviço WhatsApp iniciado com sucesso.'
            time.sleep(0.5)
        raise RuntimeError('O serviço WhatsApp não respondeu após a inicialização.')


def _company_id():
    value = session.get('idempresa') or session.get('codclin')
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Empresa da sessão não identificada.') from exc
    if value <= 0:
        raise ValueError('Selecione uma empresa antes de conectar o WhatsApp.')
    return value


def _service_request(method, path, payload=None, timeout=30):
    if not config.BAILEYS_SERVICE_TOKEN:
        raise RuntimeError('MEDSOFT_BAILEYS_TOKEN não foi configurado no servidor.')
    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    service_request = urllib.request.Request(
        config.BAILEYS_SERVICE_URL + path,
        method=method,
        data=body,
        headers={
            'Authorization': 'Bearer ' + config.BAILEYS_SERVICE_TOKEN,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(service_request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('message')
        except (ValueError, AttributeError):
            detail = None
        raise RuntimeError(detail or 'O serviço do WhatsApp recusou a solicitação.') from exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError) as exc:
        raise RuntimeError('O serviço de conexão do WhatsApp não está disponível.') from exc


def send_baileys_text(company_id, phone, message):
    try:
        company_id = int(company_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('Empresa não identificada para o envio.') from exc
    if company_id <= 0:
        raise ValueError('Empresa não identificada para o envio.')
    phone_digits = ''.join(character for character in str(phone or '') if character.isdigit())
    if len(phone_digits) in (10, 11):
        phone_digits = '55' + phone_digits
    return _service_request(
        'POST', '/sessions/{}/messages/text'.format(company_id),
        {'phone': phone_digits, 'text': message},
    )


def _digits(value):
    return ''.join(character for character in str(value or '') if character.isdigit())


def _history_timestamp_range(args):
    if str(args.get('todo_historico') or '').lower() in ('1', 'true', 'sim'):
        return None, None
    initial_value = str(args.get('data_inicial') or '').strip()
    final_value = str(args.get('data_final') or '').strip()
    if not initial_value and not final_value:
        final_date = date.today()
        initial_date = final_date - timedelta(days=29)
    elif not initial_value or not final_value:
        raise ValueError('Informe a data inicial e a data final do histórico.')
    else:
        try:
            initial_date = date.fromisoformat(initial_value)
            final_date = date.fromisoformat(final_value)
        except ValueError as exc:
            raise ValueError('O período do histórico possui uma data inválida.') from exc
    if initial_date > final_date:
        raise ValueError('A data inicial não pode ser posterior à data final.')
    timezone = ZoneInfo('America/Sao_Paulo')
    start = datetime.combine(initial_date, datetime_time.min, timezone).timestamp()
    end = datetime.combine(final_date, datetime_time.max, timezone).timestamp()
    return int(start), int(end)


def _merge_contacts(*groups):
    merged = {}
    for contacts in groups:
        for item in contacts or []:
            jid = item.get('jid') or ''
            if item.get('isGroup') or str(jid).endswith('@g.us'):
                key = jid or item.get('phone') or item.get('name')
                if not key:
                    continue
                current = merged.get(key) or {}
                merged[key] = {
                    'jid': jid or current.get('jid') or key,
                    'phone': item.get('phone') or current.get('phone') or key,
                    'name': item.get('name') or current.get('name') or key,
                    'source': item.get('source') or current.get('source') or 'baileys',
                    'isGroup': True,
                }
                continue
            raw_phone = str(item.get('phone') or '').split('@')[0].split(':')[0]
            phone = _digits(raw_phone)
            if len(phone) < 10:
                continue
            if len(phone) in (10, 11):
                phone = '55' + phone
            current = merged.get(phone) or {}
            merged[phone] = {
                'jid': item.get('jid') or current.get('jid') or '{}@s.whatsapp.net'.format(phone),
                'phone': phone,
                'name': item.get('name') or current.get('name') or phone,
                'source': item.get('source') or current.get('source') or 'baileys',
            }
    return sorted(merged.values(), key=lambda item: item['name'].lower())


def _phone_variants(value):
    phone = _digits(str(value or '').split('@')[0].split(':')[0])
    variants = set()
    if not phone:
        return variants
    variants.add(phone)
    local = phone[2:] if phone.startswith('55') else phone
    variants.update((local, '55' + local))
    if len(local) == 11 and local[2:3] == '9':
        without_nine = local[:2] + local[3:]
        variants.update((without_nine, '55' + without_nine))
    elif len(local) == 10:
        with_nine = local[:2] + '9' + local[2:]
        variants.update((with_nine, '55' + with_nine))
    return {item for item in variants if len(item) >= 10}


def _patient_whatsapp_contacts(company_id):
    """Retorna pacientes com telefone para enriquecer os contatos do Baileys."""
    connection = get_db_connection(session.get('db_path') or None)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND lower(table_name) = 'pacient'
            ''')
            columns = {str(row[0]).lower() for row in cursor.fetchall()}
            phone_columns = [name for name in ('telres', 'telcom', 'celular', 'whatsapp') if name in columns]
            if not phone_columns or 'nomecli' not in columns:
                return []
            cursor.execute(
                sql.SQL('SELECT nomecli, {} FROM public.pacient WHERE codclin = %s').format(
                    sql.SQL(', ').join(sql.Identifier(name) for name in phone_columns)
                ),
                (company_id,),
            )
            contacts = []
            for row in cursor.fetchall():
                name = str(row[0] or '').strip()
                if not name:
                    continue
                for value in row[1:]:
                    variants = _phone_variants(value)
                    if not variants:
                        continue
                    phone = max(variants, key=lambda item: (item.startswith('55'), len(item)))
                    contacts.append({
                        'jid': '{}@s.whatsapp.net'.format(phone),
                        'phone': phone,
                        'name': name,
                        'source': 'paciente',
                    })
        return contacts
    finally:
        connection.close()


@baileys_api_bp.get('/api/whatsapp/connection')
def whatsapp_connection():
    try:
        company_id = _company_id()
        try:
            result = _service_request('GET', '/sessions/{}/status'.format(company_id))
        except RuntimeError as exc:
            if 'não está disponível' not in str(exc) or not _is_local_service():
                raise
            _start_local_service()
            result = _service_request('GET', '/sessions/{}/status'.format(company_id))
        return jsonify(result)
    except (ValueError, RuntimeError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503


@baileys_api_bp.post('/api/whatsapp/service/restart')
def whatsapp_service_restart():
    try:
        message = _start_local_service(restart=True)
        return jsonify({'success': True, 'message': message})
    except RuntimeError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503


@baileys_api_bp.post('/api/whatsapp/disconnect')
def whatsapp_disconnect():
    try:
        return jsonify(_service_request('POST', '/sessions/{}/disconnect'.format(_company_id())))
    except (ValueError, RuntimeError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503


@baileys_api_bp.post('/api/whatsapp/reset')
def whatsapp_reset():
    try:
        return jsonify(_service_request('POST', '/sessions/{}/reset'.format(_company_id())))
    except (ValueError, RuntimeError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503


@baileys_api_bp.post('/api/whatsapp/send')
def whatsapp_send():
    data = request.get_json(silent=True) or {}
    try:
        company_id = _company_id()
        result = send_baileys_text(company_id, data.get('phone'), data.get('message'))
        log_sent_message('Whatzap', result.get('recipient') or data.get('phone'), company_id=company_id,
                         message_id=result.get('messageId'), content=data.get('message'))
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503


@baileys_api_bp.get('/api/whatsapp/contacts')
def whatsapp_contacts():
    try:
        company_id = _company_id()
        service_result = _service_request('GET', '/sessions/{}/contacts'.format(company_id))
        patient_contacts = _patient_whatsapp_contacts(company_id)
        contacts = _merge_contacts(service_result.get('contacts'), patient_contacts)
        return jsonify({'success': True, 'contacts': contacts})
    except (ValueError, RuntimeError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503


@baileys_api_bp.get('/api/whatsapp/received')
def whatsapp_received():
    try:
        company_id = _company_id()
        phone = ''.join(character for character in str(request.args.get('phone') or '') if character.isdigit())
        start_timestamp, end_timestamp = _history_timestamp_range(request.args)
        query = []
        if phone:
            query.append('phone=' + phone)
        if start_timestamp is not None:
            query.append('from=' + str(start_timestamp))
            query.append('to=' + str(end_timestamp))
        path = '/sessions/{}/messages/received'.format(company_id)
        if query:
            path += '?' + '&'.join(query)
        result = _service_request('GET', path)
        messages = result.get('messages') or []
        imported_count = 0
        existing_count = 0
        if messages:
            prepared = []
            for message in messages:
                message_id = str(message.get('id') or '').strip()[:255]
                raw_destination = str(message.get('phone') or '').split('@')[0].split(':')[0]
                destination = _digits(raw_destination)[:255]
                content = str(message.get('text') or '').strip()
                if not message_id or not destination or not content:
                    continue
                contact_name = str(message.get('name') or '').strip()[:255] or None
                if contact_name and _digits(contact_name) == destination:
                    contact_name = None
                prepared.append((
                    message_id,
                    int(message.get('timestamp') or 0),
                    destination,
                    content,
                    'saida' if message.get('direction') == 'outgoing' else 'entrada',
                    contact_name,
                ))
            connection = get_db_connection(session.get('db_path') or None)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('''
                        ALTER TABLE public.medsoft_logmsgem
                        ADD COLUMN IF NOT EXISTS conteudo TEXT NULL
                    ''')
                    cursor.execute('''
                        ALTER TABLE public.medsoft_logmsgem
                        ADD COLUMN IF NOT EXISTS direcao VARCHAR(10) NULL
                    ''')
                    cursor.execute('''
                        ALTER TABLE public.medsoft_logmsgem
                        ADD COLUMN IF NOT EXISTS nomecontato VARCHAR(255) NULL
                    ''')
                    message_ids = [item[0] for item in prepared]
                    existing_ids = set()
                    if message_ids:
                        cursor.execute('''
                            SELECT messageid FROM public.medsoft_logmsgem
                            WHERE codclin = %s AND tipo = 'Whatzap'
                              AND messageid = ANY(%s)
                        ''', (company_id, message_ids))
                        existing_ids = {row[0] for row in cursor.fetchall()}
                    existing_count = len(existing_ids)
                    existing_to_update = [
                        (item[5], item[2], item[0], company_id)
                        for item in prepared if item[0] in existing_ids
                    ]
                    if existing_to_update:
                        execute_values(cursor, '''
                            UPDATE public.medsoft_logmsgem AS target
                            SET nomecontato = COALESCE(NULLIF(imported.contact_name, ''), target.nomecontato),
                                destino = imported.destination
                            FROM (VALUES %s) AS imported(contact_name, destination, message_id, company_id)
                            WHERE target.codclin = imported.company_id
                              AND target.tipo = 'Whatzap'
                              AND target.messageid = imported.message_id
                        ''', existing_to_update, template='(%s, %s, %s, %s)', page_size=500)
                    pending = [item + (company_id,) for item in prepared if item[0] not in existing_ids]
                    if pending:
                        execute_values(cursor, '''
                            INSERT INTO public.medsoft_logmsgem
                                (datahoraenvio, tipo, destino, mensagem, codclin, codagend,
                                 enviado, motivoerro, messageid, conteudo, direcao, nomecontato)
                            SELECT
                                CASE WHEN imported.timestamp > 0
                                     THEN (TO_TIMESTAMP(imported.timestamp) AT TIME ZONE 'America/Sao_Paulo')
                                     ELSE (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo') END,
                                'Whatzap', imported.destination, NULL, imported.company_id, NULL,
                                'Sim', NULL, imported.message_id, imported.content, imported.direction,
                                imported.contact_name
                            FROM (VALUES %s) AS imported(
                                message_id, timestamp, destination, content, direction, contact_name, company_id
                            )
                        ''', pending, template='(%s, %s, %s, %s, %s, %s, %s)', page_size=500)
                        imported_count = len(pending)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        result['sync'] = {
            'total': len(messages),
            'validas': len(prepared) if messages else 0,
            'existentes': existing_count,
            'importadas': imported_count,
        }
        return jsonify(result)
    except (ValueError, RuntimeError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503
