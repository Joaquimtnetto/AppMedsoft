from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request, session
from medsoft_core import DBConnectionError, get_db_connection
from psycopg2 import errors, sql
from tenant_context import TENANT_COLUMN, current_company_id


procedimento_api_bp = Blueprint('procedimento_api', __name__)


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


def _fetch_columns(cursor):
    cursor.execute("""
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'amb'
    """)
    table_name = None
    columns = {}
    metadata = {}
    for row in cursor.fetchall():
        table_name = row[0]
        columns[row[1].lower()] = row[1]
        metadata[row[1].lower()] = {
            'name': row[1],
            'data_type': row[2] or '',
            'nullable': row[3] == 'YES',
            'default': row[4],
        }
    return table_name, columns, metadata


def _layout(cursor):
    table_name, columns, metadata = _fetch_columns(cursor)
    description = columns.get('descamb')
    value = columns.get('valor')
    health_professional_rate = columns.get('percrateio')
    plan = None
    for candidate in ('nomeplano', 'plano', 'nomeplano1', 'convenio'):
        if candidate in columns:
            plan = columns[candidate]
            break
    if not table_name or not description or not value:
        raise ValueError('A tabela public.AMB precisa possuir os campos DescAmb e Valor.')
    tenant_column = columns.get(TENANT_COLUMN)
    id_column = None
    for candidate in ('codamb', 'codigo', 'cod', 'idamb', 'id'):
        info = metadata.get(candidate)
        if not info:
            continue
        is_integer = any(kind in info['data_type'].lower() for kind in ('integer', 'bigint', 'smallint'))
        if is_integer:
            id_column = info['name']
            break
    return {
        'table': table_name,
        'id_column': id_column,
        'description': description,
        'plan': plan,
        'value': value,
        'health_professional_rate': health_professional_rate,
        'tenant_column': tenant_column,
    }


def _format_value(value):
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return str(value.normalize())
    return str(value)


def _procedure_data(data):
    description = (data.get('descricao') or '').strip()
    if not description:
        raise ValueError('Informe a descricao do procedimento.')
    plan = (data.get('plano') or '').strip()
    if not plan:
        raise ValueError('Informe o plano do procedimento.')
    value = str(data.get('valor') or '').strip()
    if value:
        try:
            value = Decimal(value.replace(',', '.'))
        except InvalidOperation as exc:
            raise ValueError('Valor deve ser numerico.') from exc
    health_professional_rate = str(data.get('percrateio') or '').strip()
    if health_professional_rate:
        try:
            health_professional_rate = Decimal(health_professional_rate.replace(',', '.'))
        except InvalidOperation as exc:
            raise ValueError('Prof. Saude (%) deve ser um numero inteiro.') from exc
        if (
            not health_professional_rate.is_finite()
            or health_professional_rate < 0
            or health_professional_rate > 100
        ):
            raise ValueError('Prof. Saude (%) deve estar entre 0 e 100.')
        if health_professional_rate != health_professional_rate.to_integral_value():
            raise ValueError('Prof. Saude (%) deve ser um numero inteiro.')
        health_professional_rate = int(health_professional_rate)
    return (
        description,
        plan,
        value if value != '' else None,
        health_professional_rate if health_professional_rate != '' else None,
    )


def _scope_conditions(layout):
    conditions = [sql.SQL('{} = %s').format(sql.Identifier(layout['id_column']))]
    if layout['tenant_column']:
        conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['tenant_column'])))
    return conditions


def _scope_parameters(record_id, layout):
    parameters = [record_id]
    if layout['tenant_column']:
        parameters.append(current_company_id())
    return parameters


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({'success': False, 'message': 'Ja existe um procedimento com estes dados.'}), 409
    if isinstance(exc, errors.StringDataRightTruncation):
        return jsonify({'success': False, 'message': 'Um dos campos ultrapassa o tamanho permitido.'}), 400
    if isinstance(exc, (errors.InvalidTextRepresentation, errors.NumericValueOutOfRange)):
        return jsonify({'success': False, 'message': 'Verifique o valor informado.'}), 400
    current_app.logger.exception('Falha na consulta de procedimentos', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@procedimento_api_bp.route('/api/procedimentos', methods=['POST'])
def list_procedures():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()

        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _layout(cursor)
                if not layout['id_column']:
                    raise ValueError('A tabela public.AMB precisa possuir um campo codigo.')
                select_items = [
                    sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
                    sql.SQL('{} AS descricao').format(sql.Identifier(layout['description'])),
                    (
                        sql.SQL('{} AS plano').format(sql.Identifier(layout['plan']))
                        if layout['plan'] else sql.SQL("'' AS plano")
                    ),
                    sql.SQL('{} AS valor').format(sql.Identifier(layout['value'])),
                    (
                        sql.SQL('{} AS percrateio').format(sql.Identifier(layout['health_professional_rate']))
                        if layout['health_professional_rate'] else sql.SQL("NULL AS percrateio")
                    ),
                ]
                statement = sql.SQL('SELECT {} FROM public.{}').format(
                    sql.SQL(', ').join(select_items),
                    sql.Identifier(layout['table'])
                )
                parameters = []
                conditions = []
                if layout['tenant_column']:
                    conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['tenant_column'])))
                    parameters.append(current_company_id())
                if term:
                    search_conditions = [
                        sql.SQL('{} ILIKE %s').format(sql.Identifier(layout['description'])),
                        sql.SQL('CAST({} AS TEXT) ILIKE %s').format(sql.Identifier(layout['value'])),
                    ]
                    parameters.extend([f'%{term}%', f'%{term}%'])
                    if layout['plan']:
                        search_conditions.append(sql.SQL('{} ILIKE %s').format(sql.Identifier(layout['plan'])))
                        parameters.append(f'%{term}%')
                    conditions.append(sql.SQL('(') + sql.SQL(' OR ').join(search_conditions) + sql.SQL(')'))
                if conditions:
                    statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
                statement += sql.SQL(' ORDER BY {} LIMIT 200').format(
                    sql.Identifier(layout['description'])
                )
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        return jsonify({
            'success': True,
            'procedimentos': [
                {
                    'id': row[0],
                    'descricao': row[1] or '',
                    'plano': row[2] or '',
                    'valor': _format_value(row[3]),
                    'percrateio': _format_value(row[4]),
                }
                for row in rows
            ],
        })
    except Exception as exc:
        return _error_response(exc)


@procedimento_api_bp.route('/api/procedimentos/itens', methods=['POST'])
def create_procedure():
    try:
        description, plan, value, health_professional_rate = _procedure_data(
            request.get_json(silent=True) or {}
        )

        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _layout(cursor)
                if not layout['plan']:
                    raise ValueError('A tabela public.AMB precisa possuir um campo de plano.')
                if not layout['health_professional_rate']:
                    raise ValueError('A tabela public.AMB precisa possuir o campo PercRateio.')
                columns = [
                    layout['description'],
                    layout['plan'],
                    layout['value'],
                    layout['health_professional_rate'],
                ]
                values = [description, plan, value, health_professional_rate]
                if layout['tenant_column']:
                    columns.append(layout['tenant_column'])
                    values.append(current_company_id())
                if layout['id_column']:
                    cursor.execute(
                        'SELECT pg_advisory_xact_lock(hashtext(%s))',
                        (f"public.{layout['table']}",),
                    )
                    cursor.execute(sql.SQL('SELECT COALESCE(MAX({}), 0) + 1 FROM public.{}').format(
                        sql.Identifier(layout['id_column']),
                        sql.Identifier(layout['table']),
                    ))
                    columns.insert(0, layout['id_column'])
                    values.insert(0, cursor.fetchone()[0])
                cursor.execute(
                    sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(
                        sql.Identifier(layout['table']),
                        sql.SQL(', ').join(map(sql.Identifier, columns)),
                        sql.SQL(', ').join(sql.Placeholder() for _ in columns),
                    ),
                    values,
                )

        return jsonify({
            'success': True,
            'message': 'Procedimento incluido com sucesso.',
        }), 201
    except Exception as exc:
        return _error_response(exc)


@procedimento_api_bp.route('/api/procedimentos/itens/<record_id>', methods=['PUT'])
def update_procedure(record_id):
    try:
        description, plan, value, health_professional_rate = _procedure_data(
            request.get_json(silent=True) or {}
        )

        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _layout(cursor)
                if not layout['id_column']:
                    raise ValueError('A tabela public.AMB precisa possuir um campo codigo.')
                if not layout['plan']:
                    raise ValueError('A tabela public.AMB precisa possuir um campo de plano.')
                if not layout['health_professional_rate']:
                    raise ValueError('A tabela public.AMB precisa possuir o campo PercRateio.')
                assignments = sql.SQL(', ').join([
                    sql.SQL('{} = %s').format(sql.Identifier(layout['description'])),
                    sql.SQL('{} = %s').format(sql.Identifier(layout['plan'])),
                    sql.SQL('{} = %s').format(sql.Identifier(layout['value'])),
                    sql.SQL('{} = %s').format(sql.Identifier(layout['health_professional_rate'])),
                ])
                statement = sql.SQL('UPDATE public.{} SET {} WHERE {}').format(
                    sql.Identifier(layout['table']),
                    assignments,
                    sql.SQL(' AND ').join(_scope_conditions(layout)),
                )
                cursor.execute(
                    statement,
                    [description, plan, value, health_professional_rate]
                    + _scope_parameters(record_id, layout),
                )
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Procedimento nao encontrado.'}), 404

        return jsonify({'success': True, 'message': 'Procedimento alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@procedimento_api_bp.route('/api/procedimentos/itens/<record_id>', methods=['DELETE'])
def delete_procedure(record_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _layout(cursor)
                if not layout['id_column']:
                    raise ValueError('A tabela public.AMB precisa possuir um campo codigo.')
                statement = sql.SQL('DELETE FROM public.{} WHERE {}').format(
                    sql.Identifier(layout['table']),
                    sql.SQL(' AND ').join(_scope_conditions(layout)),
                )
                cursor.execute(statement, _scope_parameters(record_id, layout))
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Procedimento nao encontrado.'}), 404

        return jsonify({'success': True, 'message': 'Procedimento excluido com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
