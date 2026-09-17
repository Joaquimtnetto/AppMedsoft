from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import errors
from psycopg2 import sql

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import TENANT_COLUMN, current_company_id

plano_api_bp = Blueprint('plano_api', __name__)

TABLE_CANDIDATES = ('plano',)
ID_CANDIDATES = ('nomeplano',)
FIELD_CANDIDATES = {
    'nome': ('nomeplano',),
    'tabela': ('tabela', 'tab', 'nometabela'),
    'ans': ('reg_ans', 'ans', 'registro_ans', 'codans'),
    'endereco': ('endereco', 'ender', 'logradouro'),
    'bairro': ('bairro',),
    'cidade': ('cidade',),
    'cep': ('cep',),
    'banco': ('banco',),
    'prazo': ('prazo',),
    'valorch': ('valor_ch', 'valorch', 'valch', 'ch'),
    'telefone': ('tel', 'telefone', 'fone'),
    'observacao': ('obs', 'observacao', 'observacoes'),
}

MAX_LENGTHS = {
    'nome': 25,
    'tabela': 10,
    'ans': 20,
    'endereco': 40,
    'bairro': 15,
    'cidade': 10,
    'cep': 9,
    'banco': 15,
    'telefone': 13,
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
            'tenant_column': (_pick(columns, (TENANT_COLUMN,)) or {}).get('name'),
        }
    raise ValueError('Tabela public.plano nao encontrada no banco.')


def _layout():
    with _connection() as connection:
        with connection.cursor() as cursor:
            return _detect_layout(cursor)


def _repository(layout):
    if not layout['tenant_column']:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.PLANO.')
    return CrudRepository(
        connection_factory=_connection,
        table=layout['table'],
        id_column=layout['id_column'],
        writable_columns=tuple(layout['fields'].values()),
        generate_integer_id=layout['generate_integer_id'],
        tenant_column=layout['tenant_column'],
        tenant_value_factory=current_company_id,
    )


def _plan_data(data, layout):
    nome = (data.get('nome') or '').strip()
    if not nome:
        raise ValueError('Informe o nome do plano.')

    values = {}
    for logical_name, column_name in layout['fields'].items():
        value = (data.get(logical_name) or '').strip()
        if value and logical_name in MAX_LENGTHS and len(value) > MAX_LENGTHS[logical_name]:
            raise ValueError(f'O campo {logical_name} excede {MAX_LENGTHS[logical_name]} caracteres.')
        if value and logical_name == 'prazo':
            try:
                value = int(value)
            except ValueError as exc:
                raise ValueError('Prazo deve ser um numero inteiro.') from exc
        if value and logical_name == 'valorch':
            try:
                value = Decimal(value.replace(',', '.'))
            except InvalidOperation as exc:
                raise ValueError('Valor CH deve ser numerico.') from exc
        values[column_name] = None if value == '' else value
    values[layout['fields']['nome']] = nome
    return values


def _visible_plan_name(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    marker = value.rfind(' [')
    suffix = value[marker + 2:-1] if marker > 0 and value.endswith(']') else ''
    if suffix and suffix.replace('-', '').isdigit():
        return value[:marker].strip()
    return value


def _stored_plan_name(cursor, layout, visible_name, current_id=None):
    tenant_column = layout.get('tenant_column')
    name_column = layout['fields']['nome']
    if not tenant_column:
        raise ValueError('Campo CODCLIN nÃ£o encontrado na tabela public.PLANO.')
    company_id = current_company_id()
    current_id = None if current_id is None else str(current_id)
    cursor.execute(
        sql.SQL('SELECT {}, {} FROM {}.{}').format(
            sql.Identifier(layout['id_column']),
            sql.Identifier(tenant_column),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
    )
    rows = cursor.fetchall()
    max_length = MAX_LENGTHS.get('nome', 25)
    used_ids = {str(row[0]) for row in rows if current_id is None or str(row[0]) != current_id}
    if visible_name not in used_ids:
        return visible_name
    for index in range(1, 100):
        suffix = f' [{company_id}]' if index == 1 else f' [{company_id}-{index}]'
        base_name = visible_name
        if len(base_name) + len(suffix) > max_length:
            base_name = base_name[:max_length - len(suffix)].rstrip()
        candidate = base_name + suffix
        if candidate not in used_ids:
            return candidate
    raise ValueError('Nao foi possivel gerar um nome interno unico para este plano.')


def _fallback_plan_name(base_name, attempt):
    company_id = current_company_id()
    max_length = MAX_LENGTHS.get('nome', 25)
    suffix = f' [{company_id}-{attempt}]'
    if len(base_name) + len(suffix) > max_length:
        base_name = base_name[:max_length - len(suffix)].rstrip()
    return base_name + suffix


def _normalize_plan_item(item):
    if isinstance(item.get('nome'), str):
        item['nome'] = _visible_plan_name(item['nome'])
    return item


def _select_expression(layout, logical_name):
    column_name = layout['fields'].get(logical_name)
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        current_app.logger.exception('Restricao unica ao salvar plano', exc_info=exc)
        return jsonify({'success': False, 'message': 'Nao foi possivel salvar o plano. Atualize a tela e tente novamente.'}), 409
    if isinstance(exc, errors.StringDataRightTruncation):
        return jsonify({'success': False, 'message': 'Um dos campos ultrapassa o tamanho permitido.'}), 400
    if isinstance(exc, (errors.InvalidTextRepresentation, errors.NumericValueOutOfRange)):
        return jsonify({'success': False, 'message': 'Verifique os campos numericos informados.'}), 400
    current_app.logger.exception('Falha na operacao do plano', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@plano_api_bp.route('/api/planos', methods=['POST'])
def list_plans():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        layout = _layout()
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
        ] + [_select_expression(layout, field) for field in FIELD_CANDIDATES]

        statement = sql.SQL('SELECT {} FROM {}.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        tenant_column = layout['tenant_column']
        if not tenant_column:
            raise ValueError('Campo CODCLIN não encontrado na tabela public.PLANO.')
        conditions = [sql.SQL('{} = %s').format(sql.Identifier(tenant_column))]
        parameters = [current_company_id()]
        if term:
            conditions.append(sql.SQL('(CAST({} AS TEXT) ILIKE %s OR {} ILIKE %s)').format(
                sql.Identifier(layout['id_column']),
                sql.Identifier(layout['fields']['nome']),
            ))
            parameters.extend([f'%{term}%', f'%{term}%'])
        statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
        statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(layout['fields']['nome']))

        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        field_names = ['id'] + list(FIELD_CANDIDATES)
        return jsonify({
            'success': True,
            'planos': [_normalize_plan_item(dict(zip(field_names, row))) for row in rows],
        })
    except Exception as exc:
        return _error_response(exc)


@plano_api_bp.route('/api/planos/opcoes', methods=['POST'])
def list_all_plan_options():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        layout = _layout()
        select_items = [sql.SQL('{} AS id').format(sql.Identifier(layout['id_column']))]
        select_items += [_select_expression(layout, field) for field in FIELD_CANDIDATES]
        select_items.append(
            sql.SQL('{} AS empresa_id').format(sql.Identifier(layout['tenant_column']))
        )
        statement = sql.SQL('SELECT {} FROM public.{}').format(
            sql.SQL(', ').join(select_items), sql.Identifier(layout['table'])
        )
        parameters = []
        if term:
            statement += sql.SQL(' WHERE (CAST({} AS TEXT) ILIKE %s OR {} ILIKE %s)').format(
                sql.Identifier(layout['id_column']), sql.Identifier(layout['fields']['nome'])
            )
            parameters.extend([f'%{term}%', f'%{term}%'])
        statement += sql.SQL(' ORDER BY {}, {} LIMIT 500').format(
            sql.Identifier(layout['fields']['nome']), sql.Identifier(layout['tenant_column'])
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        field_names = ['id'] + list(FIELD_CANDIDATES) + ['empresa_id']
        plans = []
        for row in rows:
            item = _normalize_plan_item(dict(zip(field_names, row)))
            item['_option_key'] = str(item['id']) + ':' + str(item['empresa_id'])
            plans.append(item)
        return jsonify({'success': True, 'planos': plans})
    except Exception as exc:
        return _error_response(exc)


@plano_api_bp.route('/api/planos/itens', methods=['POST'])
def create_plan():
    try:
        layout = _layout()
        item = _plan_data(request.get_json(silent=True) or {}, layout)
        visible_name = item[layout['fields']['nome']]
        with _connection() as connection:
            with connection.cursor() as cursor:
                item[layout['fields']['nome']] = _stored_plan_name(
                    cursor, layout, visible_name
                )
        for attempt in range(1, 20):
            try:
                plan_id = _repository(layout).create(item)
                break
            except errors.UniqueViolation:
                item[layout['fields']['nome']] = _fallback_plan_name(visible_name, attempt)
        else:
            raise ValueError('Nao foi possivel gerar um nome interno unico para este plano.')
        return jsonify({
            'success': True,
            'message': 'Plano incluido com sucesso.',
            'id': plan_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@plano_api_bp.route('/api/planos/itens/<plan_id>', methods=['PUT'])
def update_plan(plan_id):
    try:
        layout = _layout()
        item = _plan_data(request.get_json(silent=True) or {}, layout)
        visible_name = item[layout['fields']['nome']]
        with _connection() as connection:
            with connection.cursor() as cursor:
                item[layout['fields']['nome']] = _stored_plan_name(
                    cursor, layout, visible_name, plan_id
                )
        for attempt in range(1, 20):
            try:
                updated = _repository(layout).update(plan_id, item)
                break
            except errors.UniqueViolation:
                item[layout['fields']['nome']] = _fallback_plan_name(visible_name, attempt)
        else:
            raise ValueError('Nao foi possivel gerar um nome interno unico para este plano.')
        if not updated:
            return jsonify({'success': False, 'message': 'Plano nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Plano alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@plano_api_bp.route('/api/planos/itens/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    try:
        deleted = _repository(_layout()).delete(plan_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Plano nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Plano excluido com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
