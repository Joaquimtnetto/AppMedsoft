import logging

from flask import has_request_context, session

from medsoft_core import get_db_connection


logger = logging.getLogger(__name__)


def _database_name():
    if has_request_context():
        return session.get('db_path') or None
    return None


def _company_id():
    if not has_request_context():
        return None
    value = session.get('idempresa') or session.get('codclin')
    try:
        return int(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def log_sent_message(
        message_type, destination, message_code=None, company_id=None,
        appointment_id=None, database_name=None, sent=True, error_reason='',
        message_id=None, content=None):
    """Registra o resultado de uma tentativa sem alterar o fluxo do envio."""
    destination = str(destination or '').strip()
    if not destination:
        destination = 'Não informado'
    sent_value = 'Sim' if sent else 'Não'
    error_reason = str(error_reason or '').strip()[:100] or None
    message_id = str(message_id or '').strip()[:255] or None
    content = str(content or '').strip() or None
    if message_code in (None, ''):
        message_code = None
    else:
        try:
            message_code = int(message_code)
        except (TypeError, ValueError):
            logger.warning('Log de mensagem ignorado: código inválido %r.', message_code)
            return False

    connection = None
    try:
        company_id = company_id if company_id is not None else _company_id()
        connection = get_db_connection(database_name or _database_name())
        with connection.cursor() as cursor:
            cursor.execute('''
                ALTER TABLE public.medsoft_logmsgem
                ADD COLUMN IF NOT EXISTS conteudo TEXT NULL
            ''')
            cursor.execute('''
                INSERT INTO public.medsoft_logmsgem
                    (datahoraenvio, tipo, destino, mensagem, codclin, codagend,
                     enviado, motivoerro, messageid, conteudo)
                VALUES (
                    CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo',
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            ''', (
                message_type, destination, message_code, company_id, appointment_id,
                sent_value, error_reason, message_id, content,
            ))
        connection.commit()
        return True
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception('Mensagem enviada, mas não foi possível gravar medsoft_logmsgem.')
        return False
    finally:
        if connection is not None:
            connection.close()
