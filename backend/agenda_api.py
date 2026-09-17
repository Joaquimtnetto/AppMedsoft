import datetime
import html as html_lib
import json
import re
import smtplib
import urllib.error
import urllib.request
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from flask import Blueprint, current_app, jsonify, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg2 import sql

import config
from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection
from message_log import log_sent_message
from tenant_context import TENANT_COLUMN, current_company_id
from baileys_api import send_baileys_text

agenda_api_bp = Blueprint('agenda_api', __name__)
STATUS_VALUES = {'AT', 'AG', 'CO', 'SC'}
INTERVAL_VALUES = {10, 20, 30, 40, 50, 60}
CONFIRMATION_TOKEN_SALT = 'medsoft-appointment-confirmation'
CONFIRMATION_TOKEN_MAX_AGE = 60 * 60 * 24 * 14
COMMON_EMAIL_DOMAIN_TYPOS = {
    'gmil.com': 'gmail.com',
    'gmai.com': 'gmail.com',
    'gmail.con': 'gmail.com',
    'hotmal.com': 'hotmail.com',
    'outlok.com': 'outlook.com',
}
WEEKDAY_SCHEDULE = {
    0: ('seg', 'iseg', 'fseg', 'iiseg', 'tiseg'),
    1: ('terc', 'iter', 'fter', 'iiter', 'titer'),
    2: ('qua', 'iqua', 'tqua', 'iiqua', 'tiqua'),
    3: ('qui', 'iqui', 'tqui', 'iiqui', 'tiqui'),
    4: ('sex', 'isex', 'tsex', 'iisex', 'tisex'),
    5: ('sab', 'isab', 'tsab', 'iisab', 'tisabb'),
    6: ('dom', 'idom', 'tdom', 'iidom', 'tidom'),
}


def _database_name():
    return session.get('db_path') or None


@contextmanager
def _connection():
    connection = get_db_connection(_database_name())
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _parse_date(value):
    try:
        return datetime.datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('Data inválida.') from exc


def _parse_time(value):
    try:
        parsed = datetime.datetime.strptime(value or '', '%H:%M')
        return parsed.strftime('%H:%M')
    except ValueError as exc:
        raise ValueError('Horário inválido.') from exc


def _parse_schedule_time(value):
    text = str(value or '').strip()
    if not text:
        return None
    if ':' in text:
        parts = text.split(':', 1)
        if not parts[0].strip().isdigit():
            return None
        hour = int(parts[0].strip())
        minute = int(re.sub(r'\D', '', parts[1])[:2] or '0')
    else:
        digits = re.sub(r'\D', '', text)
        if not digits:
            return None
        if len(digits) <= 2:
            hour = int(digits)
            minute = 0
        elif len(digits) == 3:
            hour = int(digits[:1])
            minute = int(digits[1:])
        else:
            hour = int(digits[:2])
            minute = int(digits[2:4])
    if hour > 23 or minute > 59:
        return None
    return datetime.time(hour, minute)


def _time_to_minutes(value):
    return value.hour * 60 + value.minute


def _minutes_to_time(value):
    return f'{value // 60:02d}:{value % 60:02d}'


def _parse_slot_interval(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if not digits:
        return 30
    minutes = int(digits)
    if minutes not in INTERVAL_VALUES:
        return 30
    return minutes


def _schedule_intervals(row, weekday):
    flag_column, start_one, end_one, start_two, end_two = WEEKDAY_SCHEDULE[weekday]
    flag = str(row.get(flag_column) or '').strip().upper()
    if flag in ('N', 'NAO', 'NÃO', '0'):
        return []
    intervals = []
    for start_column, end_column in ((start_one, end_one), (start_two, end_two)):
        start = _parse_schedule_time(row.get(start_column))
        end = _parse_schedule_time(row.get(end_column))
        if start and end and _time_to_minutes(end) > _time_to_minutes(start):
            intervals.append((start, end))
    return intervals


def _build_slots(intervals, interval_minutes, occupied):
    slots_by_time = {}
    for start, end in intervals:
        current = _time_to_minutes(start)
        end_minutes = _time_to_minutes(end)
        while current + interval_minutes <= end_minutes:
            time_value = _minutes_to_time(current)
            appointment = occupied.get(time_value)
            slots_by_time[time_value] = {
                'hora': time_value,
                'disponivel': appointment is None,
                'paciente': (appointment or {}).get('paciente', ''),
                'status': (appointment or {}).get('status', ''),
            }
            current += interval_minutes
    for time_value, appointment in occupied.items():
        if time_value not in slots_by_time:
            slots_by_time[time_value] = {
                'hora': time_value,
                'disponivel': False,
                'paciente': (appointment or {}).get('paciente', ''),
                'status': (appointment or {}).get('status', ''),
            }
    return [slots_by_time[time_value] for time_value in sorted(slots_by_time)]



def _format_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if not digits:
        return ''
    if len(digits) == 10:
        return f'({digits[:2]}){digits[2:6]}-{digits[6:]}'
    if len(digits) == 11:
        return digits
    raise ValueError('Telefone invalido. Use o formato (99)9999-9999 ou DDD com telefone de 9 digitos.')


def _validated_email(value):
    address = (value or '').strip()
    if not address:
        return ''
    _display_name, parsed_address = parseaddr(address)
    valid_format = re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}",
        address,
    )
    if parsed_address != address or not valid_format:
        raise ValueError('E-mail do paciente inválido. Confira o endereço informado.')
    domain = address.rsplit('@', 1)[1].lower()
    suggested_domain = COMMON_EMAIL_DOMAIN_TYPOS.get(domain)
    if suggested_domain:
        suggestion = address.rsplit('@', 1)[0] + '@' + suggested_domain
        raise ValueError(
            'E-mail do paciente parece estar digitado incorretamente. '
            'Você quis dizer {}?'.format(suggestion)
        )
    return address


def _display_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 10:
        return f'({digits[:2]}){digits[2:6]}-{digits[6:]}'
    if len(digits) == 11:
        return f'({digits[:2]}){digits[2:7]}-{digits[7:]}'
    return value or ''


def _whatsapp_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) in (10, 11):
        digits = '55' + digits
    if len(digits) not in (12, 13) or not digits.startswith('55'):
        raise ValueError('Telefone do paciente inválido para envio pelo WhatsApp.')
    return digits


def _confirmation_pattern_record(pattern_type, message_code=None):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                code_filter = ' AND codigo = %s' if message_code not in (None, '') else ''
                parameters = [pattern_type.upper(), current_company_id()]
                if code_filter:
                    parameters.append(message_code)
                cursor.execute(('''
                    SELECT codigo, texto, COALESCE(msghtml, FALSE)
                    FROM public.texto
                    WHERE UPPER(BTRIM(atalho)) = %s AND codclin = %s
                    {code_filter}
                    ORDER BY nome
                    LIMIT 1
                ''').format(code_filter=code_filter), tuple(parameters))
                row = cursor.fetchone()
        return (row[0], (row[1] or '').strip(), bool(row[2])) if row else (None, '', False)
    except Exception:
        current_app.logger.exception('Falha ao carregar padrão de confirmação %s.', pattern_type)
        return None, '', False


def _confirmation_pattern(pattern_type):
    return _confirmation_pattern_record(pattern_type)[1]


def _is_html_message(value):
    return bool(re.search(r'<\s*/?\s*[a-z][a-z0-9:-]*(?:\s|/?>)', value or '', re.I))


def _plain_text_from_html(value):
    text = re.sub(r'<\s*(?:br|/p|/div|/tr|/h[1-6])\s*/?>', '\n', value or '', flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_lib.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n\s*\n+', '\n\n', text).strip()


def _confirmation_message(appointment, template='', confirmation_url='', html_mode=None):
    date_value = appointment['data'].strftime('%d/%m/%Y')
    procedure = (appointment.get('procedimento') or 'agendamento').strip()
    clinic_name = (appointment.get('nomeclinica') or 'MedSoft').strip()
    default_message = (
        f"Prezado {appointment['paciente']},\n\n"
        f"Gostaríamos de confirmar seu {procedure}, na data: {date_value} "
        f"e horário: {appointment['hora']} com o {appointment['profissional']}.\n\n"
        f"Atenciosamente,\n\n{clinic_name}."
    )
    if confirmation_url:
        default_message += '\n\nClique abaixo para confirmar o agendamento:\n' + confirmation_url
    if not template:
        return default_message
    replacements = {
        'paciente': appointment['paciente'],
        'procedimento': procedure,
        'data': date_value,
        'hora': appointment['hora'],
        'profissional': appointment['profissional'],
        'nomeclinica': clinic_name,
        'link_confirmacao': confirmation_url,
    }
    is_html = _is_html_message(template) if html_mode is None else bool(html_mode)
    if is_html:
        replacements = {
            name: html_lib.escape(str(value or ''), quote=True)
            for name, value in replacements.items()
        }
    placeholder_pattern = re.compile(
        r'\{\s*(paciente|procedimento|data|hora|profissional|nomeclinica|link_confirmacao)\s*[\}\)]',
        re.IGNORECASE,
    )
    return placeholder_pattern.sub(
        lambda match: replacements[match.group(1).lower()],
        template,
    )


def _environment_notification_settings():
    return {
        'smtp_host': config.SMTP_HOST,
        'smtp_port': config.SMTP_PORT,
        'smtp_user': config.SMTP_USER,
        'smtp_password': config.SMTP_PASS,
        'smtp_from': config.SMTP_FROM,
        'smtp_tls': config.SMTP_USE_TLS,
        'smtp_ssl': config.SMTP_USE_SSL,
        'whatsapp_sender_number': config.WHATSAPP_SENDER_NUMBER,
        'whatsapp_phone_number_id': config.WHATSAPP_PHONE_NUMBER_ID,
        'whatsapp_access_token': config.WHATSAPP_ACCESS_TOKEN,
        'whatsapp_api_version': config.WHATSAPP_API_VERSION,
        'whatsapp_template_name': config.WHATSAPP_TEMPLATE_NAME,
        'whatsapp_template_language': config.WHATSAPP_TEMPLATE_LANGUAGE,
        'whatsapp_simplified': True,
    }


def _notification_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('s', 'sim', '1', 'true', 't', 'yes', 'on')


def _notification_settings():
    settings = _environment_notification_settings()
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.medsoft_configuracao')")
                if cursor.fetchone()[0] is None:
                    return settings
                cursor.execute('''
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'medsoft_configuracao'
                          AND column_name = 'whatzapsimplificado'
                    )
                ''')
                simplified_column = 'whatzapsimplificado' if cursor.fetchone()[0] else "'N'"
                cursor.execute('''
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'medsoft_configuracao'
                          AND column_name = 'codclin'
                    )
                ''')
                if cursor.fetchone()[0]:
                    cursor.execute('''
                        SELECT smtp_host, smtp_porta, smtp_usuario, smtp_senha,
                               smtp_remetente, smtp_tls, smtp_ssl, whatsapp_remetente,
                               whatsapp_phone_number_id, whatsapp_token, whatsapp_api_version,
                               whatsapp_template, whatsapp_idioma, {}
                        FROM public.medsoft_configuracao
                        WHERE codclin = %s
                    '''.format(simplified_column), (str(current_company_id()),))
                    row = cursor.fetchone()
                else:
                    row = None
                if row is None:
                    cursor.execute('''
                        SELECT smtp_host, smtp_porta, smtp_usuario, smtp_senha,
                               smtp_remetente, smtp_tls, smtp_ssl, whatsapp_remetente,
                               whatsapp_phone_number_id, whatsapp_token, whatsapp_api_version,
                               whatsapp_template, whatsapp_idioma, {}
                        FROM public.medsoft_configuracao
                        LIMIT 1
                    '''.format(simplified_column))
                    row = cursor.fetchone()
        if not row:
            return settings
        names = [
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from',
            'smtp_tls', 'smtp_ssl', 'whatsapp_sender_number',
            'whatsapp_phone_number_id', 'whatsapp_access_token',
            'whatsapp_api_version', 'whatsapp_template_name',
            'whatsapp_template_language', 'whatsapp_simplified',
        ]
        stored = dict(zip(names, row))
        for name, value in stored.items():
            if value not in (None, ''):
                settings[name] = (
                    _notification_bool(value)
                    if name in ('smtp_tls', 'smtp_ssl', 'whatsapp_simplified')
                    else value
                )
        return settings
    except Exception:
        current_app.logger.exception('Falha ao carregar configurações de notificação; usando ambiente.')
        return settings


def _active_clinic_value(logical_field):
    try:
        from clinica_api import _detect_layout
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _detect_layout(cursor)
                if not layout or logical_field not in layout['fields']:
                    return ''
                raw_clinic_id = (
                    current_company_id()
                )
                try:
                    clinic_id = int(raw_clinic_id)
                except (TypeError, ValueError):
                    return ''
                cursor.execute(
                    sql.SQL('SELECT {} FROM public.{} WHERE {} = %s LIMIT 1').format(
                        sql.Identifier(layout['fields'][logical_field]),
                        sql.Identifier(layout['table']),
                        sql.Identifier(layout['id_column']),
                    ),
                    (clinic_id,),
                )
                row = cursor.fetchone()
        return (row[0] or '').strip() if row else ''
    except Exception:
        current_app.logger.exception('Falha ao carregar %s da clínica ativa.', logical_field)
        return ''


def _clinic_cellphone():
    return _active_clinic_value('celular')


def _clinic_name():
    return _active_clinic_value('nome')


def _appointment_confirmation_url(appointment_id, channel='email'):
    token = URLSafeTimedSerializer(current_app.secret_key).dumps({
        'appointment_id': int(appointment_id),
        'database': _database_name() or config.PG_DB,
        'idempresa': current_company_id(),
        'channel': channel,
    }, salt=CONFIRMATION_TOKEN_SALT)
    path = url_for('agenda_api.confirm_appointment', token=token)
    base_url = config.PUBLIC_URL or request.url_root.rstrip('/')
    return base_url + path


def _whatsapp_confirmation_url(appointment_id):
    url = _appointment_confirmation_url(appointment_id, channel='whatsapp')
    return (
        url.replace('http://localhost', 'http://127.0.0.1')
        .replace('https://localhost', 'https://127.0.0.1')
        .replace('127.0.0.1', '127-0-0-1.sslip.io')
    )


def _confirmation_email_html(appointment, confirmation_url):
    date_value = appointment['data'].strftime('%d/%m/%Y')
    values = {
        name: str(value or '')
        for name, value in {
            'paciente': appointment.get('paciente'),
            'profissional': appointment.get('profissional'),
            'procedimento': appointment.get('procedimento') or 'Consulta',
            'hora': appointment.get('hora'),
            'clinica': appointment.get('nomeclinica') or 'MedSoft',
            'data': date_value,
            'url': confirmation_url,
        }.items()
    }
    return render_template('email_confirmacao_agenda.html', **values)


def _confirmed_appointment_message(appointment):
    return (
        'Olá, {}.\n\nSua {} com {} foi confirmada para {} às {}.\n\n'
        'Atenciosamente,\n{}.'
    ).format(
        appointment.get('paciente') or '',
        appointment.get('procedimento') or 'consulta',
        appointment.get('profissional') or 'o profissional de saúde',
        appointment['data'].strftime('%d/%m/%Y'),
        appointment.get('hora') or '',
        appointment.get('nomeclinica') or 'MedSoft',
    )


def _confirmed_appointment_email_html(appointment):
    return render_template('email_agendamento_confirmado.html', appointment=appointment)


def _send_confirmation_email(
        to_address, appointment, settings=None, message=None, confirmation_url=None,
        subject=None, html_body=None, message_code=None, company_id=None,
        message_type='Email Manual', appointment_id=None, database_name=None,
        html_mode=None):
    settings = settings or _environment_notification_settings()
    destination_for_log = str(to_address or '').strip()
    message_id = None
    log_content = str(message or '').strip()

    def log_attempt(sent, reason=''):
        return log_sent_message(
            message_type, destination_for_log, message_code, company_id=company_id,
            appointment_id=appointment_id, database_name=database_name,
            sent=sent, error_reason=reason, message_id=message_id,
            content=log_content,
        )

    if not to_address:
        error = 'Paciente sem e-mail cadastrado.'
        log_attempt(False, error)
        return False, error
    server = None
    try:
        to_address = _validated_email(to_address)
    except ValueError as exc:
        error = str(exc)
        log_attempt(False, error)
        return False, error
    if not settings['smtp_host']:
        error = 'Servidor de e-mail (SMTP) não configurado.'
        log_attempt(False, error)
        return False, error
    try:
        email = EmailMessage()
        email['From'] = formataddr(('MedSoft', settings['smtp_from']))
        email['To'] = to_address
        sender_domain = (
            settings['smtp_from'].rsplit('@', 1)[1]
            if '@' in settings['smtp_from'] else None
        )
        tracking_parts = [
            'medsoft', str(company_id or '0'), str(appointment_id or '0')
        ]
        message_id = make_msgid(idstring='-'.join(tracking_parts), domain=sender_domain)
        email['Message-ID'] = message_id
        email['X-MedSoft-Appointment'] = str(appointment_id or '')
        date_value = appointment['data'].strftime('%d/%m/%Y')
        email['Subject'] = subject or 'Você vai à consulta com {} em {} às {}?'.format(
                appointment.get('profissional') or 'seu profissional',
                date_value,
                appointment.get('hora') or '',
            )
        rendered_message = message or _confirmation_message(appointment)
        message_is_html = (
            _is_html_message(rendered_message) if html_mode is None else bool(html_mode)
        )
        plain_message = (
            _plain_text_from_html(rendered_message)
            if message_is_html else rendered_message
        )
        if confirmation_url and not message_is_html and confirmation_url not in plain_message:
            plain_message += '\n\nConfirme seu agendamento: ' + confirmation_url
        log_content = plain_message
        email.set_content(plain_message)
        if html_body:
            email.add_alternative(html_body, subtype='html')
        elif message_is_html:
            email.add_alternative(rendered_message, subtype='html')
        elif confirmation_url and html_mode is not False:
            email.add_alternative(
                _confirmation_email_html(appointment, confirmation_url),
                subtype='html',
            )
        if settings['smtp_ssl']:
            server = smtplib.SMTP_SSL(settings['smtp_host'], settings['smtp_port'], timeout=15)
        else:
            server = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'], timeout=15)
        server.ehlo()
        if settings['smtp_tls'] and not settings['smtp_ssl']:
            server.starttls()
            server.ehlo()
        if settings['smtp_user'] and settings['smtp_password']:
            server.login(settings['smtp_user'], settings['smtp_password'])
        send_options = {}
        if server.has_extn('dsn'):
            send_options = {
                'mail_options': ['RET=HDRS'],
                'rcpt_options': ['NOTIFY=FAILURE,DELAY'],
            }
        refused_recipients = server.send_message(
            email,
            from_addr=settings['smtp_from'],
            to_addrs=[to_address],
            **send_options,
        )
        if refused_recipients:
            raise smtplib.SMTPRecipientsRefused(refused_recipients)
        server.quit()
        server = None
        log_attempt(
            True,
            'Aceito pelo servidor SMTP; entrega final não confirmada.',
        )
        return True, ''
    except smtplib.SMTPRecipientsRefused:
        current_app.logger.exception('Destinatário recusado no envio da confirmação por e-mail.')
        error = 'O servidor recusou o e-mail do paciente. Confira o endereço cadastrado.'
        log_attempt(False, error)
        return False, error
    except smtplib.SMTPAuthenticationError:
        current_app.logger.exception('Autenticação SMTP recusada no envio da confirmação por e-mail.')
        error = 'O servidor recusou a autenticação do e-mail. Teste a conexão em Config. e-mail.'
        log_attempt(False, error)
        return False, error
    except (smtplib.SMTPException, OSError, TimeoutError):
        current_app.logger.exception('Falha ao enviar confirmação por e-mail.')
        error = 'Falha na conexão com o servidor de e-mail. Teste a conexão em Config. e-mail.'
        log_attempt(False, error)
        return False, error
    except Exception:
        current_app.logger.exception('Falha inesperada ao enviar confirmação por e-mail.')
        error = 'Falha inesperada no envio do e-mail.'
        log_attempt(False, error)
        return False, error
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def _send_confirmation_whatsapp(
        phone, appointment, settings=None, message_code=None,
        appointment_id=None, company_id=None, database_name=None, message=None):
    settings = settings or _environment_notification_settings()

    def log_attempt(sent, reason='', destination=None):
        return log_sent_message(
            'Whatzap', destination or phone, message_code, company_id=company_id,
            appointment_id=appointment_id, database_name=database_name,
            sent=sent, error_reason=reason, content=message,
        )

    required = [
        settings['whatsapp_phone_number_id'],
        settings['whatsapp_access_token'],
        settings['whatsapp_api_version'],
    ]
    if not message:
        required.append(settings['whatsapp_template_name'])
    if not all(required):
        error = 'WhatsApp Business não configurado.'
        log_attempt(False, error)
        return False, error
    try:
        recipient = _whatsapp_phone(phone)
    except ValueError as exc:
        error = str(exc)
        log_attempt(False, error)
        return False, error
    if message:
        payload = {
            'messaging_product': 'whatsapp', 'to': recipient, 'type': 'text',
            'text': {'preview_url': True, 'body': message},
        }
    else:
        date_value = appointment['data'].strftime('%d/%m/%Y')
        payload = {
            'messaging_product': 'whatsapp',
            'to': recipient,
            'type': 'template',
            'template': {
                'name': settings['whatsapp_template_name'],
                'language': {'code': settings['whatsapp_template_language']},
                'components': [{
                    'type': 'body',
                    'parameters': [
                        {'type': 'text', 'text': appointment['paciente']},
                        {'type': 'text', 'text': date_value},
                        {'type': 'text', 'text': appointment['hora']},
                        {'type': 'text', 'text': appointment['profissional']},
                    ],
                }],
            },
        }
    url = (
        f"https://graph.facebook.com/{settings['whatsapp_api_version']}/"
        f"{settings['whatsapp_phone_number_id']}/messages"
    )
    api_request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f"Bearer {settings['whatsapp_access_token']}",
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(api_request, timeout=15) as response:
            if 200 <= response.status < 300:
                log_attempt(True, destination=recipient)
                return True, ''
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        current_app.logger.exception('Falha ao enviar confirmação pelo WhatsApp.')
    error = 'Falha no envio pelo WhatsApp.'
    log_attempt(False, error, destination=recipient)
    return False, error



def _limit_legacy_text(value, max_length=30):
    text = str(value or '').strip()
    return text[:max_length]
def _appointment_data(data):
    patient = _limit_legacy_text(data.get('paciente'))
    if not patient:
        raise ValueError('Informe o nome do paciente.')
    professional = _limit_legacy_text(data.get('profissional'), 40)
    if not professional:
        raise ValueError('Informe o Prof. Saude.')
    status = (data.get('status') or 'AG').strip().upper()
    if status not in STATUS_VALUES:
        raise ValueError('Informe um status valido para a agenda.')
    observation = (data.get('observacao') or '').strip()
    if len(observation) > 200:
        raise ValueError('A observação deve ter no máximo 200 caracteres.')
    email = _validated_email(data.get('email'))
    if len(email) > 120:
        raise ValueError('O e-mail deve ter no máximo 120 caracteres.')
    return {
        'datacons': _parse_date(data.get('data')),
        'horacons': _parse_time(data.get('hora')),
        'nomepaci': patient,
        'nomed': professional,
        'telefone': _format_phone(data.get('telefone')),
        'email': email,
        'nomeplano': _limit_legacy_text(data.get('plano'), 25),
        'proced': _limit_legacy_text(data.get('procedimento')),
        'observacao': observation,
        'atend': status,
    }


def _registered_patient(patient_id):
    try:
        patient_id = int(patient_id)
        if patient_id <= 0:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError('Selecione um paciente cadastrado.') from exc
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT nomecli,
                       COALESCE(NULLIF(telres, ''), NULLIF(telcom, ''), ''),
                       COALESCE(email, ''), COALESCE(nomeplano1, '')
                FROM public.pacient
                WHERE codcli = %s AND codclin = %s
                LIMIT 1
            ''', (patient_id, current_company_id()))
            row = cursor.fetchone()
    if not row:
        raise ValueError('Paciente não encontrado para a empresa ativa.')
    return {
        'id': patient_id,
        'nome': row[0] or '',
        'telefone': row[1] or '',
        'email': row[2] or '',
        'plano': row[3] or '',
    }


def _appointment_data_from_request(data):
    data = dict(data or {})
    patient = _registered_patient(data.get('codpac'))
    # Nome sempre vem do cadastro validado; os demais dados podem ser ajustados
    # especificamente para o agendamento quando necessário.
    data['paciente'] = patient['nome']
    data['telefone'] = data.get('telefone') or patient['telefone']
    data['email'] = data.get('email') or patient['email']
    data['plano'] = data.get('plano') or patient['plano']
    return _appointment_data(data)


def _update_patient_last_appointment(patient_id, appointment):
    if appointment.get('atend') != 'AT':
        return False
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE public.pacient
                SET datult_ = %s
                WHERE codcli = %s AND codclin = %s
            ''', (
                appointment['datacons'], int(patient_id), current_company_id()
            ))
            if cursor.rowcount == 0:
                raise ValueError('Paciente não encontrado para atualizar a data do atendimento.')
    return True


def _format_time(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    return str(value)[:5]


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    current_app.logger.exception('Falha na operação da agenda', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


agenda_repository = CrudRepository(
    connection_factory=_connection,
    table='agenda',
    id_column='codagend',
    writable_columns=(
        'datacons', 'horacons', 'nomepaci', 'nomed', 'telefone', 'email', 'nomeplano',
        'proced', 'observacao', 'atend'
    ),
    generate_integer_id=True,
    tenant_column=TENANT_COLUMN,
    tenant_value_factory=current_company_id,
)


@agenda_api_bp.route('/api/agenda', methods=['POST'])
def api_agenda():
    data = request.get_json(silent=True) or {}
    data_str = data.get('data') if data else None
    professional = _limit_legacy_text(data.get('profissional'), 40)
    patient = _limit_legacy_text(data.get('paciente'))
    if not data_str and not patient:
        return jsonify({'success': False, 'message': 'Informe uma data ou um paciente.'}), 400
    try:
        data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
        with _connection() as con:
            with con.cursor() as cur:
                statement = '''
                    SELECT a.codagend, a.datacons, a.horacons, a.nomepaci,
                           a.nomed, a.telefone, a.nomeplano, a.proced, a.atend,
                           a.observacao, a.email
                    FROM public.agenda a
                    WHERE a.codclin = %s
                '''
                parameters = [current_company_id()]
                if data_obj:
                    statement += ' AND a.datacons = %s'
                    parameters.append(data_obj)
                if professional:
                    statement += ' AND a.nomed = %s'
                    parameters.append(professional)
                if patient:
                    statement += ' AND a.nomepaci ILIKE %s'
                    parameters.append(f'%{patient}%')
                statement += '''
                    ORDER BY a.datacons DESC, a.horacons, a.codagend
                    LIMIT 200
                '''
                cur.execute(statement, parameters)
                rows = cur.fetchall()
        resultados = [{
            'CODAGEND': row[0],
            'DATACONS': row[1].isoformat() if row[1] else '',
            'HORACONS': _format_time(row[2]),
            'NOMEPACI': row[3] or '',
            'NOMED': row[4] or '',
            'TELEFONE': _display_phone(row[5]),
            'NOMEPLANO': row[6] or '',
            'PROCED': row[7] or '',
            'ATEND': row[8] or '',
            'OBSERVACAO': row[9] or '',
            'EMAIL': row[10] or '',
        } for row in rows]
        return jsonify({'success': True, 'resultados': resultados})
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/relatorios/agenda', methods=['POST'])
def report_agenda():
    data = request.get_json(silent=True) or {}
    try:
        start_date = _parse_date(data.get('data_inicio'))
        end_date = _parse_date(data.get('data_fim'))
        if end_date < start_date:
            raise ValueError('A Data Fim deve ser igual ou posterior a Data Inicio.')
        professional = _limit_legacy_text(data.get('profissional'), 40)
        plan = (data.get('plano') or '').strip()
        with _connection() as connection:
            with connection.cursor() as cursor:
                statement = '''
                    SELECT a.codagend, a.datacons, a.horacons, a.nomepaci,
                           a.nomed, a.telefone, a.nomeplano, a.proced, a.atend,
                           a.observacao, a.email
                    FROM public.agenda a
                    WHERE a.codclin = %s
                      AND a.datacons BETWEEN %s AND %s
                '''
                parameters = [current_company_id(), start_date, end_date]
                if professional:
                    statement += ' AND a.nomed = %s'
                    parameters.append(professional)
                if plan:
                    statement += ' AND a.nomeplano = %s'
                    parameters.append(plan)
                statement += ' ORDER BY a.datacons, a.horacons, a.codagend'
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        fields = (
            'codigo', 'data', 'hora', 'paciente', 'prof_saude', 'telefone',
            'plano', 'procedimento', 'status', 'observacao', 'email'
        )
        appointments = []
        for row in rows:
            values = list(row)
            values[1] = values[1].strftime('%d/%m/%Y') if values[1] else ''
            values[2] = _format_time(values[2])
            values[5] = _display_phone(values[5])
            appointments.append(dict(zip(fields, values)))
        return jsonify({
            'success': True,
            'agendamentos': appointments,
            'colunas': list(fields),
            'total': len(appointments),
        })
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/disponibilidade', methods=['POST'])
def availability():
    data = request.get_json(silent=True) or {}
    data_str = data.get('data') if data else None
    professional = _limit_legacy_text(data.get('profissional'), 40)
    if not data_str:
        return jsonify({'success': False, 'message': 'Data não informada.'}), 400
    if not professional:
        return jsonify({'success': False, 'message': 'Informe o Prof. Saude.'}), 400
    try:
        data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
        schedule_columns = [column for config in WEEKDAY_SCHEDULE.values() for column in config] + ['consulta']
        select_columns = ', '.join(schedule_columns)
        with _connection() as con:
            with con.cursor() as cur:
                cur.execute(
                    f'SELECT {select_columns} FROM public.nomed WHERE nomed = %s AND codclin = %s LIMIT 1',
                    (professional, current_company_id()),
                )
                schedule = cur.fetchone()
                if not schedule:
                    return jsonify({'success': False, 'message': 'Profissional nao encontrado.'}), 404
                schedule_data = dict(zip(schedule_columns, schedule))
                cur.execute('''
                    SELECT horacons, nomepaci, atend
                    FROM public.agenda
                    WHERE datacons = %s AND nomed = %s AND codclin = %s
                ''', (data_obj, professional, current_company_id()))
                occupied = {
                    _format_time(row[0]): {'paciente': row[1] or '', 'status': row[2] or ''}
                    for row in cur.fetchall()
                    if _format_time(row[0])
                }
        interval_minutes = _parse_slot_interval(data.get('intervalo'))
        intervals = _schedule_intervals(schedule_data, data_obj.weekday())
        return jsonify({
            'success': True,
            'profissional': professional,
            'data': data_obj.isoformat(),
            'intervalo': interval_minutes,
            'horarios': _build_slots(intervals, interval_minutes, occupied),
        })
    except ValueError:
        return jsonify({'success': False, 'message': 'Data inválida.'}), 400
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>/solicitar-confirmacao', methods=['POST'])
def request_appointment_confirmation(appointment_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    SELECT datacons, horacons, nomepaci, nomed, telefone, proced, email
                    FROM public.agenda
                    WHERE codagend = %s AND codclin = %s
                    LIMIT 1
                ''', (appointment_id, current_company_id()))
                row = cursor.fetchone()
                if not row:
                    return jsonify({'success': False, 'message': 'Agendamento não encontrado.'}), 404
                appointment = {
                    'data': row[0],
                    'hora': _format_time(row[1]),
                    'paciente': row[2] or '',
                    'profissional': row[3] or '',
                    'telefone': row[4] or '',
                    'procedimento': row[5] or '',
                    'email': row[6] or '',
                    'nomeclinica': _clinic_name(),
                }
                cursor.execute('''
                    SELECT email, COALESCE(NULLIF(telres, ''), NULLIF(telcom, ''), '')
                    FROM public.pacient
                    WHERE UPPER(BTRIM(nomecli)) = UPPER(BTRIM(%s)) AND codclin = %s
                    ORDER BY codcli
                    LIMIT 1
                ''', (appointment['paciente'], current_company_id()))
                patient_row = cursor.fetchone()

        patient_email = (patient_row[0] or '').strip() if patient_row else ''
        email = (appointment['email'] or '').strip() or patient_email
        fallback_phone = patient_row[1] if patient_row else ''
        phone = appointment['telefone'] or fallback_phone
        settings = _notification_settings()
        email_message_code, email_pattern, email_html = _confirmation_pattern_record('E')
        whatsapp_message_code, _whatsapp_pattern, _whatsapp_html = _confirmation_pattern_record('Z')
        confirmation_url = _appointment_confirmation_url(appointment_id)
        email_message = _confirmation_message(
            appointment, email_pattern, confirmation_url, html_mode=email_html
        )
        email_sent, email_error = _send_confirmation_email(
            email, appointment, settings, email_message, confirmation_url,
            message_code=email_message_code,
            appointment_id=appointment_id,
            html_mode=email_html,
        )
        whatsapp_sent, whatsapp_error = _send_confirmation_whatsapp(
            phone, appointment, settings, message_code=whatsapp_message_code,
            appointment_id=appointment_id,
        )

        if email_sent or whatsapp_sent:
            with _connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'UPDATE public.agenda SET atend = %s WHERE codagend = %s AND codclin = %s',
                        ('SC', appointment_id, current_company_id()),
                    )

        results = []
        results.append('E-mail aceito pelo servidor de envio.' if email_sent else email_error)
        results.append('WhatsApp enviado.' if whatsapp_sent else whatsapp_error)
        message = ' '.join(filter(None, results))
        if not email_sent and not whatsapp_sent:
            return jsonify({'success': False, 'message': message}), 400
        return jsonify({
            'success': True,
            'complete': email_sent and whatsapp_sent,
            'email_sent': email_sent,
            'whatsapp_sent': whatsapp_sent,
            'sender_number': settings['whatsapp_sender_number'],
            'message': message,
        })
    except Exception as exc:
        return _error_response(exc)


def _confirmation_context(appointment_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT datacons, horacons, nomepaci, nomed, telefone, proced, email
                FROM public.agenda
                WHERE codagend = %s AND codclin = %s
                LIMIT 1
            ''', (appointment_id, current_company_id()))
            row = cursor.fetchone()
            if not row:
                return None, '', ''
            appointment = {
                'data': row[0],
                'hora': _format_time(row[1]),
                'paciente': row[2] or '',
                'profissional': row[3] or '',
                'telefone': row[4] or '',
                'procedimento': row[5] or '',
                'email': row[6] or '',
                'nomeclinica': _clinic_name(),
            }
            cursor.execute('''
                SELECT email, COALESCE(NULLIF(telres, ''), NULLIF(telcom, ''), '')
                FROM public.pacient
                WHERE UPPER(BTRIM(nomecli)) = UPPER(BTRIM(%s)) AND codclin = %s
                ORDER BY codcli
                LIMIT 1
            ''', (appointment['paciente'], current_company_id()))
            patient_row = cursor.fetchone()
    patient_email = (patient_row[0] or '').strip() if patient_row else ''
    email = (appointment['email'] or '').strip() or patient_email
    fallback_phone = patient_row[1] if patient_row else ''
    return appointment, email, appointment['telefone'] or fallback_phone


def _mark_confirmation_requested(appointment_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE public.agenda SET atend = %s WHERE codagend = %s AND codclin = %s',
                ('SC', appointment_id, current_company_id()),
            )


def _has_successful_email_for_appointment(appointment_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT EXISTS (
                    SELECT 1
                    FROM public.medsoft_logmsgem
                    WHERE codclin::text = %s
                      AND codagend = %s
                      AND tipo IN ('Email Auto', 'Email Manual', 'Email')
                      AND COALESCE(enviado, 'Sim') = 'Sim'
                )
            ''', (str(current_company_id()), appointment_id))
            return bool(cursor.fetchone()[0])


def _mark_appointment_rescheduled(appointment_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE public.agenda
                SET atend = 'AG',
                    datatualiza = CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                WHERE codagend = %s AND codclin = %s
            ''', (appointment_id, current_company_id()))


def _appointment_schedule(appointment_id):
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT datacons, horacons
                FROM public.agenda
                WHERE codagend = %s AND codclin = %s
                LIMIT 1
            ''', (appointment_id, current_company_id()))
            return cursor.fetchone()


def _send_rescheduled_confirmation(appointment_id):
    appointment, email, _phone = _confirmation_context(appointment_id)
    if not appointment:
        return False, 'Agendamento não encontrado.'
    message_code, pattern, message_html = _confirmation_pattern_record('E')
    confirmation_url = _appointment_confirmation_url(appointment_id)
    message = _confirmation_message(
        appointment, pattern, confirmation_url, html_mode=message_html
    )
    sent, error = _send_confirmation_email(
        email,
        appointment,
        _notification_settings(),
        message,
        confirmation_url,
        message_code=message_code,
        message_type='Email Auto',
        appointment_id=appointment_id,
        html_mode=message_html,
    )
    if sent:
        _mark_confirmation_requested(appointment_id)
    return sent, error


def _confirmation_token_payload(token):
    return URLSafeTimedSerializer(current_app.secret_key).loads(
        token,
        salt=CONFIRMATION_TOKEN_SALT,
        max_age=CONFIRMATION_TOKEN_MAX_AGE,
    )


def _public_appointment(payload, confirm=False):
    appointment_id = int(payload.get('appointment_id'))
    company_id = int(payload.get('idempresa'))
    database_name = payload.get('database') or config.PG_DB
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT datacons, horacons, nomepaci, nomed, proced, atend, email, telefone
                FROM public.agenda
                WHERE codagend = %s AND codclin = %s
                LIMIT 1
                FOR UPDATE
            ''', (appointment_id, company_id))
            row = cursor.fetchone()
            if not row:
                connection.commit()
                return None
            current_status = row[5] or ''
            newly_confirmed = confirm and current_status != 'CO'
            if newly_confirmed:
                cursor.execute(
                    'UPDATE public.agenda SET atend = %s WHERE codagend = %s AND codclin = %s',
                    ('CO', appointment_id, company_id),
                )
            patient_email = ''
            patient_phone = ''
            if not (row[6] or '').strip() or not (row[7] or '').strip():
                cursor.execute('''
                    SELECT email, COALESCE(NULLIF(telres, ''), NULLIF(telcom, ''), '')
                    FROM public.pacient
                    WHERE UPPER(BTRIM(nomecli)) = UPPER(BTRIM(%s)) AND codclin = %s
                    ORDER BY codcli
                    LIMIT 1
                ''', (row[2] or '', company_id))
                patient_row = cursor.fetchone()
                patient_email = (patient_row[0] or '').strip() if patient_row else ''
                patient_phone = (patient_row[1] or '').strip() if patient_row else ''
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {
        'id': appointment_id,
        'idempresa': company_id,
        'data': row[0],
        'hora': _format_time(row[1]),
        'paciente': row[2] or '',
        'profissional': row[3] or '',
        'procedimento': row[4] or 'Consulta',
        'status': 'CO' if newly_confirmed else current_status,
        'email': (row[6] or '').strip() or patient_email,
        'telefone': (row[7] or '').strip() or patient_phone,
        'newly_confirmed': newly_confirmed,
    }


@agenda_api_bp.route('/confirmar-agendamento/<token>', methods=['GET', 'POST'])
def confirm_appointment(token):
    try:
        payload = _confirmation_token_payload(token)
        channel = str(payload.get('channel') or 'email').strip().lower()
        if channel not in ('email', 'whatsapp'):
            channel = 'email'
        session['db_path'] = payload.get('database') or config.PG_DB
        session['idempresa'] = int(payload.get('idempresa'))
        appointment = _public_appointment(payload, confirm=request.method == 'POST')
        if not appointment:
            return render_template(
                'confirmacao_agendamento.html', invalid=True,
                message='Agendamento não encontrado.'
            ), 404
        appointment['nomeclinica'] = _clinic_name() or 'MedSoft'
        email_notice = ''
        email_success = None
        if request.method == 'POST' and appointment['newly_confirmed']:
            settings = _notification_settings()
            if channel == 'whatsapp':
                confirmation_message = _confirmed_appointment_message(appointment)
                if settings['whatsapp_simplified']:
                    try:
                        result = send_baileys_text(
                            appointment['idempresa'], _whatsapp_phone(appointment['telefone']),
                            confirmation_message,
                        )
                        email_success = True
                        email_notice = result.get('message') or 'Enviamos um WhatsApp confirmando sua consulta.'
                        log_sent_message(
                            'Whatzap', _whatsapp_phone(appointment['telefone']), None,
                            appointment_id=appointment['id'], company_id=appointment['idempresa'],
                            message_id=result.get('messageId'), content=confirmation_message,
                        )
                    except (ValueError, RuntimeError) as exc:
                        email_success = False
                        email_notice = 'A consulta foi confirmada, mas o WhatsApp não pôde ser enviado: ' + str(exc)
                        log_sent_message(
                            'Whatzap', appointment['telefone'], None,
                            appointment_id=appointment['id'], company_id=appointment['idempresa'],
                            sent=False, error_reason=str(exc), content=confirmation_message,
                        )
                else:
                    sent, error = _send_confirmation_whatsapp(
                        appointment['telefone'], appointment, settings,
                        appointment_id=appointment['id'], company_id=appointment['idempresa'],
                        database_name=payload.get('database'), message=confirmation_message,
                    )
                    email_success = sent
                    email_notice = (
                        'Enviamos um WhatsApp confirmando sua consulta.'
                        if sent else 'A consulta foi confirmada, mas o WhatsApp não pôde ser enviado: ' + error
                    )
            else:
                sent, error = _send_confirmation_email(
                    appointment['email'], appointment, settings,
                    _confirmed_appointment_message(appointment),
                    subject='Sua consulta foi confirmada - MedSoft',
                    html_body=_confirmed_appointment_email_html(appointment),
                    company_id=appointment['idempresa'],
                    message_type='Email Auto',
                    appointment_id=appointment['id'],
                )
                email_success = sent
                email_notice = (
                    'Enviamos um e-mail confirmando sua consulta.'
                    if sent else 'A consulta foi confirmada, mas o e-mail não pôde ser enviado: ' + error
                )
        return render_template(
            'confirmacao_agendamento.html',
            appointment=appointment,
            token=token,
            confirmed=appointment['status'] == 'CO',
            email_notice=email_notice,
            email_success=email_success,
            whatsapp_url='',
        )
    except SignatureExpired:
        return render_template(
            'confirmacao_agendamento.html', invalid=True,
            message='Este link de confirmação expirou.'
        ), 410
    except (BadSignature, TypeError, ValueError):
        return render_template(
            'confirmacao_agendamento.html', invalid=True,
            message='Link de confirmação inválido.'
        ), 400


@agenda_api_bp.route('/api/agenda/textos-confirmacao', methods=['POST'])
def list_confirmation_patterns():
    try:
        data = request.get_json(silent=True) or {}
        pattern_type = str(data.get('tipo') or '').strip().upper()
        if pattern_type not in ('E', 'Z'):
            raise ValueError('Informe o canal da mensagem padrão.')
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    SELECT codigo, nome
                    FROM public.texto
                    WHERE UPPER(BTRIM(atalho)) = %s AND codclin = %s
                    ORDER BY nome
                ''', (pattern_type, current_company_id()))
                patterns = [
                    {'value': str(row[0]), 'label': '{} - {}'.format(row[0], row[1] or '')}
                    for row in cursor.fetchall()
                ]
        if not patterns:
            channel = 'E-mail' if pattern_type == 'E' else 'WhatsApp'
            patterns = [{'value': '__default__', 'label': 'Mensagem padrão MedSoft ({})'.format(channel)}]
        return jsonify({'success': True, 'textos': patterns})
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>/solicitar-confirmacao-email', methods=['POST'])
def request_email_confirmation(appointment_id):
    try:
        data = request.get_json(silent=True) or {}
        selected_code = data.get('codigo_texto')
        if selected_code == '__default__':
            selected_code = None
        appointment, email, _phone = _confirmation_context(appointment_id)
        if not appointment:
            return jsonify({'success': False, 'message': 'Agendamento não encontrado.'}), 404
        settings = _notification_settings()
        message_code, pattern, message_html = _confirmation_pattern_record('E', selected_code)
        if selected_code not in (None, '') and message_code is None:
            raise ValueError('O texto padrão de e-mail selecionado não foi encontrado.')
        confirmation_url = _appointment_confirmation_url(appointment_id)
        message = _confirmation_message(
            appointment, pattern, confirmation_url, html_mode=message_html
        )
        sent, error = _send_confirmation_email(
            email, appointment, settings, message, confirmation_url,
            message_code=message_code,
            appointment_id=appointment_id,
            html_mode=message_html,
        )
        if not sent:
            return jsonify({'success': False, 'message': error}), 400
        _mark_confirmation_requested(appointment_id)
        return jsonify({
            'success': True,
            'message': (
                'Solicitação aceita pelo servidor de e-mail para {}. '
                'A entrega final ainda não foi confirmada.'
            ).format(email),
        })
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>/solicitar-confirmacao-whatsapp', methods=['POST'])
def request_whatsapp_confirmation(appointment_id):
    try:
        data = request.get_json(silent=True) or {}
        selected_code = data.get('codigo_texto')
        if selected_code == '__default__':
            selected_code = None
        appointment, _email, phone = _confirmation_context(appointment_id)
        if not appointment:
            return jsonify({'success': False, 'message': 'Agendamento não encontrado.'}), 404
        settings = _notification_settings()
        message_code, pattern, _message_html = _confirmation_pattern_record('Z', selected_code)
        if selected_code not in (None, '') and message_code is None:
            raise ValueError('O texto padrão de WhatsApp selecionado não foi encontrado.')
        confirmation_url = _whatsapp_confirmation_url(appointment_id)
        message = _confirmation_message(appointment, pattern, confirmation_url)
        if confirmation_url not in message:
            message += '\n\nClique abaixo para confirmar o agendamento:\n' + confirmation_url
        if settings['whatsapp_simplified']:
            try:
                result = send_baileys_text(current_company_id(), _whatsapp_phone(phone), message)
            except (ValueError, RuntimeError) as exc:
                log_sent_message(
                    'Whatzap', phone, message_code,
                    appointment_id=appointment_id, sent=False,
                    error_reason=str(exc), content=message,
                )
                return jsonify({'success': False, 'message': str(exc)}), 400
            clinic_phone = _clinic_cellphone()
            log_sent_message(
                'Whatzap', _whatsapp_phone(phone), message_code,
                appointment_id=appointment_id,
                message_id=result.get('messageId'), content=message,
            )
            _mark_confirmation_requested(appointment_id)
            return jsonify({
                'success': True,
                'mode': 'baileys',
                'clinic_phone': clinic_phone,
                'message': result.get('message') or 'Mensagem enviada pelo WhatsApp.',
            })
        sent, error = _send_confirmation_whatsapp(
            phone, appointment, settings, message_code=message_code,
            appointment_id=appointment_id, message=message,
        )
        if not sent:
            return jsonify({'success': False, 'message': error}), 400
        _mark_confirmation_requested(appointment_id)
        return jsonify({
            'success': True,
            'mode': 'business',
            'message': 'Solicitação enviada pelo WhatsApp Business.',
        })
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens', methods=['POST'])
def create_appointment():
    try:
        data = request.get_json(silent=True) or {}
        item = _appointment_data_from_request(data)
        appointment_id = agenda_repository.create(item)
        _update_patient_last_appointment(data.get('codpac'), item)
        return jsonify({
            'success': True,
            'message': 'Agenda de paciente incluída com sucesso.',
            'id': appointment_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>', methods=['PUT'])
def update_appointment(appointment_id):
    try:
        data = request.get_json(silent=True) or {}
        item = _appointment_data_from_request(data)
        previous = _appointment_schedule(appointment_id)
        schedule_changed = bool(previous) and (
            previous[0] != item['datacons'] or
            _format_time(previous[1]) != _format_time(item['horacons'])
        )
        had_successful_email = (
            schedule_changed and _has_successful_email_for_appointment(appointment_id)
        )
        updated = agenda_repository.update(appointment_id, item)
        if not updated:
            return jsonify({'success': False, 'message': 'Agenda de paciente não encontrada.'}), 404
        resend_notice = ''
        if schedule_changed and item.get('atend') != 'AT':
            _mark_appointment_rescheduled(appointment_id)
            if had_successful_email:
                sent, error = _send_rescheduled_confirmation(appointment_id)
                resend_notice = (
                    ' Novo e-mail de confirmação enviado com a data e o horário atualizados.'
                    if sent else
                    ' A agenda foi alterada, mas o novo e-mail não pôde ser enviado: ' + error
                )
        _update_patient_last_appointment(data.get('codpac'), item)
        return jsonify({
            'success': True,
            'message': 'Agenda de paciente alterada com sucesso.' + resend_notice,
        })
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>', methods=['DELETE'])
def delete_appointment(appointment_id):
    try:
        deleted = agenda_repository.delete(appointment_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Agenda de paciente não encontrada.'}), 404
        return jsonify({'success': True, 'message': 'Agenda de paciente excluída com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
