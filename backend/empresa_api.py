from contextlib import contextmanager
from datetime import date
import re

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import errors, sql

from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import current_company_id


empresa_api_bp = Blueprint('empresa_api', __name__)

TABLE_CANDIDATES = ('ic_empresa_geral', 'icempresageral', 'Ic-empresa-geral')
ID_CANDIDATES = ('idempresa', 'id_empresa', 'codempresa', 'codigo', 'id')
FIELD_CANDIDATES = {
    'nome': ('nome', 'empresa', 'razao_social', 'fantasia'),
    'database': ('database', 'banco', 'db_path', 'nome_banco'),
    'ativo': ('ativo',),
    'email': ('email', 'e_mail'),
    'telefone': ('telefone', 'fone'),
    'whatsapp': ('whatsapp', 'whats_app', 'celular'),
    'plano': ('idplano', 'plano'),
    'datainico': ('datainico', 'datainicio', 'data_inicio'),
    'pago': ('pago',),
    'titulo1': ('titulo1', 'titulo_1'),
    'titulo2': ('titulo2', 'titulo_2'),
}


@contextmanager
def _connection():
    connection = get_db_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _fetch_table_columns(cursor, table_name):
    cursor.execute('''
        SELECT table_name, column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = lower(%s)
        ORDER BY ordinal_position
    ''', (table_name,))
    rows = cursor.fetchall()
    actual_table = rows[0][0] if rows else None
    columns = {
        row[1].lower(): {
            'name': row[1],
            'data_type': row[2] or '',
            'default': row[3],
        }
        for row in rows
    }
    return actual_table, columns


def _pick(columns, candidates):
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def _detect_layout(cursor):
    for table_candidate in TABLE_CANDIDATES:
        table_name, columns = _fetch_table_columns(cursor, table_candidate)
        if not columns:
            continue
        id_column = _pick(columns, ID_CANDIDATES)
        fields = {}
        for logical_name, candidates in FIELD_CANDIDATES.items():
            column = _pick(columns, candidates)
            if column:
                fields[logical_name] = column['name']
        if not id_column or 'nome' not in fields or 'database' not in fields:
            continue
        return {
            'table': table_name or table_candidate,
            'id_column': id_column['name'],
            'id_type': id_column['data_type'],
            'id_default': id_column['default'],
            'fields': fields,
        }
    raise ValueError('Tabela public.ic_empresa_geral nao encontrada no banco.')


def _layout():
    with _connection() as connection:
        with connection.cursor() as cursor:
            return _detect_layout(cursor)


def _is_master_profile(value):
    return (value or '').strip().upper() == 'MASTER'


def _current_user_is_master(cursor):
    if _is_master_profile(session.get('perfil')):
        return True
    user_id = session.get('idusuario')
    if not user_id:
        return False
    cursor.execute("SELECT to_regclass('public.ic_usuario_geral'), to_regclass('public.ic_perfil_geral')")
    user_table, profile_table = cursor.fetchone()
    if not user_table or not profile_table:
        return False
    cursor.execute('''
        SELECT COALESCE(perfil.nome, perfil.descricao, '')
        FROM public.ic_usuario_geral usuario
        LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = usuario.idperfil
        WHERE usuario.idusuario = %s
        LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    return _is_master_profile(row[0] if row else '')


def _current_user_has_global_scope(cursor):
    return _current_user_is_master(cursor)


def _require_master(cursor):
    if not _current_user_is_master(cursor):
        raise PermissionError('Apenas usuarios com perfil MASTER podem cadastrar ou alterar empresa.')


def _empresa_values(data, layout):
    nome = (data.get('nome') or '').strip()
    database = (data.get('database') or '').strip()
    if not nome:
        raise ValueError('Informe o nome da empresa.')
    if not database:
        raise ValueError('Informe o banco de dados da empresa.')
    if len(nome) > 120:
        raise ValueError('O nome da empresa deve ter no maximo 120 caracteres.')
    if len(database) > 120:
        raise ValueError('O banco de dados deve ter no maximo 120 caracteres.')
    email = (data.get('email') or '').strip()
    telefone = (data.get('telefone') or '').strip()
    whatsapp = (data.get('whatsapp') or '').strip()
    plano_text = str(data.get('plano') or '').strip()
    data_inicio_text = (data.get('datainico') or '').strip()
    pago = str(data.get('pago') or 'N').strip().upper()
    titulo1 = (data.get('titulo1') or '').strip()
    titulo2 = (data.get('titulo2') or '').strip()
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Informe um e-mail valido.')
    if len(email) > 120:
        raise ValueError('O e-mail deve ter no maximo 120 caracteres.')
    if len(telefone) > 20 or len(whatsapp) > 20:
        raise ValueError('Telefone e WhatsApp devem ter no maximo 20 caracteres.')
    plano = None
    if plano_text:
        try:
            plano = int(plano_text)
        except (TypeError, ValueError) as exc:
            raise ValueError('Informe um plano valido.') from exc
        if plano <= 0:
            raise ValueError('Informe um plano valido.')
    if len(titulo1) > 120 or len(titulo2) > 120:
        raise ValueError('Titulo 1 e Titulo 2 devem ter no maximo 120 caracteres.')
    if pago not in ('S', 'N'):
        raise ValueError('Pago deve ser Sim ou Nao.')
    data_inicio = None
    if data_inicio_text:
        try:
            data_inicio = date.fromisoformat(data_inicio_text)
        except ValueError as exc:
            raise ValueError('Informe uma data de inicio valida.') from exc
    values = {
        layout['fields']['nome']: nome,
        layout['fields']['database']: database,
    }
    if 'ativo' in layout['fields']:
        values[layout['fields']['ativo']] = bool(data.get('ativo', True))
    optional_values = {
        'email': email or None,
        'telefone': telefone or None,
        'whatsapp': whatsapp or None,
        'plano': plano or None,
        'datainico': data_inicio,
        'pago': pago,
        'titulo1': titulo1 or None,
        'titulo2': titulo2 or None,
    }
    for logical_name, value in optional_values.items():
        if logical_name in layout['fields']:
            values[layout['fields'][logical_name]] = value
    return values


def _should_generate_integer_id(layout):
    return (layout.get('id_type') or '').lower() in (
        'integer', 'bigint', 'smallint', 'numeric'
    )


def _next_integer_id(cursor, layout):
    cursor.execute(
        'SELECT pg_advisory_xact_lock(hashtext(%s))',
        (f"public.{layout['table']}",),
    )
    cursor.execute(sql.SQL('SELECT COALESCE(MAX({}), 0) + 1 FROM {}.{}').format(
        sql.Identifier(layout['id_column']),
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
    ))
    return cursor.fetchone()[0]


def _select_expression(layout, logical_name):
    column_name = layout['fields'].get(logical_name)
    if not column_name:
        fallback = 'TRUE' if logical_name == 'ativo' else "''"
        return sql.SQL('{} AS {}').format(sql.SQL(fallback), sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _error_response(exc):
    if isinstance(exc, PermissionError):
        return jsonify({'success': False, 'message': str(exc)}), 403
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({'success': False, 'message': 'Ja existe uma empresa com estes dados.'}), 409
    if isinstance(exc, (errors.LockNotAvailable, errors.QueryCanceled)):
        return jsonify({
            'success': False,
            'message': (
                'A empresa esta sendo alterada em outra conexao. '
                'Confirme ou cancele a alteracao pendente e tente novamente.'
            ),
        }), 409
    current_app.logger.exception('Falha na operacao de empresa', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@empresa_api_bp.route('/api/empresas', methods=['POST'])
def list_empresas():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        layout = _layout()
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
            _select_expression(layout, 'nome'),
            _select_expression(layout, 'database'),
            _select_expression(layout, 'ativo'),
            _select_expression(layout, 'email'),
            _select_expression(layout, 'telefone'),
            _select_expression(layout, 'whatsapp'),
            _select_expression(layout, 'plano'),
            _select_expression(layout, 'datainico'),
            _select_expression(layout, 'pago'),
            _select_expression(layout, 'titulo1'),
            _select_expression(layout, 'titulo2'),
        ]
        statement = sql.SQL('SELECT {} FROM {}.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        conditions = []
        parameters = []
        if term:
            conditions.append(sql.SQL('(CAST({} AS TEXT) ILIKE %s OR {} ILIKE %s OR {} ILIKE %s)').format(
                sql.Identifier(layout['id_column']),
                sql.Identifier(layout['fields']['nome']),
                sql.Identifier(layout['fields']['database']),
            ))
            parameters.extend([f'%{term}%', f'%{term}%', f'%{term}%'])
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _current_user_has_global_scope(cursor):
                    conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['id_column'])))
                    parameters.append(current_company_id())
                if conditions:
                    statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
                statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(layout['fields']['nome']))
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        field_names = (
            'id', 'nome', 'database', 'ativo', 'email', 'telefone', 'whatsapp',
            'plano', 'datainico', 'pago', 'titulo1', 'titulo2'
        )
        companies = []
        for row in rows:
            item = dict(zip(field_names, row))
            if hasattr(item.get('datainico'), 'isoformat'):
                item['datainico'] = item['datainico'].isoformat()
            companies.append(item)
        return jsonify({
            'success': True,
            'empresas': companies,
        })
    except Exception as exc:
        return _error_response(exc)


@empresa_api_bp.route('/api/empresas/permissao', methods=['POST'])
def empresa_permission():
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                return jsonify({'success': True, 'pode_editar': _current_user_is_master(cursor)})
    except Exception as exc:
        return _error_response(exc)


@empresa_api_bp.route('/api/empresas/planos', methods=['POST'])
def list_company_plans():
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''
                    SELECT idplano, plano
                    FROM public.ic_plano_geral
                    ORDER BY plano, idplano
                ''')
                rows = cursor.fetchall()
        return jsonify({
            'success': True,
            'planos': [{'id': row[0], 'nome': row[1] or ''} for row in rows],
        })
    except Exception as exc:
        return _error_response(exc)


def _subscription_plan_values(data):
    name = (data.get('plano') or '').strip()
    description = (data.get('descricao') or '').strip()
    if not name:
        raise ValueError('Informe o nome do plano.')
    if len(name) > 80:
        raise ValueError('O nome do plano deve ter no maximo 80 caracteres.')
    try:
        value = float(str(data.get('valor') or '0').replace(',', '.'))
    except ValueError as exc:
        raise ValueError('Informe um valor valido.') from exc
    if value < 0:
        raise ValueError('O valor nao pode ser negativo.')
    quantities = {}
    for field, label in (
        ('qtdusuarios', 'Quantidade de Usuarios'),
        ('qtdpacientes', 'Quantidade de Pacientes'),
        ('diasmax', 'Dias de uso'),
    ):
        try:
            quantities[field] = int(data.get(field) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{label} deve ser um numero inteiro.') from exc
        if quantities[field] < 0:
            raise ValueError(f'{label} nao pode ser negativa.')
        if quantities[field] > 2147483647:
            raise ValueError(f'{label} deve ser menor ou igual a 2.147.483.647.')
    flags = {}
    for field in ('confagenda', 'teleconsulta', 'financeiro', 'ditadovoz'):
        flag = str(data.get(field) or 'N').strip().upper()
        if flag not in ('S', 'N'):
            raise ValueError('Os campos de permissao devem ser Sim ou Nao.')
        flags[field] = flag
    maximum_date_text = str(data.get('datamax') or '').strip()
    maximum_date = None
    if maximum_date_text:
        try:
            maximum_date = date.fromisoformat(maximum_date_text)
        except ValueError as exc:
            raise ValueError('Informe uma Data Maxima valida.') from exc
    return {
        'plano': name, 'descricao': description or None, 'valor': value,
        'datamax': maximum_date, **quantities, **flags,
    }


@empresa_api_bp.route('/api/planos-empresa', methods=['POST'])
def list_subscription_plans():
    try:
        term = ((request.get_json(silent=True) or {}).get('termo') or '').strip()
        with _connection() as connection:
            with connection.cursor() as cursor:
                parameters = []
                where = sql.SQL('')
                if term:
                    where = sql.SQL(' WHERE CAST(idplano AS TEXT) ILIKE %s OR plano ILIKE %s')
                    parameters = [f'%{term}%', f'%{term}%']
                cursor.execute(sql.SQL('''
                    SELECT idplano, plano, COALESCE(descricao, ''), COALESCE(valor, 0),
                           COALESCE(qtdusuarios, 0), COALESCE(confagenda, 'N'),
                           COALESCE(qtdpacientes, 0), COALESCE("Teleconsulta", 'N'),
                           COALESCE("Financeiro", 'N'), COALESCE(ditadovoz, 'N'), datamax,
                           COALESCE(diasmax, 0)
                    FROM public.ic_plano_geral{}
                    ORDER BY plano, idplano
                ''').format(where), parameters)
                rows = cursor.fetchall()
        fields = ('id', 'plano', 'descricao', 'valor', 'qtdusuarios', 'confagenda',
                  'qtdpacientes', 'teleconsulta', 'financeiro', 'ditadovoz', 'datamax',
                  'diasmax')
        plans = []
        for row in rows:
            item = dict(zip(fields, row))
            if item.get('datamax'):
                item['datamax'] = item['datamax'].isoformat()
            plans.append(item)
        return jsonify({'success': True, 'planos': plans})
    except Exception as exc:
        return _error_response(exc)


@empresa_api_bp.route('/api/planos-empresa/itens', methods=['POST'])
def create_subscription_plan():
    try:
        values = _subscription_plan_values(request.get_json(silent=True) or {})
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master(cursor)
                cursor.execute(
                    'SELECT pg_advisory_xact_lock(hashtext(%s))',
                    ('public.ic_plano_geral',),
                )
                cursor.execute('SELECT COALESCE(MAX(idplano), 0) + 1 FROM public.ic_plano_geral')
                record_id = cursor.fetchone()[0]
                cursor.execute('''
                    INSERT INTO public.ic_plano_geral
                        (idplano, plano, descricao, valor, qtdusuarios, confagenda, qtdpacientes,
                         "Teleconsulta", "Financeiro", ditadovoz, datamax, diasmax)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (record_id,) + tuple(values[field] for field in (
                    'plano', 'descricao', 'valor', 'qtdusuarios', 'confagenda', 'qtdpacientes',
                    'teleconsulta', 'financeiro', 'ditadovoz', 'datamax', 'diasmax'
                )))
        return jsonify({'success': True, 'message': 'Plano incluido com sucesso.', 'id': record_id}), 201
    except Exception as exc:
        return _error_response(exc)


@empresa_api_bp.route('/api/planos-empresa/itens/<int:record_id>', methods=['PUT'])
def update_subscription_plan(record_id):
    try:
        values = _subscription_plan_values(request.get_json(silent=True) or {})
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master(cursor)
                cursor.execute('''
                    UPDATE public.ic_plano_geral SET
                        plano=%s, descricao=%s, valor=%s, qtdusuarios=%s, confagenda=%s,
                        qtdpacientes=%s, "Teleconsulta"=%s, "Financeiro"=%s, ditadovoz=%s,
                        datamax=%s, diasmax=%s
                    WHERE idplano=%s
                ''', tuple(values[field] for field in (
                    'plano', 'descricao', 'valor', 'qtdusuarios', 'confagenda', 'qtdpacientes',
                    'teleconsulta', 'financeiro', 'ditadovoz', 'datamax', 'diasmax'
                )) + (record_id,))
                updated = cursor.rowcount > 0
        if not updated:
            return jsonify({'success': False, 'message': 'Plano nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Plano alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@empresa_api_bp.route('/api/empresas/itens', methods=['POST'])
def create_empresa():
    try:
        layout = _layout()
        data = request.get_json(silent=True) or {}
        values = _empresa_values(data, layout)
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master(cursor)
                if _should_generate_integer_id(layout):
                    values[layout['id_column']] = _next_integer_id(cursor, layout)
                columns = list(values)
                statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}').format(
                    sql.Identifier('public'),
                    sql.Identifier(layout['table']),
                    sql.SQL(', ').join(sql.Identifier(column) for column in columns),
                    sql.SQL(', ').join(sql.Placeholder() for _ in columns),
                    sql.Identifier(layout['id_column']),
                )
                cursor.execute(statement, [values[column] for column in columns])
                record_id = cursor.fetchone()[0]
        return jsonify({'success': True, 'message': 'Empresa incluida com sucesso.', 'id': record_id}), 201
    except Exception as exc:
        return _error_response(exc)


@empresa_api_bp.route('/api/empresas/itens/<record_id>', methods=['PUT'])
def update_empresa(record_id):
    try:
        layout = _layout()
        values = _empresa_values(request.get_json(silent=True) or {}, layout)
        assignments = [
            sql.SQL('{} = %s').format(sql.Identifier(column))
            for column in values
        ]
        parameters = [values[column] for column in values] + [record_id]
        statement = sql.SQL('UPDATE {}.{} SET {} WHERE {} = %s').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(', ').join(assignments),
            sql.Identifier(layout['id_column']),
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master(cursor)
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute(statement, parameters)
                updated = cursor.rowcount > 0
        if not updated:
            return jsonify({'success': False, 'message': 'Empresa nao encontrada.'}), 404
        return jsonify({'success': True, 'message': 'Empresa alterada com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
