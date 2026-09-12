from flask import Blueprint, request, jsonify, session
from medsoft_core import get_db_connection, DBConnectionError
from psycopg2 import sql
import logging
from datetime import date, datetime
import unicodedata
from tenant_context import current_company_id
from agenda_api import (
    _clinic_name, _confirmation_message, _confirmation_pattern_record,
    _notification_settings, _send_confirmation_email,
    _send_confirmation_whatsapp, _whatsapp_phone,
)
from baileys_api import send_baileys_text
from message_log import log_sent_message


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
consulta_paciente_bp = Blueprint('consulta_paciente', __name__)
FIELD_CANDIDATES = {
    'nascimento': ('datanasc_',),
    'cpf': ('cpf',),
    'rg': ('cident',),
    'sexo': ('sexo',),
    'email': ('email',),
    'ativo': ('ativo',),
    'endereco': ('endcli',),
    'uf': ('ufcli',),
    'cep': ('cepcli',),
    'cidade': ('cidadecli',),
    'bairro': ('baicli',),
    'estado_civil': ('est_civ',),
    'cor': ('corcli',),
    'foto': ('foto',),
    'cont1': ('cont1',),
    'validade_carteira1': ('validade_carteira1',),
    'nompai': ('nompai',),
    'nommae': ('nommae',),
    'profcli': ('profcli',),
    'natcli': ('natcli',),
    'recom': ('recom',),
    'nomeplano2': ('nomeplano2',),
    'cont2': ('cont2',),
    'datult': ('datult_',),
    'matricula': ('matricula',),
    'obs': ('obs',),
}

BASE_FIELD_CANDIDATES = {
    'nomecli': ('nomecli',),
    'codcli': ('codcli',),
    'codclin': ('codclin',),
    'nomeplano1': ('nomeplano1',),
    'nomed': ('nomed',),
    'telres': ('telres',),
    'telcom': ('telcom',),
}

DATE_FIELDS = {'nascimento', 'validade_carteira1', 'datult'}
PATIENT_REPORT_EXCLUDED_COLUMNS = {'codclin', 'id', 'doenca1', 'nomed', 'mes', 'cident'}


def _patient_report_column_allowed(column_name):
    normalized = ''.join(
        character for character in unicodedata.normalize('NFD', str(column_name or ''))
        if unicodedata.category(character) != 'Mn'
    ).strip().lower()
    return normalized not in PATIENT_REPORT_EXCLUDED_COLUMNS


def _fetch_columns(cursor):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'pacient'
    """)
    return {row[0].lower(): row[0] for row in cursor.fetchall()}


def _pick(columns, candidates):
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def _select_optional(columns, logical_name):
    column_name = _pick(columns, FIELD_CANDIDATES[logical_name])
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(logical_name))
    if logical_name in DATE_FIELDS:
        return sql.SQL("to_char({}, 'YYYY-MM-DD') AS {}").format(
            sql.Identifier(column_name),
            sql.Identifier(logical_name),
        )
    if logical_name == 'ativo':
        return sql.SQL(
            "CASE WHEN LOWER(COALESCE(CAST({} AS TEXT), '')) "
            "IN ('n', 'nao', 'não', 'false', '0', 'inativo') THEN FALSE ELSE TRUE END AS {}"
        ).format(sql.Identifier(column_name), sql.Identifier(logical_name))
    if logical_name == 'foto':
        return sql.SQL(
            "CASE WHEN {} IS NULL THEN '' ELSE 'data:image/jpeg;base64,' || encode({}, 'base64') END AS {}"
        ).format(
            sql.Identifier(column_name),
            sql.Identifier(column_name),
            sql.Identifier(logical_name),
        )
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _select_base_optional(columns, logical_name):
    column_name = _pick(columns, BASE_FIELD_CANDIDATES[logical_name])
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _phone_expression(columns):
    telres = _pick(columns, BASE_FIELD_CANDIDATES['telres'])
    telcom = _pick(columns, BASE_FIELD_CANDIDATES['telcom'])
    if telres and telcom:
        return sql.SQL("COALESCE(NULLIF({}, ''), NULLIF({}, ''), '') AS telefone").format(
            sql.Identifier(telres),
            sql.Identifier(telcom),
        )
    if telres:
        return sql.SQL("COALESCE({}, '') AS telefone").format(sql.Identifier(telres))
    if telcom:
        return sql.SQL("COALESCE({}, '') AS telefone").format(sql.Identifier(telcom))
    return sql.SQL("'' AS telefone")


def remover_acentos(txt):
    if not txt:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').upper()

@consulta_paciente_bp.route('/api/consulta-paciente', methods=['POST'])
def consulta_paciente():
    data = request.json
    termo = data.get('termo', '').strip() if data else ''
    campo_busca = str(data.get('campo') or 'nome').strip().lower() if data else 'nome'
    if not termo:
        return jsonify({'success': False, 'message': 'Informe o nome ou código do paciente.', 'pacientes': []}), 400
    try:
        # Usa a conexão PostgreSQL configurada.
        db_path = session.get('db_path') or None
        con = get_db_connection(db_path)
        cur = con.cursor()
        columns = _fetch_columns(cur)
        nome_column = _pick(columns, BASE_FIELD_CANDIDATES['nomecli'])
        codigo_column = _pick(columns, BASE_FIELD_CANDIDATES['codcli'])
        tenant_column = _pick(columns, BASE_FIELD_CANDIDATES['codclin'])
        ativo_column = _pick(columns, FIELD_CANDIDATES['ativo'])
        if not nome_column or not codigo_column or not tenant_column:
            raise ValueError('Tabela de pacientes sem campos obrigatórios de nome, código ou clínica.')
        nascimento_column = _pick(columns, FIELD_CANDIDATES['nascimento'])
        idade_expr = (
            sql.SQL('COALESCE(EXTRACT(YEAR FROM age(CURRENT_DATE, {})), 0)::int AS idade')
            .format(sql.Identifier(nascimento_column))
            if nascimento_column else sql.SQL('0::int AS idade')
        )
        select_items = [
            sql.SQL('{} AS nomecli').format(sql.Identifier(nome_column)),
            sql.SQL('{} AS codcli').format(sql.Identifier(codigo_column)),
            idade_expr,
            _select_base_optional(columns, 'nomeplano1'),
            _select_base_optional(columns, 'nomed'),
            _phone_expression(columns),
        ] + [_select_optional(columns, field) for field in FIELD_CANDIDATES]
        termo_limpo = termo.strip()
        if termo_limpo and any(c != '%' for c in termo_limpo):
            if campo_busca == 'nome':
                filtro = sql.SQL('{} ILIKE %s').format(sql.Identifier(nome_column))
                quantidade_parametros = 1
                termo_busca = f"{termo_limpo}%"
            elif campo_busca == 'sobrenome':
                filtro = sql.SQL('{} ILIKE %s').format(sql.Identifier(nome_column))
                quantidade_parametros = 1
                termo_busca = f"%{termo_limpo}"
            elif campo_busca == 'cpf':
                cpf_column = _pick(columns, FIELD_CANDIDATES['cpf'])
                if not cpf_column:
                    raise ValueError('O cadastro de pacientes não possui campo de CPF.')
                filtro = sql.SQL("regexp_replace(COALESCE(CAST({} AS TEXT), ''), '\\D', '', 'g') LIKE %s").format(
                    sql.Identifier(cpf_column)
                )
                quantidade_parametros = 1
                termo_busca = ''.join(c for c in termo_limpo if c.isdigit()) + '%'
            else:
                colunas_telefone = [
                    _pick(columns, BASE_FIELD_CANDIDATES['telres']),
                    _pick(columns, BASE_FIELD_CANDIDATES['telcom']),
                ]
                colunas_telefone = [column for column in colunas_telefone if column]
                if not colunas_telefone:
                    raise ValueError('O cadastro de pacientes não possui campo de telefone.')
                filtros_telefone = [
                    sql.SQL("regexp_replace(COALESCE(CAST({} AS TEXT), ''), '\\D', '', 'g') LIKE %s").format(
                        sql.Identifier(column)
                    ) for column in colunas_telefone
                ]
                filtro = sql.SQL('(') + sql.SQL(' OR ').join(filtros_telefone) + sql.SQL(')')
                quantidade_parametros = len(colunas_telefone)
                termo_busca = ''.join(c for c in termo_limpo if c.isdigit()) + '%'
            filtro_ativo = (
                sql.SQL(
                    "LOWER(COALESCE(CAST({} AS TEXT), '')) "
                    "NOT IN ('n', 'nao', 'não', 'false', '0', 'inativo')"
                ).format(sql.Identifier(ativo_column))
                if ativo_column else sql.SQL('TRUE')
            )
            query = sql.SQL('''
                SELECT {}
                FROM public.pacient
                WHERE {} = %s
                  AND {}
                  AND {}
                ORDER BY {}
                LIMIT 100
            ''').format(
                sql.SQL(', ').join(select_items),
                sql.Identifier(tenant_column),
                filtro_ativo,
                filtro,
                sql.Identifier(nome_column),
            )
            logging.info(f'Executando busca em public.pacient por {campo_busca} db_path={db_path}')
            cur.execute(query, tuple([current_company_id()] + [termo_busca] * quantidade_parametros))
        else:
            con.close()
            return jsonify({'success': False, 'message': 'Termo inválido.', 'pacientes': []}), 400
        pacientes = []
        rows = cur.fetchall()
        field_names = ['nomecli', 'codcli', 'idade', 'nomeplano1', 'nomed', 'telefone'] + list(FIELD_CANDIDATES)
        for row in rows:
            pacientes.append(dict(zip(field_names, row)))
        con.close()
        if not rows:
            return jsonify({'success': True, 'pacientes': [], 'message': 'Nenhum paciente encontrado.'})
        return jsonify({'success': True, 'pacientes': pacientes})
    except DBConnectionError as e:
        logging.error(f'Erro de conexão no consulta_paciente: {e}')
        return jsonify({'success': False, 'message': str(e), 'pacientes': []}), 503
    except Exception as e:
        import traceback
        logging.error(f'Erro na consulta de paciente: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Erro interno no servidor.' , 'pacientes': []}), 500


@consulta_paciente_bp.route('/api/relatorios/pacientes', methods=['POST'])
def relatorio_pacientes():
    data = request.get_json(silent=True) or {}
    termo = str(data.get('termo') or '').strip()
    campo_busca = str(data.get('campo') or 'nome').strip().lower()
    listar_todos = bool(data.get('todos'))
    incluir_historico = bool(data.get('historico_clinico'))
    if not listar_todos and not termo:
        return jsonify({'success': False, 'message': 'Informe o paciente.', 'pacientes': []}), 400
    if campo_busca not in ('nome', 'cpf', 'telefone'):
        return jsonify({'success': False, 'message': 'Campo de busca inválido.', 'pacientes': []}), 400
    if incluir_historico and session.get('profile_verhist') is False:
        return jsonify({
            'success': False,
            'message': 'Seu perfil nao permite visualizar o historico clinico.',
            'pacientes': [],
        }), 403
    if campo_busca not in ('nome', 'cpf', 'telefone'):
        return jsonify({'success': False, 'message': 'Campo de busca inválido.', 'pacientes': []}), 400
    try:
        connection = get_db_connection(session.get('db_path') or None)
        try:
            with connection.cursor() as cursor:
                columns = _fetch_columns(cursor)
                nome_column = _pick(columns, BASE_FIELD_CANDIDATES['nomecli'])
                codigo_column = _pick(columns, BASE_FIELD_CANDIDATES['codcli'])
                tenant_column = _pick(columns, BASE_FIELD_CANDIDATES['codclin'])
                cpf_column = _pick(columns, FIELD_CANDIDATES['cpf'])
                telefone_column = _pick(columns, BASE_FIELD_CANDIDATES['telres'])
                if not nome_column or not codigo_column or not tenant_column:
                    raise ValueError('Tabela de pacientes sem os campos obrigatorios.')
                cursor.execute('''
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND lower(table_name) = 'pacient'
                    ORDER BY ordinal_position
                ''')
                report_columns = cursor.fetchall()
                report_columns = [
                    column for column in report_columns
                    if _patient_report_column_allowed(column[0])
                ]
                select_items = []
                for column_name, data_type in report_columns:
                    if data_type == 'bytea':
                        expression = sql.SQL(
                            "CASE WHEN {} IS NULL THEN '' ELSE '[imagem/arquivo]' END AS {}"
                        ).format(sql.Identifier(column_name), sql.Identifier(column_name))
                    else:
                        expression = sql.SQL("COALESCE(CAST({} AS TEXT), '') AS {}").format(
                            sql.Identifier(column_name), sql.Identifier(column_name)
                        )
                    select_items.append(expression)
                conditions = [sql.SQL('{} = %s').format(sql.Identifier(tenant_column))]
                parameters = [current_company_id()]
                if not listar_todos:
                    if campo_busca == 'nome':
                        conditions.append(sql.SQL('{} ILIKE %s').format(sql.Identifier(nome_column)))
                        parameters.append(f'%{termo}%')
                    elif campo_busca == 'cpf':
                        if not cpf_column:
                            raise ValueError('Cadastro de pacientes sem o campo CPF.')
                        conditions.append(sql.SQL('CAST({} AS TEXT) LIKE %s').format(
                            sql.Identifier(cpf_column)
                        ))
                        parameters.append(f'%{termo}%')
                    else:
                        if not telefone_column:
                            raise ValueError('Cadastro de pacientes sem o campo Telefone.')
                        conditions.append(sql.SQL('CAST({} AS TEXT) LIKE %s').format(
                            sql.Identifier(telefone_column)
                        ))
                        parameters.append(f'%{termo}%')
                statement = sql.SQL('''
                    SELECT {} FROM public.pacient
                    WHERE {}
                    ORDER BY {}
                ''').format(
                    sql.SQL(', ').join(select_items),
                    sql.SQL(' AND ').join(conditions),
                    sql.Identifier(nome_column),
                )
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
                fields = [column_name for column_name, _data_type in report_columns]
                pacientes = [dict(zip(fields, row)) for row in rows]
                if incluir_historico and pacientes:
                    patient_ids = []
                    for patient in pacientes:
                        try:
                            patient_ids.append(int(patient.get(codigo_column)))
                        except (TypeError, ValueError):
                            continue
                    history_by_patient = {patient_id: [] for patient_id in patient_ids}
                    if patient_ids:
                        cursor.execute('''
                            SELECT codpac, dtvisita, historico
                            FROM public.consulta
                            WHERE codclin = %s AND codpac = ANY(%s)
                            ORDER BY codpac, dtvisita DESC NULLS LAST, cod DESC
                        ''', (current_company_id(), patient_ids))
                        for patient_id, visit_date, history in cursor.fetchall():
                            if isinstance(history, memoryview):
                                history = history.tobytes()
                            if isinstance(history, bytes):
                                try:
                                    history = history.decode('utf-8')
                                except UnicodeDecodeError:
                                    history = history.decode('latin-1', errors='replace')
                            history = str(history or '').replace('\r\n', '\n').replace('\r', '\n').strip()
                            if not history:
                                continue
                            date_text = visit_date.strftime('%d/%m/%Y') if visit_date else 'Sem data'
                            history_by_patient.setdefault(patient_id, []).append(f'{date_text}: {history}')
                    for patient in pacientes:
                        try:
                            patient_id = int(patient.get(codigo_column))
                        except (TypeError, ValueError):
                            patient_id = None
                        patient['historico_clinico'] = '\n\n'.join(history_by_patient.get(patient_id, []))
                    fields.append('historico_clinico')
        finally:
            connection.close()
        return jsonify({
            'success': True,
            'pacientes': pacientes,
            'colunas': fields,
            'total': len(rows),
        })
    except DBConnectionError as exc:
        return jsonify({'success': False, 'message': str(exc), 'pacientes': []}), 503
    except Exception:
        logging.exception('Erro ao gerar relatorio de pacientes.')
        return jsonify({'success': False, 'message': 'Erro interno no servidor.', 'pacientes': []}), 500


@consulta_paciente_bp.route('/api/relatorios/pacientes/enviar-mensagem', methods=['POST'])
def enviar_mensagem_pacientes():
    data = request.get_json(silent=True) or {}
    channel = str(data.get('canal') or '').strip().lower()
    message_code = data.get('codigo_texto')
    try:
        patient_ids = list(dict.fromkeys(int(value) for value in (data.get('pacientes') or [])))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Seleção de pacientes inválida.'}), 400
    if channel not in ('email', 'whatsapp'):
        return jsonify({'success': False, 'message': 'Canal de mensagem inválido.'}), 400
    if not patient_ids:
        return jsonify({'success': False, 'message': 'Selecione pelo menos um paciente.'}), 400
    if len(patient_ids) > 100:
        return jsonify({'success': False, 'message': 'Selecione no máximo 100 pacientes por envio.'}), 400

    selected_code, pattern, message_html = _confirmation_pattern_record(
        'E' if channel == 'email' else 'Z', message_code
    )
    if selected_code is None:
        return jsonify({'success': False, 'message': 'O texto padrão selecionado não foi encontrado.'}), 400

    try:
        connection = get_db_connection(session.get('db_path') or None)
        try:
            with connection.cursor() as cursor:
                columns = _fetch_columns(cursor)
                id_column = _pick(columns, BASE_FIELD_CANDIDATES['codcli'])
                name_column = _pick(columns, BASE_FIELD_CANDIDATES['nomecli'])
                tenant_column = _pick(columns, BASE_FIELD_CANDIDATES['codclin'])
                contact_column = (
                    _pick(columns, FIELD_CANDIDATES['email']) if channel == 'email'
                    else _pick(columns, BASE_FIELD_CANDIDATES['telres'])
                )
                if not id_column or not name_column or not tenant_column:
                    raise ValueError('Tabela de pacientes sem os campos obrigatórios.')
                if not contact_column:
                    raise ValueError('Cadastro de pacientes sem o contato necessário para este envio.')
                cursor.execute(sql.SQL('''
                    SELECT {}, {}, COALESCE(CAST({} AS TEXT), '')
                    FROM public.pacient
                    WHERE {} = %s AND {} = ANY(%s)
                    ORDER BY {}
                ''').format(
                    sql.Identifier(id_column), sql.Identifier(name_column),
                    sql.Identifier(contact_column), sql.Identifier(tenant_column),
                    sql.Identifier(id_column), sql.Identifier(name_column),
                ), (current_company_id(), patient_ids))
                patients = cursor.fetchall()
        finally:
            connection.close()

        settings = _notification_settings()
        clinic_name = _clinic_name() or 'MedSoft'
        results = []
        for patient_id, patient_name, contact in patients:
            context = {
                'paciente': str(patient_name or ''), 'procedimento': 'atendimento',
                'data': date.today(), 'hora': '', 'profissional': '',
                'nomeclinica': clinic_name,
            }
            message = _confirmation_message(
                context, pattern, html_mode=message_html if channel == 'email' else False
            )
            sent, error = False, ''
            if channel == 'email':
                sent, error = _send_confirmation_email(
                    contact, context, settings, message=message,
                    subject='Mensagem da {}'.format(clinic_name),
                    message_code=selected_code, company_id=current_company_id(),
                    message_type='Email Manual', html_mode=message_html,
                )
            elif settings['whatsapp_simplified']:
                try:
                    normalized_contact = _whatsapp_phone(contact)
                    result = send_baileys_text(current_company_id(), normalized_contact, message)
                    log_sent_message(
                        'Whatzap', normalized_contact, selected_code,
                        company_id=current_company_id(),
                        message_id=result.get('messageId'), content=message,
                    )
                    sent = True
                except (ValueError, RuntimeError) as exc:
                    error = str(exc)
                    log_sent_message(
                        'Whatzap', contact, selected_code, company_id=current_company_id(),
                        sent=False, error_reason=error, content=message,
                    )
            else:
                sent, error = _send_confirmation_whatsapp(
                    contact, context, settings, message_code=selected_code,
                    company_id=current_company_id(), message=message,
                )
            results.append({
                'paciente_id': patient_id, 'paciente': str(patient_name or ''),
                'sucesso': sent, 'erro': error,
            })

        found_ids = {row[0] for row in patients}
        for patient_id in patient_ids:
            if patient_id not in found_ids:
                results.append({
                    'paciente_id': patient_id, 'paciente': '',
                    'sucesso': False, 'erro': 'Paciente não encontrado.',
                })
        sent_count = sum(1 for item in results if item['sucesso'])
        failed_count = len(results) - sent_count
        payload = {
            'success': sent_count > 0,
            'mode': 'baileys' if channel == 'whatsapp' and settings['whatsapp_simplified'] else channel,
            'enviados': sent_count, 'falhas': failed_count,
            'resultados': results,
            'message': '{} mensagem(ns) enviada(s); {} falha(s).'.format(
                sent_count, failed_count
            ),
        }
        return jsonify(payload), 200 if sent_count > 0 else 400
    except DBConnectionError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except Exception:
        logging.exception('Erro ao enviar mensagens do relatório de pacientes.')
        return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@consulta_paciente_bp.route('/api/relatorios/cadastros/<report_type>', methods=['POST'])
def relatorio_cadastro(report_type):
    reports = {
        'plano': {'table': 'plano', 'order': 'nomeplano', 'title': 'Planos'},
        'prof-saude': {'table': 'nomed', 'order': 'nomed', 'title': 'Profissionais de Saúde'},
        'procedimentos': {
            'table': 'amb',
            'order': 'descamb',
            'first_column': 'descamb',
            'title': 'Procedimentos',
        },
    }
    config = reports.get(report_type)
    if not config:
        return jsonify({'success': False, 'message': 'Relatorio invalido.'}), 404
    try:
        connection = get_db_connection(session.get('db_path') or None)
        try:
            with connection.cursor() as cursor:
                cursor.execute('''
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND lower(table_name) = lower(%s)
                    ORDER BY ordinal_position
                ''', (config['table'],))
                metadata = cursor.fetchall()
                column_lookup = {name.lower(): name for name, _data_type in metadata}
                tenant_column = column_lookup.get('codclin')
                if not tenant_column:
                    raise ValueError('Tabela do relatorio sem identificacao da empresa.')
                visible_metadata = [column for column in metadata if column[0].lower() != 'codclin']
                first_column = config.get('first_column')
                if first_column:
                    visible_metadata.sort(key=lambda column: column[0].lower() != first_column)
                select_items = []
                for column_name, data_type in visible_metadata:
                    if data_type == 'bytea':
                        expression = sql.SQL(
                            "CASE WHEN {} IS NULL THEN '' ELSE '[imagem/arquivo]' END AS {}"
                        ).format(sql.Identifier(column_name), sql.Identifier(column_name))
                    else:
                        expression = sql.SQL("COALESCE(CAST({} AS TEXT), '') AS {}").format(
                            sql.Identifier(column_name), sql.Identifier(column_name)
                        )
                    select_items.append(expression)
                order_column = column_lookup.get(config['order'], visible_metadata[0][0] if visible_metadata else tenant_column)
                statement = sql.SQL('''
                    SELECT {} FROM public.{}
                    WHERE {} = %s
                    ORDER BY {}
                ''').format(
                    sql.SQL(', ').join(select_items),
                    sql.Identifier(config['table']),
                    sql.Identifier(tenant_column),
                    sql.Identifier(order_column),
                )
                cursor.execute(statement, (current_company_id(),))
                rows = cursor.fetchall()
        finally:
            connection.close()
        fields = [column_name for column_name, _data_type in visible_metadata]
        records = [dict(zip(fields, row)) for row in rows]
        return jsonify({
            'success': True,
            'titulo': config['title'],
            'registros': records,
            'colunas': fields,
            'total': len(records),
        })
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except DBConnectionError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 503
    except Exception:
        logging.exception('Erro ao gerar relatorio cadastral %s.', report_type)
        return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


