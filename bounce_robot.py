import email
import datetime
import imaplib
import logging
import re
import threading
from email import policy

from medsoft_core import get_db_connection


logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 60
_start_lock = threading.Lock()
_started = False


def _mailboxes():
    from email_robot import _company_configuration, _company_targets

    mailboxes = {}
    for company_id, database_name, _clinic_name in _company_targets():
        settings = _company_configuration(database_name, company_id)
        if not settings:
            continue
        host = (settings.get('smtp_host') or '').strip()
        user = (settings.get('smtp_user') or '').strip()
        password = settings.get('smtp_password') or ''
        if host and user and password:
            mailboxes[(database_name, host, user)] = {
                'database': database_name,
                'host': host,
                'user': user,
                'password': password,
            }
    return list(mailboxes.values())


def _header_message_ids(value):
    return re.findall(r'<[^<>\s]+@[^<>\s]+>', str(value or ''))


def _recipient(value):
    value = str(value or '').strip()
    if ';' in value:
        value = value.split(';', 1)[1].strip()
    match = re.search(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}', value, re.I)
    return match.group(0).lower() if match else ''


def _bounce_details(message):
    message_ids = set()
    recipients = set()
    diagnostics = []
    actions = []
    statuses = []

    for header in ('Original-Message-ID', 'X-Original-Message-ID', 'In-Reply-To', 'References'):
        message_ids.update(_header_message_ids(message.get(header)))

    sender = str(message.get('From') or '').lower()
    subject = str(message.get('Subject') or '').lower()
    looks_like_bounce = message.get_content_type() == 'multipart/report' or (
        'mailer-daemon' in sender
    ) or any(
        text in subject for text in (
            'undelivered', 'delivery status notification', 'mail delivery failed',
            'returned mail', 'falha na entrega', 'não entregue', 'nao entregue',
        )
    )
    if not looks_like_bounce:
        return None

    for part in message.walk():
        content_type = part.get_content_type()
        if content_type == 'message/delivery-status':
            blocks = part.get_payload()
            if not isinstance(blocks, list):
                blocks = [part]
            for block in blocks:
                for header in ('Original-Message-ID', 'X-Original-Message-ID'):
                    message_ids.update(_header_message_ids(block.get(header)))
                recipient = _recipient(
                    block.get('Final-Recipient') or block.get('Original-Recipient')
                )
                if recipient:
                    recipients.add(recipient)
                if block.get('Diagnostic-Code'):
                    diagnostics.append(str(block.get('Diagnostic-Code')))
                if block.get('Action'):
                    actions.append(str(block.get('Action')))
                if block.get('Status'):
                    statuses.append(str(block.get('Status')))
        elif content_type == 'message/rfc822':
            payload = part.get_payload()
            originals = payload if isinstance(payload, list) else []
            for original in originals:
                message_ids.update(_header_message_ids(original.get('Message-ID')))
                recipient = _recipient(original.get('To'))
                if recipient:
                    recipients.add(recipient)

    if actions or statuses:
        failed = any(value.lower() in ('failed', 'failure') for value in actions)
        permanent_status = any(value.startswith('5.') for value in statuses)
        if not (failed or permanent_status):
            return None
    elif not diagnostics:
        return None

    reason = diagnostics[0] if diagnostics else (
        'E-mail devolvido pelo servidor do destinatário.'
    )
    return {
        'message_ids': sorted(message_ids),
        'recipients': sorted(recipients),
        'reason': re.sub(r'\s+', ' ', reason).strip()[:100],
    }


def _update_log(database_name, details):
    connection = get_db_connection(database_name)
    try:
        with connection.cursor() as cursor:
            updated = []
            for message_id in details['message_ids']:
                cursor.execute('''
                    UPDATE public.medsoft_logmsgem
                    SET enviado = 'Não', motivoerro = %s
                    WHERE messageid = %s
                      AND tipo LIKE 'Email%%'
                      AND enviado = 'Sim'
                    RETURNING codigo
                ''', (details['reason'], message_id))
                updated.extend(row[0] for row in cursor.fetchall())
            if not updated:
                for recipient in details['recipients']:
                    cursor.execute('''
                        SELECT codigo
                        FROM public.medsoft_logmsgem
                        WHERE LOWER(destino) = %s
                          AND tipo LIKE 'Email%%'
                          AND enviado = 'Sim'
                          AND datahoraenvio >= (
                              CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                          ) - INTERVAL '7 days'
                        ORDER BY datahoraenvio DESC
                        LIMIT 2
                    ''', (recipient,))
                    candidates = [row[0] for row in cursor.fetchall()]
                    if len(candidates) == 1:
                        cursor.execute('''
                            UPDATE public.medsoft_logmsgem
                            SET enviado = 'Não', motivoerro = %s
                            WHERE codigo = %s
                            RETURNING codigo
                        ''', (details['reason'], candidates[0]))
                        updated.extend(row[0] for row in cursor.fetchall())
            connection.commit()
            return updated
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _process_mailbox(mailbox):
    client = imaplib.IMAP4_SSL(mailbox['host'], 993, timeout=20)
    try:
        client.login(mailbox['user'], mailbox['password'])
        updated_count = 0
        since = (datetime.date.today() - datetime.timedelta(days=7)).strftime('%d-%b-%Y')
        for folder in ('INBOX', 'INBOX.Junk', 'INBOX.spam'):
            status, _ = client.select(folder, readonly=True)
            if status != 'OK':
                continue
            status, data = client.search(None, 'SINCE', since)
            if status != 'OK' or not data:
                continue
            for message_number in data[0].split()[-200:]:
                status, payload = client.fetch(message_number, '(BODY.PEEK[])')
                if status != 'OK' or not payload or not isinstance(payload[0], tuple):
                    continue
                message = email.message_from_bytes(payload[0][1], policy=policy.default)
                details = _bounce_details(message)
                if details is None:
                    continue
                updated = _update_log(mailbox['database'], details)
                updated_count += len(updated)
                if updated:
                    logger.warning('Devolução de e-mail atualizou os logs %s.', updated)
        return updated_count
    finally:
        try:
            client.logout()
        except Exception:
            pass


def run_bounce_robot_once(app=None):
    total = 0
    for mailbox in _mailboxes():
        try:
            total += _process_mailbox(mailbox)
        except Exception:
            logger.exception('Falha ao consultar devoluções na conta %s.', mailbox['user'])
    return total


def _robot_loop(app, interval_seconds):
    while True:
        run_bounce_robot_once(app)
        threading.Event().wait(interval_seconds)


def start_bounce_robot(app, interval_seconds=POLL_INTERVAL_SECONDS):
    global _started
    with _start_lock:
        if _started:
            return False
        _started = True
        thread = threading.Thread(
            target=_robot_loop,
            args=(app, interval_seconds),
            name='medsoft-bounce-robot',
            daemon=True,
        )
        thread.start()
        logger.info(
            'Monitor de devoluções iniciado; intervalo de %s segundos.',
            interval_seconds,
        )
        return True
