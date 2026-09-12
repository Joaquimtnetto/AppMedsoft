import calendar
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request, session
from medsoft_core import DBConnectionError, get_db_connection
from psycopg2 import errors, sql

from crud_repository import CrudRepository
from tenant_context import TENANT_COLUMN, current_company_id


faturamento_api_bp = Blueprint('faturamento_api', __name__)

TABLE_NAME = 'pagamento'
ID_COLUMN = 'codigo'
FIELD_COLUMNS = {
    'cliente': 'cod_cli',
    'dataPrevista': 'data_pag_prev',
    'dataRealizada': 'data_pag_realiz',
    'valorPrevisto': 'valor_pago_prev',
    'valorRealizado': 'valor_pago_realiz',
    'pago': 'pago',
    'descricao': 'desc_pagamento',
    'valor': 'valor',
    'tipo': 'tipodesp',
}
MAX_LENGTHS = {
    'descricao': 18,
    'pago': 1,
    'tipo': 10,
}
NUMERIC_FIELDS = {'valorPrevisto', 'valorRealizado', 'valor'}
INTEGER_FIELDS = {'cliente'}
DATE_FIELDS = {'dataPrevista', 'dataRealizada'}


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
        SELECT column_name, data_type, column_default, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = %s
    """, (TABLE_NAME,))
    return {
        row[0].lower(): {
            'name': row[0],
            'data_type': row[1] or '',
            'default': row[2],
            'max_length': row[3],
        }
        for row in cursor.fetchall()
    }


def _layout():
    with _connection() as connection:
        with connection.cursor() as cursor:
            columns = _fetch_columns(cursor)
    if not columns:
        raise ValueError('Tabela public.Pagamento nao encontrada no banco.')
    if ID_COLUMN not in columns:
        raise ValueError('A tabela public.Pagamento precisa possuir o campo codigo.')
    if TENANT_COLUMN not in columns:
        raise ValueError('A tabela public.Pagamento precisa possuir o campo codclin.')

    fields = {}
    for logical_name, column_name in FIELD_COLUMNS.items():
        column = columns.get(column_name.lower())
        if column:
            fields[logical_name] = column['name']

    id_info = columns[ID_COLUMN]
    generate_integer_id = (
        id_info['default'] is None and
        any(kind in id_info['data_type'].lower() for kind in ('integer', 'bigint', 'smallint'))
    )
    return {
        'table': TABLE_NAME,
        'id_column': id_info['name'],
        'tenant_column': columns[TENANT_COLUMN]['name'],
        'fields': fields,
        'max_lengths': {
            logical_name: columns[column_name.lower()].get('max_length')
            for logical_name, column_name in FIELD_COLUMNS.items()
            if column_name.lower() in columns
        },
        'generate_integer_id': generate_integer_id,
    }


def _repository(layout):
    return CrudRepository(
        connection_factory=_connection,
        table=layout['table'],
        id_column=layout['id_column'],
        writable_columns=tuple(layout['fields'].values()),
        generate_integer_id=layout['generate_integer_id'],
        tenant_column=layout['tenant_column'],
        tenant_value_factory=current_company_id,
    )


def _parse_decimal(value, label):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    value = str(value or '').strip()
    if not value:
        return None
    try:
        if ',' in value:
            value = value.replace('.', '').replace(',', '.')
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'{label} deve ser numerico.') from exc


def _parse_date(value, label):
    value = str(value or '').strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{label} deve ser uma data valida.') from exc


def _payment_data(data, layout):
    labels = {
        'cliente': 'Cliente',
        'dataPrevista': 'Data prevista',
        'dataRealizada': 'Data realizada',
        'valorPrevisto': 'Valor previsto',
        'valorRealizado': 'Valor realizado',
        'valor': 'Valor',
        'pago': 'Pago',
        'descricao': 'Descricao',
        'tipo': 'Tipo',
    }
    values = {}
    for logical_name, column_name in layout['fields'].items():
        if logical_name not in data:
            continue
        value = data.get(logical_name)
        if logical_name in NUMERIC_FIELDS:
            value = _parse_decimal(value, labels[logical_name])
        elif logical_name in INTEGER_FIELDS:
            value = str(value or '').strip()
            value = int(value) if value else None
        elif logical_name in DATE_FIELDS:
            value = _parse_date(value, labels[logical_name])
        else:
            value = str(value or '').strip()
            if logical_name == 'pago':
                value = value.upper()
                if value not in ('', 'S', 'N'):
                    raise ValueError('Pago deve ser S ou N.')
            if logical_name == 'tipo' and value not in ('', 'Receita', 'Despesa'):
                raise ValueError('Tipo deve ser Receita ou Despesa.')
            limit = _column_limit(layout, logical_name)
            if value and limit and len(value) > limit:
                raise ValueError(f'{labels[logical_name]} excede {limit} caracteres.')
            value = value or None
        values[column_name] = value
    return values


def _format_decimal(value):
    if value is None:
        return ''
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f'{value:.2f}'.replace('.', ',')


def _format_date(value):
    if value is None:
        return ''
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _parse_month(value):
    try:
        month = int(str(value or '').strip())
    except ValueError as exc:
        raise ValueError('Selecione um mes para importar da agenda.') from exc
    if month < 1 or month > 12:
        raise ValueError('Mes deve ser um numero de 1 a 12.')
    return month


def _parse_br_date(value, label):
    value = str(value or '').strip()
    if not value:
        raise ValueError(f'Informe {label}.')
    try:
        day, month, year = [int(part) for part in value.split('/')]
        return date(year, month, day)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} deve estar no formato dd/mm/aaaa.') from exc


def _column_limit(layout, logical_name):
    configured = layout.get('max_lengths', {}).get(logical_name)
    fallback = MAX_LENGTHS.get(logical_name)
    return configured or fallback


def _fit_column(layout, logical_name, value):
    value = str(value or '').strip()
    limit = _column_limit(layout, logical_name)
    if limit and len(value) > limit:
        return value[:limit]
    return value


def _add_one_month(value):
    if value is None:
        return None
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _amb_layout(cursor):
    cursor.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'amb'
    """)
    table_name = None
    columns = {}
    for table_name, column_name in cursor.fetchall():
        columns[column_name.lower()] = column_name
    description = columns.get('descamb')
    value = columns.get('valor')
    professional_rate = columns.get('percrateio')
    plan = None
    for candidate in ('nomeplano', 'plano', 'nomeplano1', 'convenio'):
        if candidate in columns:
            plan = columns[candidate]
            break
    tenant_column = columns.get(TENANT_COLUMN)
    if not table_name or not description or not value or not plan or not professional_rate:
        raise ValueError(
            'A tabela public.AMB precisa possuir procedimento, plano, valor e PercRateio.'
        )
    return {
        'table': table_name,
        'description': description,
        'plan': plan,
        'value': value,
        'professional_rate': professional_rate,
        'tenant_column': tenant_column,
    }


def _agenda_columns(cursor):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'agenda'
    """)
    return {row[0].lower(): row[0] for row in cursor.fetchall()}


def _plan_layout(cursor):
    cursor.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'plano'
    """)
    table_name = None
    columns = {}
    for table_name, column_name in cursor.fetchall():
        columns[column_name.lower()] = column_name
    name = columns.get('nomeplano')
    due_days = columns.get('prazo')
    tenant_column = columns.get(TENANT_COLUMN)
    if not table_name or not name or not due_days:
        raise ValueError('A tabela public.plano precisa possuir os campos nomeplano e prazo.')
    return {
        'table': table_name,
        'name': name,
        'due_days': due_days,
        'tenant_column': tenant_column,
    }


def _payment_from_row(row):
    return {
        'id': row[0],
        'cliente': row[1] or '',
        'dataPrevista': _format_date(row[2]),
        'dataRealizada': _format_date(row[3]),
        'valorPrevisto': _format_decimal(row[4]),
        'valorRealizado': _format_decimal(row[5]),
        'pago': (row[6] or '').strip(),
        'descricao': (row[7] or '').strip(),
        'valor': _format_decimal(row[8]),
        'tipo': (row[9] or '').strip(),
    }


def _totalization_item(row):
    payment_type, total_expected, total_realized = row
    return {
        'tipo': payment_type or '',
        'valorPrevisto': _format_decimal(total_expected or Decimal('0')),
        'valorRealizado': _format_decimal(total_realized or Decimal('0')),
    }


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.StringDataRightTruncation):
        return jsonify({'success': False, 'message': 'Um dos campos ultrapassa o tamanho permitido.'}), 400
    if isinstance(exc, (errors.InvalidTextRepresentation, errors.NumericValueOutOfRange)):
        return jsonify({'success': False, 'message': 'Verifique os campos numericos informados.'}), 400
    current_app.logger.exception('Falha na operacao do financeiro', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@faturamento_api_bp.route('/api/faturamento', methods=['POST'])
def list_payments():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        month = str(data.get('mes') or '').strip()
        payment_type = (data.get('tipo') or '').strip()
        layout = _layout()

        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
            sql.SQL('{} AS cliente').format(sql.Identifier(layout['fields'].get('cliente', 'cod_cli'))),
            sql.SQL('{} AS data_prevista').format(sql.Identifier(layout['fields'].get('dataPrevista', 'data_pag_prev'))),
            sql.SQL('{} AS data_realizada').format(sql.Identifier(layout['fields'].get('dataRealizada', 'data_pag_realiz'))),
            sql.SQL('{} AS valor_previsto').format(sql.Identifier(layout['fields'].get('valorPrevisto', 'valor_pago_prev'))),
            sql.SQL('{} AS valor_realizado').format(sql.Identifier(layout['fields'].get('valorRealizado', 'valor_pago_realiz'))),
            sql.SQL('{} AS pago').format(sql.Identifier(layout['fields'].get('pago', 'pago'))),
            sql.SQL('{} AS descricao').format(sql.Identifier(layout['fields'].get('descricao', 'desc_pagamento'))),
            sql.SQL('{} AS valor').format(sql.Identifier(layout['fields'].get('valor', 'valor'))),
            sql.SQL('{} AS tipo').format(sql.Identifier(layout['fields'].get('tipo', 'tipodesp'))),
        ]
        statement = sql.SQL('SELECT {} FROM public.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier(layout['table']),
        )
        conditions = [sql.SQL('{} = %s').format(sql.Identifier(layout['tenant_column']))]
        parameters = [current_company_id()]
        if month:
            try:
                month_number = int(month)
            except ValueError as exc:
                raise ValueError('Mes deve ser um numero de 1 a 12.') from exc
            if month_number < 1 or month_number > 12:
                raise ValueError('Mes deve ser um numero de 1 a 12.')
            conditions.append(sql.SQL('EXTRACT(MONTH FROM {}) = %s').format(
                sql.Identifier(layout['fields']['dataRealizada'])
            ))
            parameters.append(month_number)
        if payment_type:
            if payment_type not in ('Receita', 'Despesa'):
                raise ValueError('Tipo deve ser Receita ou Despesa.')
            conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['fields']['tipo'])))
            parameters.append(payment_type)
        if term:
            conditions.append(sql.SQL('(') + sql.SQL(' OR ').join([
                sql.SQL('CAST({} AS TEXT) ILIKE %s').format(sql.Identifier(layout['id_column'])),
                sql.SQL('CAST({} AS TEXT) ILIKE %s').format(sql.Identifier(layout['fields']['cliente'])),
                sql.SQL('{} ILIKE %s').format(sql.Identifier(layout['fields']['descricao'])),
                sql.SQL('{} ILIKE %s').format(sql.Identifier(layout['fields']['tipo'])),
            ]) + sql.SQL(')'))
            parameters.extend([f'%{term}%', f'%{term}%', f'%{term}%', f'%{term}%'])
        statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
        statement += sql.SQL(' ORDER BY {} DESC LIMIT 200').format(sql.Identifier(layout['id_column']))

        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        return jsonify({'success': True, 'pagamentos': [_payment_from_row(row) for row in rows]})
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/faturamento/totalizacao', methods=['POST'])
def totalize_payments():
    try:
        data = request.get_json(silent=True) or {}
        start_date = _parse_br_date(data.get('dataInicio'), 'Data inicio')
        end_date = _parse_br_date(data.get('dataFim'), 'Data fim')
        if end_date < start_date:
            raise ValueError('Data fim deve ser maior ou igual a data inicio.')
        payment_type = (data.get('tipo') or '').strip()
        if payment_type and payment_type not in ('Receita', 'Despesa'):
            raise ValueError('Tipo deve ser Receita, Despesa ou Tudo.')

        layout = _layout()
        statement = sql.SQL("""
            SELECT
                {} AS tipo,
                COALESCE(SUM(COALESCE({}, 0)), 0) AS total_previsto,
                COALESCE(SUM(CASE WHEN UPPER(TRIM(COALESCE({}, ''))) = 'S'
                    THEN COALESCE({}, 0) ELSE 0 END), 0) AS total_realizado
            FROM public.{}
            WHERE {} = %s
              AND {} BETWEEN %s AND %s
        """).format(
            sql.Identifier(layout['fields']['tipo']),
            sql.Identifier(layout['fields']['valorPrevisto']),
            sql.Identifier(layout['fields']['pago']),
            sql.Identifier(layout['fields']['valorRealizado']),
            sql.Identifier(layout['table']),
            sql.Identifier(layout['tenant_column']),
            sql.Identifier(layout['fields']['dataRealizada']),
        )
        parameters = [current_company_id(), start_date, end_date]
        if payment_type:
            statement += sql.SQL(' AND {} = %s').format(sql.Identifier(layout['fields']['tipo']))
            parameters.append(payment_type)
        statement += sql.SQL(' GROUP BY {}').format(sql.Identifier(layout['fields']['tipo']))

        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        totals = {
            'Receita': {'tipo': 'Receita', 'valorPrevisto': '0,00', 'valorRealizado': '0,00'},
            'Despesa': {'tipo': 'Despesa', 'valorPrevisto': '0,00', 'valorRealizado': '0,00'},
        }
        for item in (_totalization_item(row) for row in rows):
            if item['tipo'] in totals:
                totals[item['tipo']] = item
        return jsonify({
            'success': True,
            'totalizacao': totals,
        })
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/relatorios/financeiro', methods=['POST'])
def financial_report():
    try:
        data = request.get_json(silent=True) or {}
        start_date = _parse_date(data.get('data_inicio'), 'Data inicial')
        end_date = _parse_date(data.get('data_fim'), 'Data final')
        if not start_date or not end_date:
            raise ValueError('Informe a Data Inicial e a Data Final.')
        if end_date < start_date:
            raise ValueError('A Data Final deve ser igual ou posterior a Data Inicial.')
        payment_type = str(data.get('tipo') or '').strip()
        if payment_type and payment_type not in ('Receita', 'Despesa'):
            raise ValueError('Tipo deve ser Receita, Despesa ou Todas.')

        layout = _layout()
        report_fields = [
            ('descricao', 'descricao'),
            ('tipo', 'tipo'),
            ('data_prevista', 'dataPrevista'),
            ('data_realizada', 'dataRealizada'),
            ('valor_previsto', 'valorPrevisto'),
            ('valor_realizado', 'valorRealizado'),
            ('pago', 'pago'),
            ('cliente', 'cliente'),
            ('codigo', None),
        ]
        select_items = []
        visible_fields = []
        for output_name, logical_name in report_fields:
            column_name = layout['id_column'] if logical_name is None else layout['fields'].get(logical_name)
            if not column_name:
                continue
            visible_fields.append(output_name)
            select_items.append(sql.SQL("COALESCE(CAST({} AS TEXT), '') AS {}").format(
                sql.Identifier(column_name), sql.Identifier(output_name)
            ))

        realized_column = layout['fields'].get('dataRealizada')
        if not realized_column:
            raise ValueError('Tabela financeira sem o campo Data Realizada.')
        conditions = [
            sql.SQL('{} = %s').format(sql.Identifier(layout['tenant_column'])),
            sql.SQL('{} BETWEEN %s AND %s').format(sql.Identifier(realized_column)),
        ]
        parameters = [current_company_id(), start_date, end_date]
        if payment_type:
            conditions.append(sql.SQL('{} = %s').format(sql.Identifier(layout['fields']['tipo'])))
            parameters.append(payment_type)
        statement = sql.SQL('''
            SELECT {} FROM public.{}
            WHERE {}
            ORDER BY {}, {}
        ''').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier(layout['table']),
            sql.SQL(' AND ').join(conditions),
            sql.Identifier(realized_column),
            sql.Identifier(layout['id_column']),
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        records = [dict(zip(visible_fields, row)) for row in rows]
        return jsonify({
            'success': True,
            'titulo': 'Financeiro',
            'registros': records,
            'colunas': visible_fields,
            'total': len(records),
        })
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/faturamento/itens', methods=['POST'])
def create_payment():
    try:
        layout = _layout()
        payment_id = _repository(layout).create(_payment_data(request.get_json(silent=True) or {}, layout))
        return jsonify({
            'success': True,
            'message': 'Financeiro incluido com sucesso.',
            'id': payment_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/faturamento/importar-agenda', methods=['POST'])
def import_from_agenda():
    try:
        data = request.get_json(silent=True) or {}
        month = _parse_month(data.get('mes'))
        layout = _layout()

        with _connection() as connection:
            with connection.cursor() as cursor:
                amb = _amb_layout(cursor)
                plan_layout = _plan_layout(cursor)
                agenda_columns = _agenda_columns(cursor)
                patient_code_column = None
                for candidate in ('codpaci', 'codpac', 'codcli', 'cod_cli'):
                    if candidate in agenda_columns:
                        patient_code_column = agenda_columns[candidate]
                        break

                select_items = [
                    sql.SQL('a.{}').format(sql.Identifier('datacons')),
                    sql.SQL('a.{}').format(sql.Identifier('nomepaci')),
                    sql.SQL('a.{}').format(sql.Identifier('nomeplano')),
                    sql.SQL('a.{}').format(sql.Identifier('proced')),
                    sql.SQL('a.{}').format(sql.Identifier('nomed')),
                ]
                if patient_code_column:
                    select_items.append(sql.SQL('a.{}').format(sql.Identifier(patient_code_column)))
                else:
                    select_items.append(sql.SQL('NULL'))

                agenda_statement = sql.SQL("""
                    SELECT {}
                    FROM public.agenda a
                    WHERE a.codclin = %s
                      AND EXTRACT(MONTH FROM a.datacons) = %s
                      AND UPPER(TRIM(COALESCE(a.atend, ''))) IN ('AT', 'AT-ATENDIDO', 'ATENDIDO')
                    ORDER BY a.datacons, a.horacons, a.codagend
                """).format(sql.SQL(', ').join(select_items))
                cursor.execute(agenda_statement, (current_company_id(), month))
                agenda_rows = cursor.fetchall()

                procedure_statement = sql.SQL("""
                    SELECT {}, {}
                    FROM public.{}
                    WHERE UPPER(TRIM({})) = UPPER(TRIM(%s))
                      AND UPPER(TRIM({})) = UPPER(TRIM(%s))
                """).format(
                    sql.Identifier(amb['value']),
                    sql.Identifier(amb['professional_rate']),
                    sql.Identifier(amb['table']),
                    sql.Identifier(amb['description']),
                    sql.Identifier(amb['plan']),
                )
                if amb['tenant_column']:
                    procedure_statement += sql.SQL(' AND {} = %s').format(sql.Identifier(amb['tenant_column']))

                plan_statement = sql.SQL("""
                    SELECT {}
                    FROM public.{}
                    WHERE UPPER(TRIM({})) = UPPER(TRIM(%s))
                """).format(
                    sql.Identifier(plan_layout['due_days']),
                    sql.Identifier(plan_layout['table']),
                    sql.Identifier(plan_layout['name']),
                )
                if plan_layout['tenant_column']:
                    plan_statement += sql.SQL(' AND {} = %s').format(sql.Identifier(plan_layout['tenant_column']))

                imports = []
                skipped = []
                for (
                    appointment_date,
                    patient_name,
                    plan_name,
                    procedure_name,
                    professional_name,
                    patient_code,
                ) in agenda_rows:
                    patient_name = (patient_name or '').strip()
                    plan_name = (plan_name or '').strip()
                    procedure_name = (procedure_name or '').strip()
                    professional_name = (professional_name or '').strip()
                    if not procedure_name or not plan_name:
                        skipped.append(patient_name or 'Paciente sem nome')
                        continue
                    parameters = [procedure_name, plan_name]
                    if amb['tenant_column']:
                        parameters.append(current_company_id())
                    cursor.execute(procedure_statement, parameters)
                    procedure = cursor.fetchone()
                    if not procedure:
                        skipped.append(f'{procedure_name} / {plan_name} / {patient_name}')
                        continue
                    value = _parse_decimal(procedure[0], 'Valor do procedimento') or Decimal('0')
                    professional_rate = (
                        _parse_decimal(procedure[1], 'Rateio do profissional') or Decimal('0')
                    )
                    professional_payment = (
                        value * professional_rate * Decimal('0.01')
                    ).quantize(Decimal('0.01'))
                    plan_parameters = [plan_name]
                    if plan_layout['tenant_column']:
                        plan_parameters.append(current_company_id())
                    cursor.execute(plan_statement, plan_parameters)
                    plan_row = cursor.fetchone()
                    try:
                        due_days = int(plan_row[0] or 0) if plan_row else 0
                    except (TypeError, ValueError):
                        due_days = 0
                    realized_date = appointment_date
                    expected_date = realized_date + timedelta(days=due_days) if realized_date else None
                    description = _fit_column(
                        layout,
                        'descricao',
                        f'{procedure_name} {plan_name} {patient_name}',
                    )
                    imports.append({
                        'cliente': patient_code,
                        'descricao': description,
                        'tipo': 'Receita',
                        'dataPrevista': expected_date,
                        'dataRealizada': realized_date,
                        'valorPrevisto': value,
                        'valorRealizado': None,
                        'valor': value,
                        'pago': 'S',
                    })
                    expense_description = _fit_column(
                        layout,
                        'descricao',
                        f'Pag. {professional_name} {procedure_name} {patient_name}',
                    )
                    imports.append({
                        'cliente': None,
                        'descricao': expense_description,
                        'tipo': 'Despesa',
                        'dataPrevista': realized_date,
                        'dataRealizada': realized_date,
                        'valorPrevisto': professional_payment,
                        'valorRealizado': None,
                        'valor': professional_payment,
                        'pago': 'S',
                    })

        repository = _repository(layout)
        created = []
        for payment in imports:
            created.append(repository.create(_payment_data(payment, layout)))

        message = f'{len(created)} lancamento(s) financeiro(s) incluido(s) da agenda.'
        if skipped:
            message += f' {len(skipped)} agenda(s) sem valor de procedimento/plano.'
        return jsonify({
            'success': True,
            'message': message,
            'incluidos': len(created),
            'ignorados': len(skipped),
            'detalhesIgnorados': skipped[:20],
        })
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/faturamento/itens/<record_id>', methods=['PUT'])
def update_payment(record_id):
    try:
        layout = _layout()
        updated = _repository(layout).update(record_id, _payment_data(request.get_json(silent=True) or {}, layout))
        if not updated:
            return jsonify({'success': False, 'message': 'Financeiro nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Financeiro alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/faturamento/itens/<record_id>/duplicar-proximo-mes', methods=['POST'])
def duplicate_next_month(record_id):
    try:
        layout = _layout()
        logical_fields = list(layout['fields'].keys())
        select_items = [sql.Identifier(layout['fields'][name]) for name in logical_fields]
        statement = sql.SQL('SELECT {} FROM public.{} WHERE {} = %s AND {} = %s').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier(layout['table']),
            sql.Identifier(layout['id_column']),
            sql.Identifier(layout['tenant_column']),
        )
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, (record_id, current_company_id()))
                row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Financeiro nao encontrado.'}), 404

        values = {logical_name: row[index] for index, logical_name in enumerate(logical_fields)}
        if 'dataPrevista' in values:
            values['dataPrevista'] = _add_one_month(values['dataPrevista'])
        if 'dataRealizada' in values:
            values['dataRealizada'] = _add_one_month(values['dataRealizada'])

        new_id = _repository(layout).create(_payment_data(values, layout))
        return jsonify({
            'success': True,
            'message': 'Financeiro duplicado para o proximo mes.',
            'id': new_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@faturamento_api_bp.route('/api/faturamento/itens/<record_id>', methods=['DELETE'])
def delete_payment(record_id):
    try:
        deleted = _repository(_layout()).delete(record_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Financeiro nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Financeiro excluido com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
