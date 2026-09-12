import datetime
import logging
import math
import threading

from itsdangerous import URLSafeTimedSerializer

import config
from medsoft_core import get_db_connection


logger = logging.getLogger(__name__)
SAO_PAULO = datetime.timezone(datetime.timedelta(hours=-3), name='America/Sao_Paulo')
POLL_INTERVAL_SECONDS = 30
_start_lock = threading.Lock()
_started = False


def _now_sao_paulo():
    return datetime.datetime.now(SAO_PAULO).replace(tzinfo=None)


def _configuration_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('s', 'sim', '1', 'true', 't', 'yes', 'on')


def _company_targets():
    connection = get_db_connection(config.PG_DB)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT idempresa, COALESCE(NULLIF(database, ''), %s), COALESCE(nome, 'MedSoft')
                FROM public.ic_empresa_geral
                WHERE ativo IS TRUE
                ORDER BY idempresa
            ''', (config.PG_DB,))
            return [(int(row[0]), row[1], row[2]) for row in cursor.fetchall()]
    finally:
        connection.close()


def _agenda_confirmation_enabled(company_id):
    connection = get_db_connection(config.PG_DB)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT COALESCE(plano.confagenda, 'N')
                FROM public.ic_empresa_geral empresa
                LEFT JOIN public.ic_plano_geral plano ON plano.idplano = empresa.idplano
                WHERE empresa.idempresa = %s
                  AND empresa.ativo IS TRUE
                LIMIT 1
            ''', (company_id,))
            row = cursor.fetchone()
        return bool(row) and _configuration_bool(row[0])
    finally:
        connection.close()


def _company_configuration(database_name, company_id):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT smtp_host, smtp_porta, smtp_usuario, smtp_senha,
                       smtp_remetente, smtp_tls, smtp_ssl,
                       autlembraagendaemail, textolembraagendaemail,
                       autlembraniveremail, textolembraniveremail
                FROM public.medsoft_configuracao
                WHERE CAST(codclin AS TEXT) = %s
                LIMIT 1
            ''', (str(company_id),))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'smtp_host': row[0] or '',
                'smtp_port': int(row[1] or 0),
                'smtp_user': row[2] or '',
                'smtp_password': row[3] or '',
                'smtp_from': row[4] or '',
                'smtp_tls': _configuration_bool(row[5]),
                'smtp_ssl': _configuration_bool(row[6]),
                'minutes': row[7],
                'message_code': row[8],
                'birthday_minutes': row[9],
                'birthday_message_code': row[10],
            }
    finally:
        connection.close()


def _message_template(database_name, company_id, message_code):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT texto, COALESCE(msghtml, FALSE)
                FROM public.texto
                WHERE codigo = %s AND codclin = %s
                LIMIT 1
            ''', (message_code, company_id))
            row = cursor.fetchone()
            return ((row[0] or '').strip(), bool(row[1])) if row else ('', False)
    finally:
        connection.close()


def _appointments(database_name, company_id, start_date, end_date):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT a.codagend, a.datacons, a.horacons, a.nomepaci, a.nomed,
                       a.proced, COALESCE(NULLIF(BTRIM(a.email), ''), p.email, '')
                FROM public.agenda a
                LEFT JOIN LATERAL (
                    SELECT COALESCE(email, '') AS email
                    FROM public.pacient
                    WHERE UPPER(BTRIM(nomecli)) = UPPER(BTRIM(a.nomepaci))
                      AND codclin = a.codclin
                    ORDER BY codcli
                    LIMIT 1
                ) p ON TRUE
                WHERE a.codclin = %s
                  AND a.datacons BETWEEN %s AND %s
                  AND COALESCE(a.atend, '') <> 'CO'
                ORDER BY a.datacons, a.horacons, a.codagend
            ''', (company_id, start_date, end_date))
            return cursor.fetchall()
    finally:
        connection.close()


def _appointment(database_name, company_id, appointment_id):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT a.codagend, a.datacons, a.horacons, a.nomepaci, a.nomed,
                       a.proced, COALESCE(NULLIF(BTRIM(a.email), ''), p.email, '')
                FROM public.agenda a
                LEFT JOIN LATERAL (
                    SELECT COALESCE(email, '') AS email
                    FROM public.pacient
                    WHERE UPPER(BTRIM(nomecli)) = UPPER(BTRIM(a.nomepaci))
                      AND codclin = a.codclin
                    ORDER BY codcli
                    LIMIT 1
                ) p ON TRUE
                WHERE a.codclin = %s AND a.codagend = %s
                  AND COALESCE(a.atend, '') NOT IN ('CO', 'AT')
                LIMIT 1
            ''', (company_id, appointment_id))
            return cursor.fetchone()
    finally:
        connection.close()


def _mark_confirmation_requested(database_name, company_id, appointment_id):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE public.agenda
                SET atend = 'SC'
                WHERE codclin = %s AND codagend = %s
                  AND COALESCE(atend, '') NOT IN ('CO', 'AT')
            ''', (company_id, appointment_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _birthday_patients(database_name, company_id):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT codcli, COALESCE(nomecli, ''), datanasc_, COALESCE(email, '')
                FROM public.pacient
                WHERE codclin = %s
                  AND datanasc_ IS NOT NULL
                  AND NULLIF(BTRIM(COALESCE(email, '')), '') IS NOT NULL
                ORDER BY codcli
            ''', (company_id,))
            return cursor.fetchall()
    finally:
        connection.close()


def _birthday_in_year(birth_date, year):
    try:
        return birth_date.replace(year=year)
    except ValueError:
        # Em anos não bissextos, aniversários de 29/02 são lembrados em 28/02.
        return datetime.date(year, 2, 28)


def _next_birthday(birth_date, reference_date):
    birthday = _birthday_in_year(birth_date, reference_date.year)
    if birthday < reference_date:
        birthday = _birthday_in_year(birth_date, reference_date.year + 1)
    return birthday


def _claim_birthday(
        database_name, company_id, patient_id, email, message_code, window_start):
    connection = get_db_connection(database_name)
    cursor = connection.cursor()
    lock_id = -abs(int(patient_id))
    cursor.execute('SELECT pg_try_advisory_lock(%s, %s)', (company_id, lock_id))
    if not cursor.fetchone()[0]:
        cursor.close()
        connection.close()
        return None
    cursor.execute('''
        SELECT EXISTS (
            SELECT 1
            FROM public.medsoft_logmsgem
            WHERE codclin = %s
              AND codagend IS NULL
              AND mensagem = %s
              AND LOWER(BTRIM(destino)) = LOWER(BTRIM(%s))
              AND tipo = 'Email Auto'
              AND datahoraenvio >= %s
              AND (
                    COALESCE(enviado, 'Sim') = 'Sim'
                    OR (
                        enviado = 'Não'
                        AND datahoraenvio >= (
                            CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                        ) - INTERVAL '5 minutes'
                    )
              )
        )
    ''', (company_id, message_code, email, window_start))
    if cursor.fetchone()[0]:
        cursor.execute('SELECT pg_advisory_unlock(%s, %s)', (company_id, lock_id))
        cursor.close()
        connection.close()
        return None
    cursor.close()
    return connection


def _release_birthday(connection, company_id, patient_id):
    _release_appointment(connection, company_id, -abs(int(patient_id)))


def _confirmation_url(app, database_name, company_id, appointment_id):
    token = URLSafeTimedSerializer(app.secret_key).dumps({
        'appointment_id': int(appointment_id),
        'database': database_name,
        'idempresa': int(company_id),
    }, salt='medsoft-appointment-confirmation')
    return (config.PUBLIC_URL or 'http://localhost:8072') + '/confirmar-agendamento/' + token


def _claim_appointment(database_name, company_id, appointment_id):
    connection = get_db_connection(database_name)
    cursor = connection.cursor()
    cursor.execute('SELECT pg_try_advisory_lock(%s, %s)', (company_id, appointment_id))
    if not cursor.fetchone()[0]:
        cursor.close()
        connection.close()
        return None
    cursor.execute('''
        SELECT EXISTS (
            SELECT 1
            FROM public.medsoft_logmsgem
            WHERE codclin = %s
              AND codagend = %s
              AND datahoraenvio >= COALESCE(
                    (SELECT datatualiza FROM public.agenda
                     WHERE codclin = %s AND codagend = %s),
                    TIMESTAMP '1900-01-01'
              )
              AND tipo IN ('Email Auto', 'Email Manual', 'Email')
              AND (
                    COALESCE(enviado, 'Sim') = 'Sim'
                    OR (
                        enviado = 'Não'
                        AND datahoraenvio >= (
                            CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                        ) - INTERVAL '5 minutes'
                    )
              )
        )
    ''', (company_id, appointment_id, company_id, appointment_id))
    if cursor.fetchone()[0]:
        cursor.execute('SELECT pg_advisory_unlock(%s, %s)', (company_id, appointment_id))
        cursor.close()
        connection.close()
        return None
    cursor.close()
    return connection


def _release_appointment(connection, company_id, appointment_id):
    if connection is None:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s, %s)', (company_id, appointment_id))
    finally:
        connection.close()


def _process_company(app, database_name, company_id, clinic_name, now):
    from agenda_api import (
        _confirmation_message,
        _format_time,
        _parse_schedule_time,
        _send_confirmation_email,
    )

    if not _agenda_confirmation_enabled(company_id):
        logger.info(
            'Confirmação automática de agenda desabilitada pelo plano da empresa %s.',
            company_id,
        )
        return 0

    automation = _company_configuration(database_name, company_id)
    if not automation or automation['minutes'] is None or automation['message_code'] is None:
        return 0
    minutes = max(0, int(automation['minutes']))
    message_code = int(automation['message_code'])
    template_record = _message_template(database_name, company_id, message_code)
    if isinstance(template_record, tuple):
        template, message_html = template_record
    else:
        # Compatibilidade com integrações antigas que fornecem apenas o texto.
        template, message_html = template_record, None
    end_date = now.date() + datetime.timedelta(days=max(1, math.ceil(minutes / 1440) + 1))
    rows = _appointments(database_name, company_id, now.date(), end_date)
    sent_count = 0

    for row in rows:
        appointment_time = _parse_schedule_time(row[2])
        if not appointment_time:
            continue
        appointment_at = datetime.datetime.combine(row[1], appointment_time)
        send_at = appointment_at - datetime.timedelta(minutes=minutes)
        if now < send_at or now >= appointment_at:
            continue
        appointment_id = int(row[0])
        email = (row[6] or '').strip()
        lock_connection = _claim_appointment(database_name, company_id, appointment_id)
        if lock_connection is None:
            continue
        try:
            # A agenda pode ser alterada entre a listagem do ciclo e o envio.
            # Recarrega o registro sob a trava para usar sempre data e hora atuais.
            row = _appointment(database_name, company_id, appointment_id)
            if not row:
                continue
            appointment_time = _parse_schedule_time(row[2])
            if not appointment_time:
                continue
            appointment_at = datetime.datetime.combine(row[1], appointment_time)
            send_at = appointment_at - datetime.timedelta(minutes=minutes)
            if now < send_at or now >= appointment_at:
                continue
            email = (row[6] or '').strip()
            appointment = {
                'data': row[1],
                'hora': _format_time(row[2]),
                'paciente': row[3] or '',
                'profissional': row[4] or '',
                'procedimento': row[5] or 'Consulta',
                'nomeclinica': clinic_name or 'MedSoft',
            }
            confirmation_url = _confirmation_url(
                app, database_name, company_id, appointment_id
            )
            message = _confirmation_message(
                appointment, template, confirmation_url, html_mode=message_html
            )
            with app.app_context():
                sent, error = _send_confirmation_email(
                    email, appointment, automation, message, confirmation_url,
                    message_code=message_code,
                    company_id=company_id,
                    message_type='Email Auto',
                    appointment_id=appointment_id,
                    database_name=database_name,
                    html_mode=message_html,
                )
            if sent:
                _mark_confirmation_requested(
                    database_name, company_id, appointment_id
                )
                sent_count += 1
                logger.info(
                    'E-mail automático enviado para o agendamento %s da clínica %s.',
                    appointment_id, company_id,
                )
            else:
                logger.warning(
                    'Falha no e-mail automático do agendamento %s: %s',
                    appointment_id, error,
                )
        finally:
            _release_appointment(lock_connection, company_id, appointment_id)
    return sent_count


def _process_birthdays(app, database_name, company_id, clinic_name, now):
    from agenda_api import _confirmation_message, _send_confirmation_email

    automation = _company_configuration(database_name, company_id)
    if not automation:
        return 0
    configured_minutes = automation.get('birthday_minutes')
    configured_message = automation.get('birthday_message_code')
    if configured_minutes is None or configured_message is None:
        return 0

    minutes = max(0, int(configured_minutes))
    message_code = int(configured_message)
    template_record = _message_template(database_name, company_id, message_code)
    if isinstance(template_record, tuple):
        template, message_html = template_record
    else:
        template, message_html = template_record, None
    if not template:
        return 0

    sent_count = 0
    for patient_id, patient_name, birth_date, email in _birthday_patients(
            database_name, company_id):
        if isinstance(birth_date, datetime.datetime):
            birth_date = birth_date.date()
        if not isinstance(birth_date, datetime.date):
            continue
        birthday_date = _next_birthday(birth_date, now.date())
        birthday_at = datetime.datetime.combine(birthday_date, datetime.time.min)
        window_start = birthday_at - datetime.timedelta(minutes=minutes)
        window_end = (
            birthday_at if minutes > 0
            else birthday_at + datetime.timedelta(days=1)
        )
        if now < window_start or now >= window_end:
            continue

        destination = (email or '').strip()
        lock_connection = _claim_birthday(
            database_name, company_id, patient_id, destination,
            message_code, window_start,
        )
        if lock_connection is None:
            continue
        try:
            message_context = {
                'data': birthday_date,
                'hora': '',
                'paciente': patient_name or '',
                'profissional': '',
                'procedimento': 'aniversário',
                'nomeclinica': clinic_name or 'MedSoft',
            }
            message = _confirmation_message(
                message_context, template, html_mode=message_html
            )
            with app.app_context():
                sent, error = _send_confirmation_email(
                    destination,
                    message_context,
                    automation,
                    message,
                    subject='Feliz aniversário, {}!'.format(patient_name or 'paciente'),
                    message_code=message_code,
                    company_id=company_id,
                    message_type='Email Auto',
                    appointment_id=None,
                    database_name=database_name,
                    html_mode=message_html,
                )
            if sent:
                sent_count += 1
                logger.info(
                    'E-mail de aniversário enviado para o paciente %s da clínica %s.',
                    patient_id, company_id,
                )
            else:
                logger.warning(
                    'Falha no e-mail de aniversário do paciente %s: %s',
                    patient_id, error,
                )
        finally:
            _release_birthday(lock_connection, company_id, patient_id)
    return sent_count


def run_email_robot_once(app, now=None):
    now = now or _now_sao_paulo()
    total = 0
    for company_id, database_name, clinic_name in _company_targets():
        try:
            total += _process_company(
                app, database_name, company_id, clinic_name, now
            )
            total += _process_birthdays(
                app, database_name, company_id, clinic_name, now
            )
        except Exception:
            logger.exception(
                'Falha no ciclo do robô de e-mail da clínica %s.', company_id
            )
    return total


def _robot_loop(app, interval_seconds):
    while True:
        try:
            run_email_robot_once(app)
        except Exception:
            logger.exception('Falha no ciclo geral do robô de e-mail.')
        threading.Event().wait(interval_seconds)


def start_email_robot(app, interval_seconds=POLL_INTERVAL_SECONDS):
    global _started
    with _start_lock:
        if _started:
            return False
        _started = True
        thread = threading.Thread(
            target=_robot_loop,
            args=(app, interval_seconds),
            name='medsoft-email-robot',
            daemon=True,
        )
        thread.start()
        logger.info('Robô de e-mail iniciado; intervalo de %s segundos.', interval_seconds)
        return True
