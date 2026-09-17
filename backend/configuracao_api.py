import re
import smtplib
import socket
import ssl
from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, session

from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import current_company_id


configuracao_api_bp = Blueprint('configuracao_api', __name__)


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


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    current_app.logger.exception('Falha na configuração', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


def _table_exists(cursor):
    cursor.execute("SELECT to_regclass('public.medsoft_configuracao')")
    return cursor.fetchone()[0] is not None


def _column_exists(cursor, column_name):
    cursor.execute('''
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'medsoft_configuracao'
              AND column_name = %s
        )
    ''', (column_name,))
    return bool(cursor.fetchone()[0])


def _columns(cursor, table_name):
    cursor.execute('''
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
    ''', (table_name,))
    return {row[0] for row in cursor.fetchall()}


def _column_types(cursor, table_name):
    cursor.execute('''
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
    ''', (table_name,))
    return {row[0]: row[1] for row in cursor.fetchall()}


def _company_parameter():
    return str(current_company_id())


def _ensure_simplified_column(cursor):
    cursor.execute('''
        ALTER TABLE public.medsoft_configuracao
        ADD COLUMN IF NOT EXISTS whatzapsimplificado VARCHAR(1) NOT NULL DEFAULT 'N'
    ''')


AUTOMATION_FIELDS = (
    'autlembraagendaemail',
    'autlembraretagendaemail',
    'autlembraniveremail',
    'autlembraeventemail',
    'textolembraagendaemail',
    'textolembraretagendaemail',
    'textolembraniveremail',
    'textolembraeventemail',
    'autlembraagendawhatzap',
    'autlembraretagendawhatzap',
    'autlembraniverwahtzap',
    'autlembraeventowahtzap',
    'textolembraagendawahtzap',
    'textolembraretagendawahtzap',
    'textolembraniverwahtzap',
    'textolembraeventwahtzap',
)


def _as_bool(value):
    return value is True or str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _row_bool(value):
    return value is True or str(value or '').strip().lower() in ('s', 'sim', '1', 'true', 't', 'yes', 'on')


def _db_bool(value, column_name, column_types):
    if column_types.get(column_name) == 'boolean':
        return bool(value)
    return 'S' if value else 'N'


def _as_nullable_int(value, label):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('{} inválido.'.format(label)) from exc


def _as_nullable_minutes(value, label):
    minutes = _as_nullable_int(value, label)
    if minutes is not None and minutes < 0:
        raise ValueError('{} deve ser igual ou maior que zero.'.format(label))
    return minutes


def _automation_values(data):
    return {
        'autlembraagendaemail': _as_nullable_minutes(data.get('autlembraagendaemail'), 'Agendamento Email (Tempo em Minutos)'),
        'autlembraretagendaemail': _as_nullable_minutes(data.get('autlembraretagendaemail'), 'Retorno agendamento Email (Tempo em Minutos)'),
        'autlembraniveremail': _as_nullable_minutes(data.get('autlembraniveremail'), 'Lembra Aniversário Email (Tempo em Minutos)'),
        'autlembraeventemail': _as_nullable_minutes(data.get('autlembraeventemail'), 'Lembra Evento Email (Tempo em Minutos)'),
        'textolembraagendaemail': _as_nullable_int(data.get('textolembraagendaemail'), 'Texto Agendamento Email'),
        'textolembraretagendaemail': _as_nullable_int(data.get('textolembraretagendaemail'), 'Texto Retorno do Agendamento Email'),
        'textolembraniveremail': _as_nullable_int(data.get('textolembraniveremail'), 'Texto Aniversário Email'),
        'textolembraeventemail': _as_nullable_int(data.get('textolembraeventemail'), 'Texto Evento Email'),
        'autlembraagendawhatzap': _as_nullable_minutes(data.get('autlembraagendawhatzap'), 'Agendamento WhatsApp (Tempo em Minutos)'),
        'autlembraretagendawhatzap': _as_nullable_minutes(data.get('autlembraretagendawhatzap'), 'Retorno agendamento WhatsApp (Tempo em Minutos)'),
        'autlembraniverwahtzap': _as_nullable_minutes(data.get('autlembraniverwahtzap'), 'Lembra Aniversário WhatsApp (Tempo em Minutos)'),
        'autlembraeventowahtzap': _as_nullable_minutes(data.get('autlembraeventowahtzap'), 'Lembra Evento WhatsApp (Tempo em Minutos)'),
        'textolembraagendawahtzap': _as_nullable_int(data.get('textolembraagendawahtzap'), 'Texto Agendamento WhatsApp'),
        'textolembraretagendawahtzap': _as_nullable_int(data.get('textolembraretagendawahtzap'), 'Texto Retorno do Agendamento WhatsApp'),
        'textolembraniverwahtzap': _as_nullable_int(data.get('textolembraniverwahtzap'), 'Texto Aniversário WhatsApp'),
        'textolembraeventwahtzap': _as_nullable_int(data.get('textolembraeventwahtzap'), 'Texto Evento WhatsApp'),
    }


def _configuration_values(data):
    sender = re.sub(r'\D', '', data.get('whatsapp_remetente') or '5521986496127')
    if len(sender) in (10, 11):
        sender = '55' + sender
    if len(sender) not in (12, 13) or not sender.startswith('55'):
        raise ValueError('Informe o celular remetente do WhatsApp com código do país e DDD.')
    try:
        smtp_port = int(data.get('smtp_porta') or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError('Porta SMTP inválida.') from exc
    smtp_tls = _as_bool(data.get('smtp_tls'))
    smtp_ssl = _as_bool(data.get('smtp_ssl'))
    if smtp_tls and smtp_ssl:
        raise ValueError('Selecione TLS ou SSL para o SMTP, não os dois.')
    values = {
        'smtp_host': (data.get('smtp_host') or '').strip(),
        'smtp_porta': smtp_port,
        'smtp_usuario': (data.get('smtp_usuario') or '').strip(),
        'smtp_senha': data.get('smtp_senha') or '',
        'smtp_remetente': (data.get('smtp_remetente') or '').strip(),
        'smtp_tls': smtp_tls,
        'smtp_ssl': smtp_ssl,
        'whatsapp_remetente': sender,
        'whatsapp_phone_number_id': (data.get('whatsapp_phone_number_id') or '').strip(),
        'whatsapp_token': data.get('whatsapp_token') or '',
        'whatsapp_api_version': (data.get('whatsapp_api_version') or '').strip(),
        'whatsapp_template': (data.get('whatsapp_template') or '').strip(),
        'whatsapp_idioma': (data.get('whatsapp_idioma') or 'pt_BR').strip(),
        'whatzapsimplificado': _as_bool(data.get('whatzapsimplificado')),
    }
    values.update(_automation_values(data))
    return values


def _smtp_test_values(data):
    try:
        port = int(data.get('smtp_porta') or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError('Porta SMTP inválida.') from exc
    host = (data.get('smtp_host') or '').strip()
    user = (data.get('smtp_usuario') or '').strip()
    password = data.get('smtp_senha') or ''
    use_tls = _as_bool(data.get('smtp_tls'))
    use_ssl = _as_bool(data.get('smtp_ssl'))
    if not host:
        raise ValueError('Informe o servidor SMTP.')
    if not 1 <= port <= 65535:
        raise ValueError('Informe uma porta SMTP válida.')
    if not user:
        raise ValueError('Informe o usuário SMTP.')
    if use_tls and use_ssl:
        raise ValueError('Selecione TLS ou SSL para o SMTP, não os dois.')
    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'use_tls': use_tls,
        'use_ssl': use_ssl,
    }


def _smtp_response(label, response):
    code, text = response
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    return '{}: {} {}'.format(label, code, str(text or '').strip())


def _row_payload(row):
    if not row:
        return {
            'smtp_host': '', 'smtp_porta': 0, 'smtp_usuario': '', 'smtp_senha': '',
            'smtp_remetente': '', 'smtp_tls': True, 'smtp_ssl': False,
            'whatsapp_remetente': '5521986496127', 'whatsapp_phone_number_id': '',
            'whatsapp_token': '', 'whatsapp_api_version': '', 'whatsapp_template': '',
            'whatsapp_idioma': 'pt_BR', 'possui_smtp_senha': False,
            'possui_whatsapp_token': False, 'whatzapsimplificado': True,
            'autlembraagendaemail': '', 'autlembraretagendaemail': '',
            'autlembraniveremail': '', 'autlembraeventemail': '',
            'textolembraagendaemail': '', 'textolembraretagendaemail': '',
            'textolembraniveremail': '', 'textolembraeventemail': '',
            'autlembraagendawhatzap': '', 'autlembraretagendawhatzap': '',
            'autlembraniverwahtzap': '', 'autlembraeventowahtzap': '',
            'textolembraagendawahtzap': '', 'textolembraretagendawahtzap': '',
            'textolembraniverwahtzap': '', 'textolembraeventwahtzap': '',
        }
    names = [
        'smtp_host', 'smtp_porta', 'smtp_usuario', 'possui_smtp_senha',
        'smtp_remetente', 'smtp_tls', 'smtp_ssl', 'whatsapp_remetente',
        'whatsapp_phone_number_id', 'possui_whatsapp_token', 'whatsapp_api_version',
        'whatsapp_template', 'whatsapp_idioma', 'whatzapsimplificado',
    ]
    payload = dict(zip(names, row))
    payload['whatzapsimplificado'] = _row_bool(payload.get('whatzapsimplificado'))
    offset = len(names)
    for index, field_name in enumerate(AUTOMATION_FIELDS):
        value = row[offset + index] if len(row) > offset + index else None
        payload[field_name] = '' if value is None else str(value)
    payload['smtp_senha'] = ''
    payload['whatsapp_token'] = ''
    return payload


def _configuration_select_columns(cursor):
    existing = _columns(cursor, 'medsoft_configuracao')
    select_columns = [
        'smtp_host', 'smtp_porta', 'smtp_usuario',
        "COALESCE(smtp_senha, '') <> ''", 'smtp_remetente', 'smtp_tls', 'smtp_ssl',
        'whatsapp_remetente', 'whatsapp_phone_number_id',
        "COALESCE(whatsapp_token, '') <> ''", 'whatsapp_api_version',
        'whatsapp_template', 'whatsapp_idioma',
        'whatzapsimplificado' if 'whatzapsimplificado' in existing else "'N'",
    ]
    for field_name in AUTOMATION_FIELDS:
        if field_name in existing:
            select_columns.append(field_name)
        else:
            select_columns.append('NULL')
    return ', '.join(select_columns)


def _texto_options(cursor):
    if not _table_exists_named(cursor, 'texto'):
        return []
    columns = _columns(cursor, 'texto')
    id_column = next((name for name in ('codigo', 'codtexto', 'cod', 'idtexto', 'id') if name in columns), None)
    name_column = next((name for name in ('nome', 'descricao', 'titulo', 'atalho', 'texto') if name in columns), None)
    if not id_column:
        return []
    label_expr = name_column if name_column else id_column
    type_expr = 'atalho' if 'atalho' in columns else "''"
    where_clause = ''
    params = []
    if 'codclin' in columns:
        where_clause = ' WHERE codclin = %s'
        params.append(current_company_id())
    cursor.execute(
        'SELECT {id_column}, COALESCE(CAST({label_expr} AS TEXT), CAST({id_column} AS TEXT)), '
        'COALESCE(CAST({type_expr} AS TEXT), \'\') '
        'FROM public.texto{where_clause} ORDER BY 2'.format(
            id_column=id_column,
            label_expr=label_expr,
            type_expr=type_expr,
            where_clause=where_clause,
        ),
        tuple(params),
    )
    return [{
        'value': str(row[0]),
        'label': '{} - {}'.format(row[0], row[1]),
        'tipo': (row[2] or '').strip().upper(),
    } for row in cursor.fetchall()]


def _table_exists_named(cursor, table_name):
    cursor.execute('SELECT to_regclass(%s)', ('public.' + table_name,))
    return cursor.fetchone()[0] is not None


def _save_assignments(values, existing_columns, column_types, include_codclin=False):
    assignments = []
    parameters = []
    field_specs = [
        ('smtp_host', '%s', values['smtp_host']),
        ('smtp_porta', '%s', values['smtp_porta']),
        ('smtp_usuario', '%s', values['smtp_usuario']),
        ('smtp_senha', "COALESCE(NULLIF(%s, ''), smtp_senha)", values['smtp_senha']),
        ('smtp_remetente', '%s', values['smtp_remetente']),
        ('smtp_tls', '%s', values['smtp_tls']),
        ('smtp_ssl', '%s', values['smtp_ssl']),
        ('whatsapp_remetente', '%s', values['whatsapp_remetente']),
        ('whatsapp_phone_number_id', '%s', values['whatsapp_phone_number_id']),
        ('whatsapp_token', "COALESCE(NULLIF(%s, ''), whatsapp_token)", values['whatsapp_token']),
        ('whatsapp_api_version', '%s', values['whatsapp_api_version']),
        ('whatsapp_template', '%s', values['whatsapp_template']),
        ('whatsapp_idioma', '%s', values['whatsapp_idioma']),
        ('whatzapsimplificado', '%s', _db_bool(values['whatzapsimplificado'], 'whatzapsimplificado', column_types)),
        ('autlembraagendaemail', '%s', values['autlembraagendaemail']),
        ('autlembraretagendaemail', '%s', values['autlembraretagendaemail']),
        ('autlembraniveremail', '%s', values['autlembraniveremail']),
        ('autlembraeventemail', '%s', values['autlembraeventemail']),
        ('textolembraagendaemail', '%s', values['textolembraagendaemail']),
        ('textolembraretagendaemail', '%s', values['textolembraretagendaemail']),
        ('textolembraniveremail', '%s', values['textolembraniveremail']),
        ('textolembraeventemail', '%s', values['textolembraeventemail']),
        ('autlembraagendawhatzap', '%s', values['autlembraagendawhatzap']),
        ('autlembraretagendawhatzap', '%s', values['autlembraretagendawhatzap']),
        ('autlembraniverwahtzap', '%s', values['autlembraniverwahtzap']),
        ('autlembraeventowahtzap', '%s', values['autlembraeventowahtzap']),
        ('textolembraagendawahtzap', '%s', values['textolembraagendawahtzap']),
        ('textolembraretagendawahtzap', '%s', values['textolembraretagendawahtzap']),
        ('textolembraniverwahtzap', '%s', values['textolembraniverwahtzap']),
        ('textolembraeventwahtzap', '%s', values['textolembraeventwahtzap']),
    ]
    if include_codclin and 'codclin' in existing_columns:
        assignments.append('codclin = %s')
        parameters.append(current_company_id())
    for column_name, expression, value in field_specs:
        if column_name in existing_columns:
            assignments.append('{} = {}'.format(column_name, expression))
            parameters.append(value)
    if 'atualizado_em' in existing_columns:
        assignments.append('atualizado_em = NOW()')
    if 'atualizado_por' in existing_columns:
        assignments.append('atualizado_por = %s')
        parameters.append(str(session.get('usuario') or ''))
    return assignments, parameters


def _insert_configuration(cursor, values, existing_columns, column_types, has_codclin):
    columns = []
    placeholders = []
    parameters = []
    insert_specs = [
        ('codclin', '%s', current_company_id()),
        ('smtp_host', '%s', values['smtp_host']),
        ('smtp_porta', '%s', values['smtp_porta']),
        ('smtp_usuario', '%s', values['smtp_usuario']),
        ('smtp_senha', '%s', values['smtp_senha']),
        ('smtp_remetente', '%s', values['smtp_remetente']),
        ('smtp_tls', '%s', values['smtp_tls']),
        ('smtp_ssl', '%s', values['smtp_ssl']),
        ('whatsapp_remetente', '%s', values['whatsapp_remetente']),
        ('whatsapp_phone_number_id', '%s', values['whatsapp_phone_number_id']),
        ('whatsapp_token', '%s', values['whatsapp_token']),
        ('whatsapp_api_version', '%s', values['whatsapp_api_version']),
        ('whatsapp_template', '%s', values['whatsapp_template']),
        ('whatsapp_idioma', '%s', values['whatsapp_idioma']),
        ('whatzapsimplificado', '%s', _db_bool(values['whatzapsimplificado'], 'whatzapsimplificado', column_types)),
        ('autlembraagendaemail', '%s', values['autlembraagendaemail']),
        ('autlembraretagendaemail', '%s', values['autlembraretagendaemail']),
        ('autlembraniveremail', '%s', values['autlembraniveremail']),
        ('autlembraeventemail', '%s', values['autlembraeventemail']),
        ('textolembraagendaemail', '%s', values['textolembraagendaemail']),
        ('textolembraretagendaemail', '%s', values['textolembraretagendaemail']),
        ('textolembraniveremail', '%s', values['textolembraniveremail']),
        ('textolembraeventemail', '%s', values['textolembraeventemail']),
        ('autlembraagendawhatzap', '%s', values['autlembraagendawhatzap']),
        ('autlembraretagendawhatzap', '%s', values['autlembraretagendawhatzap']),
        ('autlembraniverwahtzap', '%s', values['autlembraniverwahtzap']),
        ('autlembraeventowahtzap', '%s', values['autlembraeventowahtzap']),
        ('textolembraagendawahtzap', '%s', values['textolembraagendawahtzap']),
        ('textolembraretagendawahtzap', '%s', values['textolembraretagendawahtzap']),
        ('textolembraniverwahtzap', '%s', values['textolembraniverwahtzap']),
        ('textolembraeventwahtzap', '%s', values['textolembraeventwahtzap']),
        ('atualizado_em', 'NOW()', None),
        ('atualizado_por', '%s', str(session.get('usuario') or '')),
    ]
    if 'id' in existing_columns:
        if has_codclin:
            # Bancos legados usam DEFAULT 1 em vez de sequence. Serializa a
            # inclusão para evitar que duas clínicas recebam o mesmo código.
            cursor.execute('LOCK TABLE public.medsoft_configuracao IN SHARE ROW EXCLUSIVE MODE')
            cursor.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM public.medsoft_configuracao')
            next_id = cursor.fetchone()[0]
        else:
            next_id = 1
        columns.append('id')
        placeholders.append('%s')
        parameters.append(next_id)
    for column_name, placeholder, value in insert_specs:
        if column_name in existing_columns:
            columns.append(column_name)
            placeholders.append(placeholder)
            if placeholder != 'NOW()':
                parameters.append(value)
    cursor.execute(
        'INSERT INTO public.medsoft_configuracao ({}) VALUES ({})'.format(
            ', '.join(columns), ', '.join(placeholders)
        ),
        tuple(parameters),
    )


@configuracao_api_bp.route('/api/configuracao', methods=['POST'])
def get_configuration():
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _table_exists(cursor):
                    return jsonify({
                        'success': False,
                        'message': 'Tabela public.medsoft_configuracao não encontrada. Execute o DDL fornecido.',
                    }), 409
                select_columns = _configuration_select_columns(cursor)
                texto_options = _texto_options(cursor)
                if _column_exists(cursor, 'codclin'):
                    company_id = _company_parameter()
                    cursor.execute('''
                        SELECT {}
                        FROM public.medsoft_configuracao
                        WHERE codclin = %s
                    '''.format(select_columns), (company_id,))
                    row = cursor.fetchone()
                    if row is None:
                        cursor.execute('''
                            SELECT {}
                            FROM public.medsoft_configuracao
                            WHERE codclin IS NULL
                            LIMIT 1
                        '''.format(select_columns))
                        row = cursor.fetchone()
                else:
                    cursor.execute('''
                        SELECT {}
                        FROM public.medsoft_configuracao
                        LIMIT 1
                    '''.format(select_columns))
                    row = cursor.fetchone()
        return jsonify({'success': True, 'configuracao': _row_payload(row), 'textos': texto_options})
    except Exception as exc:
        return _error_response(exc)


@configuracao_api_bp.route('/api/configuracao', methods=['PUT'])
def save_configuration():
    try:
        values = _configuration_values(request.get_json(silent=True) or {})
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _table_exists(cursor):
                    return jsonify({
                        'success': False,
                        'message': 'Tabela public.medsoft_configuracao não encontrada. Execute o DDL fornecido.',
                    }), 409
                _ensure_simplified_column(cursor)
                has_codclin = _column_exists(cursor, 'codclin')
                existing_columns = _columns(cursor, 'medsoft_configuracao')
                column_types = _column_types(cursor, 'medsoft_configuracao')
                assignments, parameters = _save_assignments(values, existing_columns, column_types)
                update_sql = 'UPDATE public.medsoft_configuracao SET {}'.format(', '.join(assignments))
                if has_codclin:
                    company_id = _company_parameter()
                    cursor.execute(update_sql + ' WHERE codclin = %s', tuple(parameters) + (company_id,))
                    if cursor.rowcount == 0:
                        null_assignments, null_parameters = _save_assignments(
                            values, existing_columns, column_types, include_codclin=True
                        )
                        cursor.execute(
                            'UPDATE public.medsoft_configuracao SET {} '
                            'WHERE ctid = (SELECT ctid FROM public.medsoft_configuracao '
                            'WHERE codclin IS NULL LIMIT 1)'.format(', '.join(null_assignments)),
                            tuple(null_parameters),
                        )
                else:
                    cursor.execute(update_sql + '''
                        WHERE ctid = (
                            SELECT ctid FROM public.medsoft_configuracao LIMIT 1
                        )
                    ''', tuple(parameters))
                if cursor.rowcount == 0 and has_codclin:
                    _insert_configuration(cursor, values, existing_columns, column_types, has_codclin)
                elif cursor.rowcount == 0:
                    _insert_configuration(cursor, values, existing_columns, column_types, has_codclin)
        return jsonify({'success': True, 'message': 'Configurações salvas com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@configuracao_api_bp.route('/api/configuracao/testar-email', methods=['POST'])
def test_email_configuration():
    server = None
    try:
        values = _smtp_test_values(request.get_json(silent=True) or {})
        if not values['password']:
            with _connection() as connection:
                with connection.cursor() as cursor:
                    if _column_exists(cursor, 'codclin'):
                        cursor.execute('''
                            SELECT smtp_senha
                            FROM public.medsoft_configuracao
                            WHERE codclin = %s
                        ''', (_company_parameter(),))
                        row = cursor.fetchone()
                        if row is None:
                            cursor.execute('''
                                SELECT smtp_senha
                                FROM public.medsoft_configuracao
                                LIMIT 1
                            ''')
                            row = cursor.fetchone()
                    else:
                        cursor.execute('''
                            SELECT smtp_senha
                            FROM public.medsoft_configuracao
                            LIMIT 1
                        ''')
                        row = cursor.fetchone()
            values['password'] = row[0] if row else ''
        if not values['password']:
            raise ValueError('Informe a senha SMTP ou salve uma senha antes do teste.')

        responses = []
        if values['use_ssl']:
            server = smtplib.SMTP_SSL(
                values['host'], values['port'], timeout=15,
                context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(values['host'], values['port'], timeout=15)
        responses.append('Conexão: estabelecida com {}:{}'.format(values['host'], values['port']))
        responses.append(_smtp_response('EHLO', server.ehlo()))
        if values['use_tls'] and not values['use_ssl']:
            responses.append(_smtp_response(
                'STARTTLS', server.starttls(context=ssl.create_default_context())
            ))
            responses.append(_smtp_response('EHLO após TLS', server.ehlo()))
        responses.append(_smtp_response(
            'Autenticação', server.login(values['user'], values['password'])
        ))
        responses.append(_smtp_response('Servidor', server.noop()))
        server.quit()
        server = None
        return jsonify({
            'success': True,
            'message': 'Conexão SMTP e autenticação realizadas com sucesso.',
            'responses': responses,
        })
    except socket.gaierror:
        return jsonify({
            'success': False,
            'message': 'Servidor SMTP não encontrado. Confira o endereço informado.',
        }), 400
    except smtplib.SMTPAuthenticationError as exc:
        return jsonify({
            'success': False,
            'message': 'Autenticação recusada pelo servidor SMTP ({}). Confira usuário e senha.'.format(exc.smtp_code),
        }), 400
    except (smtplib.SMTPException, ssl.SSLError, TimeoutError, OSError) as exc:
        current_app.logger.warning('Teste SMTP falhou: %s', exc)
        return jsonify({
            'success': False,
            'message': 'Falha na conexão SMTP: {}'.format(str(exc)),
        }), 400
    except Exception as exc:
        return _error_response(exc)
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
