from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import errors, sql

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import current_company_id

clinica_api_bp = Blueprint('clinica_api', __name__)

TABLE_CANDIDATES = ('clinica',)
ID_CANDIDATES = ('codclin', 'codcli', 'cod', 'codigo', 'id')
FIELD_CANDIDATES = {
    'idempresa': ('idempresa', 'id_empresa', 'id-empresa'),
    'nome': ('nome', 'nomeclin', 'nomecli', 'nomclin', 'razao_social'),
    'uf': ('uf', 'ufclin', 'estado'),
    'municipio': ('municipio', 'cidade', 'cidclin'),
    'endereco': ('endereco', 'end', 'ender', 'logradouro'),
    'bairro': ('bairro', 'bai', 'baiclin'),
    'cep': ('cep',),
    'especialidade': ('especialidade', 'especialid', 'especial'),
    'nrconselho': ('nrconselho', 'nr_conselho', 'numconselho'),
    'conselho': ('conselho', 'cons'),
    'cnpj': ('cnpj', 'cgc'),
    'telefone': ('telefone', 'tel', 'fone', 'tel1'),
    'celular': ('celular', 'cel', 'whatsapp', 'tel1', 'tel2'),
    'email': ('email', 'e_mail'),
    'observacao': ('observacao', 'obs'),
}

MAX_LENGTHS = {
    'nome': 60,
    'uf': 2,
    'municipio': 30,
    'endereco': 60,
    'bairro': 30,
    'cep': 9,
    'especialidade': 40,
    'nrconselho': 20,
    'conselho': 20,
    'cnpj': 18,
    'telefone': 14,
    'celular': 14,
    'email': 60,
    'observacao': 400,
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


def _fetch_table_columns(cursor, table_name):
    cursor.execute("""
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = %s
    """, (table_name,))
    return {
        row[0].lower(): {
            'name': row[0],
            'data_type': row[1] or '',
            'default': row[2],
        }
        for row in cursor.fetchall()
    }


def _pick(columns, candidates):
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def _detect_layout(cursor):
    for table_candidate in TABLE_CANDIDATES:
        columns = _fetch_table_columns(cursor, table_candidate)
        if not columns:
            continue
        id_column = _pick(columns, ID_CANDIDATES)
        nome_column = _pick(columns, FIELD_CANDIDATES['nome'])
        if not id_column or not nome_column:
            continue
        fields = {}
        for logical_name, candidates in FIELD_CANDIDATES.items():
            column = _pick(columns, candidates)
            if column:
                fields[logical_name] = column['name']
        generate_integer_id = (
            id_column['default'] is None and
            any(kind in id_column['data_type'].lower() for kind in ('integer', 'bigint', 'smallint'))
        )
        return {
            'table': table_candidate,
            'id_column': id_column['name'],
            'fields': fields,
            'generate_integer_id': generate_integer_id,
        }
    raise ValueError('Tabela public.CLINICA nao encontrada no banco.')


def _layout():
    with _connection() as connection:
        with connection.cursor() as cursor:
            return _detect_layout(cursor)


def _repository(layout):
    return CrudRepository(
        connection_factory=_connection,
        table=layout['table'],
        id_column=layout['id_column'],
        writable_columns=tuple(layout['fields'].values()),
        generate_integer_id=layout['generate_integer_id'],
    )


def _clinica_data(data, layout):
    nome = (data.get('nome') or '').strip()
    if not nome:
        raise ValueError('Informe o nome da clinica.')

    values = {}
    for logical_name, column_name in layout['fields'].items():
        value = (data.get(logical_name) or '').strip()
        if logical_name == 'idempresa':
            if not value:
                raise ValueError('Informe a empresa da clinica.')
            try:
                values[column_name] = int(value)
            except ValueError as exc:
                raise ValueError('Informe uma empresa valida para a clinica.') from exc
            continue
        if value and logical_name in MAX_LENGTHS and len(value) > MAX_LENGTHS[logical_name]:
            raise ValueError(f'O campo {logical_name} excede {MAX_LENGTHS[logical_name]} caracteres.')
        values[column_name] = None if value == '' else value
    values[layout['fields']['nome']] = nome
    return values


def _select_expression(layout, logical_name):
    column_name = layout['fields'].get(logical_name)
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _empresa_name_expression(layout):
    return sql.SQL("'' AS idempresa_nome")


def _table_exists(cursor, table_name):
    cursor.execute("SELECT to_regclass(%s)", (f'public.{table_name}',))
    row = cursor.fetchone()
    return bool(row and row[0])


def _profile_is_master(profile_name):
    return (profile_name or '').strip().upper() == 'MASTER'


def _current_user_profile(cursor):
    session_profile = session.get('perfil')
    if session_profile:
        return session_profile

    user_id = session.get('idusuario')
    if user_id and _table_exists(cursor, 'ic_usuario_geral') and _table_exists(cursor, 'ic_perfil_geral'):
        cursor.execute("""
            SELECT COALESCE(perfil.nome, perfil.descricao, '')
            FROM public.ic_usuario_geral usuario
            LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = usuario.idperfil
            WHERE usuario.idusuario = %s
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]

    login_name = session.get('usuario')
    if login_name and _table_exists(cursor, 'senha'):
        cursor.execute("""
            SELECT COALESCE(perfil, '')
            FROM public.senha
            WHERE nome = %s
            LIMIT 1
        """, (login_name,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]

    return ''


def _current_user_is_master(cursor):
    return _profile_is_master(_current_user_profile(cursor))


def _record_belongs_to_current_company(cursor, layout, record_id):
    company_column = layout['fields'].get('idempresa')
    if not company_column:
        return True
    cursor.execute(sql.SQL('''
        SELECT 1
        FROM {}.{}
        WHERE {} = %s AND {} = %s
        LIMIT 1
    ''').format(
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.Identifier(layout['id_column']),
        sql.Identifier(company_column),
    ), (record_id, current_company_id()))
    return cursor.fetchone() is not None


def _can_include_clinica():
    with _connection() as connection:
        with connection.cursor() as cursor:
            return _current_user_is_master(cursor)


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({'success': False, 'message': 'Ja existe uma clinica com este codigo.'}), 409
    if isinstance(exc, errors.StringDataRightTruncation):
        return jsonify({'success': False, 'message': 'Um dos campos ultrapassa o tamanho permitido.'}), 400
    current_app.logger.exception('Falha na operacao da clinica', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@clinica_api_bp.route('/api/clinicas/permissao', methods=['POST'])
def clinica_permission():
    try:
        return jsonify({
            'success': True,
            'pode_incluir': _can_include_clinica(),
        })
    except Exception as exc:
        return _error_response(exc)


@clinica_api_bp.route('/api/clinicas', methods=['POST'])
def list_clinicas():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        layout = _layout()
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
        ] + [_select_expression(layout, field) for field in FIELD_CANDIDATES] + [
            _empresa_name_expression(layout),
        ]

        statement = sql.SQL('SELECT {} FROM {}.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                conditions = []
                parameters = []
                if 'idempresa' in layout['fields'] and not _current_user_is_master(cursor):
                    conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['fields']['idempresa'])))
                    parameters.append(current_company_id())
                if term:
                    conditions.append(sql.SQL('(CAST({} AS TEXT) ILIKE %s OR {} ILIKE %s)').format(
                        sql.Identifier(layout['id_column']),
                        sql.Identifier(layout['fields']['nome']),
                    ))
                    parameters.extend([f'%{term}%', f'%{term}%'])
                if conditions:
                    statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
                statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(layout['fields']['nome']))
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        field_names = ['id'] + list(FIELD_CANDIDATES) + ['idempresa_nome']
        return jsonify({
            'success': True,
            'clinicas': [dict(zip(field_names, row)) for row in rows],
        })
    except Exception as exc:
        return _error_response(exc)


@clinica_api_bp.route('/api/clinicas/itens', methods=['POST'])
def create_clinica():
    try:
        if not _can_include_clinica():
            return jsonify({
                'success': False,
                'message': 'Apenas usuarios com perfil MASTER podem incluir clinica.',
            }), 403
        layout = _layout()
        item = _clinica_data(request.get_json(silent=True) or {}, layout)
        record_id = _repository(layout).create(item)
        return jsonify({
            'success': True,
            'message': 'Clinica incluida com sucesso.',
            'id': record_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@clinica_api_bp.route('/api/clinicas/itens/<record_id>', methods=['PUT'])
def update_clinica(record_id):
    try:
        layout = _layout()
        item = _clinica_data(request.get_json(silent=True) or {}, layout)
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _current_user_is_master(cursor):
                    if not _record_belongs_to_current_company(cursor, layout, record_id):
                        return jsonify({'success': False, 'message': 'Clinica nao encontrada.'}), 404
                    if 'idempresa' in layout['fields']:
                        item[layout['fields']['idempresa']] = current_company_id()
        updated = _repository(layout).update(record_id, item)
        if not updated:
            return jsonify({'success': False, 'message': 'Clinica nao encontrada.'}), 404
        return jsonify({'success': True, 'message': 'Clinica alterada com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@clinica_api_bp.route('/api/clinicas/itens/<record_id>', methods=['DELETE'])
def delete_clinica(record_id):
    try:
        layout = _layout()
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _current_user_is_master(cursor) and not _record_belongs_to_current_company(cursor, layout, record_id):
                    return jsonify({'success': False, 'message': 'Clinica nao encontrada.'}), 404
        deleted = _repository(layout).delete(record_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Clinica nao encontrada.'}), 404
        return jsonify({'success': True, 'message': 'Clinica excluida com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
