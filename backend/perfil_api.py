from contextlib import contextmanager
import re

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import errors, sql

from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import current_company_id


perfil_api_bp = Blueprint('perfil_api', __name__)

TABLE_CANDIDATES = ('ic_perfil_geral', 'icperfilgeral', 'Ic-perfil-geral')
ID_CANDIDATES = ('idperfil', 'id_perfil', 'codperfil', 'codigo', 'id')
FIELD_CANDIDATES = {
    'nome': ('perfil', 'nome', 'descricao'),
    'descricao': ('descricao', 'observacao', 'detalhe'),
    'ativo': ('ativo',),
    'verhist': ('verhist',),
    'verexame': ('verexame',),
    'codclin': ('codclin',),
}
for _menu_number in range(1, 16):
    FIELD_CANDIDATES[f'menu{_menu_number}'] = (f'menu{_menu_number}',)

MENU_PERMISSION_PATTERN = re.compile(r'^(?:[1-9]|1[0-5])-(?:AM|NAM)-(?:ET|NET)$')


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


def _ensure_default_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS public.ic_perfil_geral (
            idperfil SERIAL PRIMARY KEY,
            codclin INTEGER,
            perfil VARCHAR(60) NOT NULL,
            descricao VARCHAR(200) NOT NULL DEFAULT '',
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_por VARCHAR(120) NOT NULL DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS ic_perfil_geral_codclin_perfil_uidx
        ON public.ic_perfil_geral (codclin, lower(perfil))
    ''')


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
        fields = {}
        for logical_name, candidates in FIELD_CANDIDATES.items():
            column = _pick(columns, candidates)
            if column:
                fields[logical_name] = column['name']
        if 'nome' not in fields:
            continue
        id_column = _pick(columns, ID_CANDIDATES)
        return {
            'table': table_name or table_candidate,
            'id_column': id_column['name'] if id_column else fields['nome'],
            'id_type': id_column['data_type'] if id_column else '',
            'id_is_name': id_column is None,
            'fields': fields,
        }
    _ensure_default_table(cursor)
    return _detect_layout(cursor)


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


def _record_is_master(cursor, layout, record_id):
    conditions = [sql.SQL('{} = %s').format(sql.Identifier(layout['id_column']))]
    parameters = [record_id]
    if 'codclin' in layout['fields']:
        conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['fields']['codclin'])))
        parameters.append(current_company_id())
    statement = sql.SQL('SELECT {} FROM {}.{} WHERE {} LIMIT 1').format(
        sql.Identifier(layout['fields']['nome']),
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.SQL(' AND ').join(conditions),
    )
    cursor.execute(statement, parameters)
    row = cursor.fetchone()
    return _is_master_profile(row[0] if row else '')


def _require_master_for_master_profile(cursor, layout, requested_name='', record_id=None):
    touches_master = _is_master_profile(requested_name)
    if record_id is not None:
        touches_master = touches_master or _record_is_master(cursor, layout, record_id)
    if touches_master and not _current_user_is_master(cursor):
        raise PermissionError('Apenas usuários com perfil MASTER podem criar, alterar ou excluir o perfil MASTER.')


def _profile_values(data, layout):
    nome = (data.get('nome') or '').strip()
    descricao = (data.get('descricao') or '').strip()
    if not nome:
        raise ValueError('Informe o nome do perfil.')
    if len(nome) > 60:
        raise ValueError('O nome do perfil deve ter no máximo 60 caracteres.')
    if len(descricao) > 200:
        raise ValueError('A descrição deve ter no máximo 200 caracteres.')

    values = {layout['fields']['nome']: nome}
    if 'descricao' in layout['fields']:
        values[layout['fields']['descricao']] = descricao
    if 'ativo' in layout['fields']:
        values[layout['fields']['ativo']] = bool(data.get('ativo', True))
    for logical_name in ('verhist', 'verexame'):
        if logical_name not in layout['fields']:
            continue
        informed_value = str(data.get(logical_name, 'SIM') or 'SIM').strip().upper()
        values[layout['fields'][logical_name]] = (
            'NÃO' if informed_value in ('N', 'NAO', 'NÃO', 'FALSE', '0') else 'SIM'
        )
    selected_menus = set()
    for menu_number in range(1, 16):
        logical_name = f'menu{menu_number}'
        if logical_name not in layout['fields']:
            continue
        permission = (data.get(logical_name) or '').strip().upper()
        if not permission:
            permission = f'{menu_number}-AM-ET'
        if not MENU_PERMISSION_PATTERN.fullmatch(permission):
            raise ValueError(f'Permissão inválida no Menu {menu_number}.')
        selected_menu = permission.split('-', 1)[0]
        if selected_menu in selected_menus:
            raise ValueError('Cada menu deve aparecer apenas uma vez nas permissões do perfil.')
        selected_menus.add(selected_menu)
        values[layout['fields'][logical_name]] = permission
    return values


def _should_generate_integer_id(layout):
    if layout.get('id_is_name'):
        return False
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
        if logical_name == 'ativo':
            fallback = 'TRUE'
        elif logical_name in ('verhist', 'verexame'):
            fallback = "'SIM'"
        else:
            fallback = "''"
        return sql.SQL('{} AS {}').format(sql.SQL(fallback), sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _conditions(layout, term=''):
    conditions = []
    parameters = []
    tenant_column = layout['fields'].get('codclin')
    if tenant_column:
        conditions.append(sql.SQL('{} = %s').format(sql.Identifier(tenant_column)))
        parameters.append(current_company_id())
    if term:
        descricao_column = layout['fields'].get('descricao', layout['fields']['nome'])
        conditions.append(sql.SQL('({} ILIKE %s OR COALESCE({}, %s) ILIKE %s)').format(
            sql.Identifier(layout['fields']['nome']),
            sql.Identifier(descricao_column),
            sql.Placeholder(),
        ))
        parameters.extend([f'%{term}%', '', f'%{term}%'])
    return conditions, parameters


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, PermissionError):
        return jsonify({'success': False, 'message': str(exc)}), 403
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({'success': False, 'message': 'Já existe um perfil com este nome.'}), 409
    current_app.logger.exception('Falha na operação de perfil', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@perfil_api_bp.route('/api/perfis', methods=['POST'])
def list_perfis():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        layout = _layout()
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
            _select_expression(layout, 'nome'),
            _select_expression(layout, 'descricao'),
            _select_expression(layout, 'ativo'),
            _select_expression(layout, 'verhist'),
            _select_expression(layout, 'verexame'),
        ] + [_select_expression(layout, f'menu{number}') for number in range(1, 16)]
        statement = sql.SQL('SELECT {} FROM {}.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        conditions, parameters = _conditions(layout, term)
        if conditions:
            statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
        statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(layout['fields']['nome']))
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
                usuario_master = _current_user_is_master(cursor)
        return jsonify({
            'success': True,
            'perfis': [dict(zip(
                ('id', 'nome', 'descricao', 'ativo', 'verhist', 'verexame')
                + tuple(f'menu{number}' for number in range(1, 16)),
                row
            )) for row in rows],
            'usuario_master': usuario_master,
        })
    except Exception as exc:
        return _error_response(exc)


@perfil_api_bp.route('/api/perfis/opcoes', methods=['POST'])
def profile_options():
    """Retorna somente os dados necessários ao combobox de usuários."""
    try:
        layout = _layout()
        statement = sql.SQL('SELECT {}, {}, {} FROM {}.{}').format(
            sql.Identifier(layout['id_column']),
            sql.Identifier(layout['fields']['nome']),
            sql.Identifier(layout['fields'].get('descricao', layout['fields']['nome'])),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        conditions, parameters = _conditions(layout)
        if 'ativo' in layout['fields']:
            conditions.append(sql.SQL('{} IS NOT FALSE').format(sql.Identifier(layout['fields']['ativo'])))
        if conditions:
            statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
        statement += sql.SQL(' ORDER BY {}').format(sql.Identifier(layout['fields']['nome']))
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
                usuario_master = _current_user_is_master(cursor)
        return jsonify({
            'success': True,
            'perfis': [dict(zip(('id', 'nome', 'descricao'), row)) for row in rows],
            'usuario_master': usuario_master,
        })
    except Exception as exc:
        return _error_response(exc)


@perfil_api_bp.route('/api/perfis/itens', methods=['POST'])
def create_perfil():
    try:
        layout = _layout()
        values = _profile_values(request.get_json(silent=True) or {}, layout)
        if 'codclin' in layout['fields']:
            values[layout['fields']['codclin']] = current_company_id()
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master_for_master_profile(
                    cursor, layout, values.get(layout['fields']['nome'], '')
                )
                if _should_generate_integer_id(layout):
                    values[layout['id_column']] = _next_integer_id(cursor, layout)
                columns = list(values)
                placeholders = [sql.Placeholder()] * len(columns)
                statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}').format(
                    sql.Identifier('public'),
                    sql.Identifier(layout['table']),
                    sql.SQL(', ').join(sql.Identifier(column) for column in columns),
                    sql.SQL(', ').join(placeholders),
                    sql.Identifier(layout['id_column']),
                )
                cursor.execute(statement, [values[column] for column in columns])
                record_id = cursor.fetchone()[0]
        return jsonify({'success': True, 'message': 'Perfil incluído com sucesso.', 'id': record_id}), 201
    except Exception as exc:
        return _error_response(exc)


@perfil_api_bp.route('/api/perfis/itens/<record_id>', methods=['PUT'])
def update_perfil(record_id):
    try:
        layout = _layout()
        values = _profile_values(request.get_json(silent=True) or {}, layout)
        assignments = [
            sql.SQL('{} = %s').format(sql.Identifier(column))
            for column in values
        ]
        conditions = [sql.SQL('{} = %s').format(sql.Identifier(layout['id_column']))]
        parameters = [values[column] for column in values] + [record_id]
        if 'codclin' in layout['fields']:
            conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['fields']['codclin'])))
            parameters.append(current_company_id())
        statement = sql.SQL('UPDATE {}.{} SET {} WHERE {}').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(', ').join(assignments),
            sql.SQL(' AND ').join(conditions),
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master_for_master_profile(
                    cursor, layout, values.get(layout['fields']['nome'], ''), record_id
                )
                cursor.execute(statement, parameters)
                updated = cursor.rowcount > 0
        if not updated:
            return jsonify({'success': False, 'message': 'Perfil não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Perfil alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@perfil_api_bp.route('/api/perfis/itens/<record_id>', methods=['DELETE'])
def delete_perfil(record_id):
    try:
        layout = _layout()
        conditions = [sql.SQL('{} = %s').format(sql.Identifier(layout['id_column']))]
        parameters = [record_id]
        if 'codclin' in layout['fields']:
            conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['fields']['codclin'])))
            parameters.append(current_company_id())
        statement = sql.SQL('DELETE FROM {}.{} WHERE {}').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(' AND ').join(conditions),
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                _require_master_for_master_profile(cursor, layout, record_id=record_id)
                cursor.execute(statement, parameters)
                deleted = cursor.rowcount > 0
        if not deleted:
            return jsonify({'success': False, 'message': 'Perfil não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Perfil excluído com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
