import datetime
import re
from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, session

from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import current_company_id
from baileys_api import _patient_whatsapp_contacts, _phone_variants


mensagens_api_bp = Blueprint('mensagens_api', __name__)
PAGE_SIZE = 50


def _database_name():
    return session.get('db_path') or None


@contextmanager
def _connection():
    connection = get_db_connection(_database_name())
    try:
        yield connection
    finally:
        connection.close()


def _date_value(value, label):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError('{} inválida.'.format(label)) from exc


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    current_app.logger.exception('Falha ao consultar mensagens enviadas.', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro ao consultar mensagens enviadas.'}), 500


def _display_message_content(content):
    content = str(content or '').strip()
    legacy_template = bool(re.search(
        r'\{(?:paciente|procedimento|data|hora|profissional|clinica|url)\}',
        content,
        flags=re.IGNORECASE,
    ))
    return '' if legacy_template else content, legacy_template or not content


@mensagens_api_bp.get('/api/crm/whatsapp/conversas')
def whatsapp_conversations():
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    ALTER TABLE public.medsoft_logmsgem
                    ADD COLUMN IF NOT EXISTS conteudo TEXT NULL
                ''')
                cursor.execute('''
                    ALTER TABLE public.medsoft_logmsgem
                    ADD COLUMN IF NOT EXISTS nomecontato VARCHAR(255) NULL
                ''')
                cursor.execute(r'''
                    WITH logs AS (
                        SELECT l.destino,
                               REGEXP_REPLACE(COALESCE(l.destino, ''), '\D', '', 'g') AS digits,
                               MAX(l.datahoraenvio) AS ultima_data,
                               COUNT(*) AS total,
                               COUNT(*) FILTER (WHERE COALESCE(l.enviado, 'Sim') = 'Não') AS falhas
                        FROM public.medsoft_logmsgem l
                        WHERE l.codclin = %s AND l.tipo = 'Whatzap'
                        GROUP BY l.destino
                    )
                    SELECT logs.destino, logs.ultima_data, logs.total, logs.falhas,
                           COALESCE(NULLIF(p.nomecli, ''), NULLIF(last_log.nomecontato, ''), ''),
                           COALESCE(last_log.conteudo, ''),
                           COALESCE(last_log.enviado, 'Sim')
                    FROM logs
                    LEFT JOIN LATERAL (
                        SELECT nomecli
                        FROM public.pacient
                        WHERE codclin = %s
                          AND REGEXP_REPLACE(COALESCE(telres, ''), '\D', '', 'g') IN (
                              logs.digits,
                              CASE WHEN logs.digits LIKE '55%%' THEN SUBSTRING(logs.digits FROM 3) ELSE logs.digits END
                          )
                        ORDER BY codcli LIMIT 1
                    ) p ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT conteudo, enviado, nomecontato
                        FROM public.medsoft_logmsgem l2
                        WHERE l2.codclin = %s AND l2.tipo = 'Whatzap'
                          AND l2.destino IS NOT DISTINCT FROM logs.destino
                        ORDER BY l2.datahoraenvio DESC NULLS LAST, l2.codigo DESC
                        LIMIT 1
                    ) last_log ON TRUE
                    ORDER BY logs.ultima_data DESC NULLS LAST
                    LIMIT 200
                ''', (current_company_id(), current_company_id(), current_company_id()))
                rows = cursor.fetchall()
            connection.commit()
        patient_names = {}
        for contact in _patient_whatsapp_contacts(current_company_id()):
            for phone_key in _phone_variants(contact.get('phone')):
                patient_names[phone_key] = contact.get('name') or ''
        conversations = []
        for row in rows:
            preview, legacy = _display_message_content(row[5])
            patient_name = row[4] or ''
            if not patient_name:
                for phone_key in _phone_variants(row[0]):
                    if patient_names.get(phone_key):
                        patient_name = patient_names[phone_key]
                        break
            conversations.append({
                'destino': row[0] or '',
                'ultima_data': row[1].isoformat(timespec='seconds') if row[1] else '',
                'total': row[2] or 0,
                'falhas': row[3] or 0,
                'paciente': patient_name,
                'ultima_mensagem': preview,
                'registro_legado': legacy,
                'enviado': row[6] or 'Sim',
            })
        return jsonify({'success': True, 'conversas': conversations})
    except Exception as exc:
        return _error_response(exc)


@mensagens_api_bp.post('/api/crm/whatsapp/historico')
def whatsapp_conversation_history():
    try:
        data = request.get_json(silent=True) or {}
        destination = str(data.get('destino') or '').strip()
        if not destination or len(destination) > 255:
            raise ValueError('Conversa inválida.')
        destination_digits = ''.join(character for character in destination if character.isdigit())
        alternate_digits = (
            destination_digits[2:] if destination_digits.startswith('55')
            else '55' + destination_digits
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    ALTER TABLE public.medsoft_logmsgem
                    ADD COLUMN IF NOT EXISTS conteudo TEXT NULL
                ''')
                cursor.execute('''
                    ALTER TABLE public.medsoft_logmsgem
                    ADD COLUMN IF NOT EXISTS direcao VARCHAR(10) NULL
                ''')
                cursor.execute(r'''
                    SELECT codigo, datahoraenvio, destino, COALESCE(conteudo, ''),
                           COALESCE(enviado, 'Sim'), COALESCE(motivoerro, ''),
                           COALESCE(messageid, ''), codagend, COALESCE(direcao, 'saida')
                    FROM public.medsoft_logmsgem
                    WHERE codclin = %s AND tipo = 'Whatzap'
                      AND REGEXP_REPLACE(COALESCE(destino, ''), '\D', '', 'g') IN (%s, %s)
                    ORDER BY datahoraenvio ASC NULLS LAST, codigo ASC
                    LIMIT 500
                ''', (current_company_id(), destination_digits, alternate_digits))
                rows = cursor.fetchall()
            connection.commit()
        messages = []
        for row in rows:
            content, legacy = _display_message_content(row[3])
            messages.append({
                'codigo': row[0],
                'datahora': row[1].isoformat(timespec='seconds') if row[1] else '',
                'destino': row[2] or '',
                'conteudo': content,
                'registro_legado': legacy,
                'enviado': row[4] or 'Sim',
                'motivoerro': row[5] or '',
                'messageid': row[6] or '',
                'codagenda': row[7],
                'direcao': row[8] or 'saida',
            })
        return jsonify({'success': True, 'mensagens': messages})
    except Exception as exc:
        return _error_response(exc)


@mensagens_api_bp.get('/api/crm/email/conversas')
def email_conversations():
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    ALTER TABLE public.medsoft_logmsgem
                    ADD COLUMN IF NOT EXISTS conteudo TEXT NULL
                ''')
                cursor.execute('''
                    WITH logs AS (
                        SELECT l.destino, MAX(l.datahoraenvio) AS ultima_data,
                               COUNT(*) AS total,
                               COUNT(*) FILTER (WHERE COALESCE(l.enviado, 'Sim') = 'Não') AS falhas
                        FROM public.medsoft_logmsgem l
                        WHERE l.codclin = %s AND l.tipo IN ('Email', 'Email Auto', 'Email Manual')
                        GROUP BY l.destino
                    )
                    SELECT logs.destino, logs.ultima_data, logs.total, logs.falhas,
                           COALESCE(p.nomecli, ''), COALESCE(last_log.conteudo, ''),
                           COALESCE(last_log.enviado, 'Sim')
                    FROM logs
                    LEFT JOIN LATERAL (
                        SELECT nomecli FROM public.pacient
                        WHERE codclin = %s
                          AND LOWER(BTRIM(COALESCE(email, ''))) = LOWER(BTRIM(logs.destino))
                        ORDER BY codcli LIMIT 1
                    ) p ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT conteudo, enviado FROM public.medsoft_logmsgem l2
                        WHERE l2.codclin = %s
                          AND l2.tipo IN ('Email', 'Email Auto', 'Email Manual')
                          AND l2.destino IS NOT DISTINCT FROM logs.destino
                        ORDER BY l2.datahoraenvio DESC NULLS LAST, l2.codigo DESC LIMIT 1
                    ) last_log ON TRUE
                    ORDER BY logs.ultima_data DESC NULLS LAST LIMIT 200
                ''', (current_company_id(), current_company_id(), current_company_id()))
                rows = cursor.fetchall()
            connection.commit()
        return jsonify({'success': True, 'conversas': [{
            'destino': row[0] or '',
            'ultima_data': row[1].isoformat(timespec='seconds') if row[1] else '',
            'total': row[2] or 0,
            'falhas': row[3] or 0,
            'paciente': row[4] or '',
            'ultima_mensagem': row[5] or '',
            'enviado': row[6] or 'Sim',
        } for row in rows]})
    except Exception as exc:
        return _error_response(exc)


@mensagens_api_bp.post('/api/crm/email/historico')
def email_conversation_history():
    try:
        data = request.get_json(silent=True) or {}
        destination = str(data.get('destino') or '').strip()
        if not destination or len(destination) > 255:
            raise ValueError('Conversa inválida.')
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    ALTER TABLE public.medsoft_logmsgem
                    ADD COLUMN IF NOT EXISTS conteudo TEXT NULL
                ''')
                cursor.execute('''
                    SELECT codigo, datahoraenvio, destino, COALESCE(conteudo, ''),
                           COALESCE(enviado, 'Sim'), COALESCE(motivoerro, ''),
                           COALESCE(messageid, ''), codagend, tipo
                    FROM public.medsoft_logmsgem
                    WHERE codclin = %s AND tipo IN ('Email', 'Email Auto', 'Email Manual')
                      AND destino = %s
                    ORDER BY datahoraenvio ASC NULLS LAST, codigo ASC LIMIT 500
                ''', (current_company_id(), destination))
                rows = cursor.fetchall()
            connection.commit()
        return jsonify({'success': True, 'mensagens': [{
            'codigo': row[0],
            'datahora': row[1].isoformat(timespec='seconds') if row[1] else '',
            'destino': row[2] or '',
            'conteudo': row[3] or '',
            'enviado': row[4] or 'Sim',
            'motivoerro': row[5] or '',
            'messageid': row[6] or '',
            'codagenda': row[7],
            'tipo': row[8] or 'Email',
            'direcao': 'saida',
        } for row in rows]})
    except Exception as exc:
        return _error_response(exc)


@mensagens_api_bp.get('/api/agenda/itens/<int:appointment_id>/mensagens-whatsapp')
def appointment_whatsapp_messages(appointment_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    SELECT l.codigo, l.datahoraenvio, l.destino,
                           COALESCE(NULLIF(l.conteudo, ''), ''),
                           COALESCE(t.nome, ''), COALESCE(l.enviado, 'Sim'),
                           COALESCE(l.motivoerro, ''), COALESCE(l.messageid, '')
                    FROM public.medsoft_logmsgem l
                    LEFT JOIN public.texto t
                      ON t.codigo = l.mensagem AND t.codclin = l.codclin
                    WHERE l.codclin = %s AND l.codagend = %s AND l.tipo = 'Whatzap'
                    ORDER BY l.datahoraenvio DESC NULLS LAST, l.codigo DESC
                ''', (current_company_id(), appointment_id))
                rows = cursor.fetchall()
            connection.commit()
        messages = []
        for row in rows:
            content = row[3] or ''
            # Versões antigas chegaram a gravar o modelo ainda não preenchido.
            # Não o apresenta como se fosse o texto efetivamente enviado.
            display_content, legacy_template = _display_message_content(content)
            messages.append({
                'codigo': row[0],
                'datahoraenvio': row[1].isoformat(timespec='seconds') if row[1] else '',
                'destino': row[2] or '',
                'conteudo': display_content,
                'conteudo_armazenado': bool(content) and not legacy_template,
                'registro_legado': legacy_template or not content,
                'mensagem_nome': row[4] or '',
                'enviado': row[5] or 'Sim',
                'motivoerro': row[6] or '',
                'messageid': row[7] or '',
            })
        return jsonify({'success': True, 'mensagens': messages})
    except Exception as exc:
        return _error_response(exc)


@mensagens_api_bp.route('/api/mensagens-enviadas', methods=['POST'])
def list_sent_messages():
    try:
        data = request.get_json(silent=True) or {}
        start_date = _date_value(data.get('data_inicial'), 'Data inicial')
        end_date = _date_value(data.get('data_final'), 'Data final')
        if start_date and end_date and start_date > end_date:
            raise ValueError('A data inicial não pode ser maior que a data final.')
        message_type = (data.get('tipo') or '').strip()
        if message_type not in ('', 'Email', 'Email Auto', 'Email Manual', 'Whatzap'):
            raise ValueError('Tipo de mensagem inválido.')
        destination = (data.get('destino') or '').strip()
        if len(destination) > 255:
            raise ValueError('O destino deve ter no máximo 255 caracteres.')
        try:
            page = max(1, int(data.get('pagina') or 1))
        except (TypeError, ValueError) as exc:
            raise ValueError('Página inválida.') from exc

        conditions = ['l.codclin = %s']
        parameters = [current_company_id()]
        if start_date:
            conditions.append('l.datahoraenvio >= %s')
            parameters.append(start_date)
        if end_date:
            conditions.append("l.datahoraenvio < %s + INTERVAL '1 day'")
            parameters.append(end_date)
        if message_type:
            conditions.append('l.tipo = %s')
            parameters.append(message_type)
        if destination:
            conditions.append('l.destino ILIKE %s')
            parameters.append('%' + destination + '%')
        where_clause = ' AND '.join(conditions)

        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT COUNT(*) FROM public.medsoft_logmsgem l WHERE ' + where_clause,
                    tuple(parameters),
                )
                total = cursor.fetchone()[0]
                total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
                page = min(page, total_pages)
                cursor.execute('''
                    SELECT l.codigo, l.datahoraenvio, l.tipo, l.destino,
                           l.mensagem, COALESCE(t.nome, ''),
                           COALESCE(l.enviado, 'Sim'), COALESCE(l.motivoerro, ''),
                           l.codagend, a.datacons
                    FROM public.medsoft_logmsgem l
                    LEFT JOIN public.texto t
                      ON t.codigo = l.mensagem
                     AND t.codclin = l.codclin
                    LEFT JOIN public.agenda a
                      ON a.codagend = l.codagend
                     AND a.codclin = l.codclin
                    WHERE {}
                    ORDER BY l.datahoraenvio DESC NULLS LAST, l.codigo DESC
                    LIMIT %s OFFSET %s
                '''.format(where_clause), tuple(parameters) + (
                    PAGE_SIZE, (page - 1) * PAGE_SIZE
                ))
                rows = cursor.fetchall()

        messages = [{
            'codigo': row[0],
            'datahoraenvio': row[1].isoformat(timespec='seconds') if row[1] else '',
            'tipo': row[2] or '',
            'destino': row[3] or '',
            'mensagem': row[4],
            'mensagem_nome': row[5] or '',
            'enviado': row[6] or 'Sim',
            'motivoerro': row[7] or '',
            'codagenda': row[8],
            'agenda_data': row[9].isoformat() if row[9] else '',
        } for row in rows]
        return jsonify({
            'success': True,
            'mensagens': messages,
            'pagina': page,
            'por_pagina': PAGE_SIZE,
            'total': total,
            'total_paginas': total_pages,
        })
    except Exception as exc:
        return _error_response(exc)


@mensagens_api_bp.route('/api/mensagens-enviadas/destinatario-paciente', methods=['POST'])
def find_message_recipient_patient():
    try:
        data = request.get_json(silent=True) or {}
        destination = str(data.get('destino') or '').strip()
        message_type = str(data.get('tipo') or '').strip()
        if not destination or destination.lower() in ('não informado', 'nao informado'):
            raise ValueError('Esta mensagem não possui destinatário informado.')
        if len(destination) > 255:
            raise ValueError('Destinatário inválido.')

        is_email = message_type != 'Whatzap' or '@' in destination
        with _connection() as connection:
            with connection.cursor() as cursor:
                if is_email:
                    cursor.execute('''
                        SELECT codcli, nomecli
                        FROM public.pacient
                        WHERE codclin = %s
                          AND LOWER(BTRIM(COALESCE(email, ''))) = LOWER(BTRIM(%s))
                        ORDER BY codcli
                        LIMIT 1
                    ''', (current_company_id(), destination))
                else:
                    digits = re.sub(r'\D', '', destination)
                    local_digits = (
                        digits[2:]
                        if digits.startswith('55') and len(digits) in (12, 13)
                        else digits
                    )
                    cursor.execute(r'''
                        SELECT codcli, nomecli
                        FROM public.pacient
                        WHERE codclin = %s
                          AND REGEXP_REPLACE(COALESCE(telres, ''), '\D', '', 'g') IN (%s, %s)
                        ORDER BY codcli
                        LIMIT 1
                    ''', (current_company_id(), digits, local_digits))
                patient = cursor.fetchone()

        if not patient:
            return jsonify({
                'success': False,
                'message': 'Nenhum paciente foi encontrado para este destinatário.',
            }), 404
        return jsonify({
            'success': True,
            'paciente': {'codcli': patient[0], 'nomecli': patient[1] or ''},
        })
    except Exception as exc:
        return _error_response(exc)
