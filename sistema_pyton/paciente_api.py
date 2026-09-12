from contextlib import contextmanager
from datetime import datetime
import base64
import re

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import Binary, sql

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import TENANT_COLUMN, current_company_id

paciente_api_bp = Blueprint('paciente_api', __name__)

FIELD_CANDIDATES = {
    'nome': ('nomecli',),
    'nomed': ('nomed',),
    'telefone': ('telres',),
    'plano': ('nomeplano1',),
    'email': ('email',),
    'ativo': ('ativo',),
    'nascimento': ('datanasc_',),
    'cpf': ('cpf',),
    'rg': ('cident',),
    'sexo': ('sexo',),
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
    'plano2': ('nomeplano2',),
    'cont2': ('cont2',),
    'datult': ('datult_',),
    'matricula': ('matricula',),
    'obs': ('obs',),
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


def _fetch_columns(cursor):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'pacient'
    """)
    return {row[0].lower(): row[0] for row in cursor.fetchall()}


def _detect_fields():
    with _connection() as connection:
        with connection.cursor() as cursor:
            columns = _fetch_columns(cursor)
            if 'ativo' not in columns:
                cursor.execute('''
                    ALTER TABLE public.pacient
                    ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE
                ''')
                columns = _fetch_columns(cursor)
    fields = {}
    for logical_name, candidates in FIELD_CANDIDATES.items():
        for candidate in candidates:
            if candidate.lower() in columns:
                fields[logical_name] = columns[candidate.lower()]
                break
    return fields


def _active_storage_value(active):
    """Retorna o valor compatível com o tipo legado da coluna ativo."""
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND lower(table_name) = 'pacient'
                  AND lower(column_name) = 'ativo'
                LIMIT 1
            ''')
            row = cursor.fetchone()
    return bool(active) if row and row[0] == 'boolean' else ('S' if active else 'N')


DATE_FIELDS = {
    'nascimento': 'Nascimento invalido.',
    'validade_carteira1': 'Validade do plano invalida.',
    'datult': 'Data da ultima consulta invalida.',
}


def _parse_date(value, message):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError(message) from exc


def _patient_data(data, fields):
    nome = (data.get('nome') or '').strip()
    if not nome:
        raise ValueError('Informe o nome do paciente.')

    item = {
        fields['nome']: nome,
    }
    for logical_name, column_name in fields.items():
        if logical_name == 'nome':
            continue
        if logical_name == 'ativo':
            active = str(data.get('ativo', 'S')).strip().upper() not in ('N', 'NAO', 'NÃO', 'FALSE', '0', 'INATIVO')
            item[column_name] = _active_storage_value(active)
            continue
        if logical_name in DATE_FIELDS:
            item[column_name] = _parse_date(data.get(logical_name), DATE_FIELDS[logical_name])
            continue
        value = (data.get(logical_name) or '').strip()
        if logical_name == 'cpf':
            value = re.sub(r'\D', '', value)
        if logical_name == 'foto':
            if value.startswith('data:image/') and ',' in value:
                value = Binary(base64.b64decode(value.split(',', 1)[1]))
            else:
                value = None
        item[column_name] = value or None
    return item


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    current_app.logger.exception('Falha na operação do paciente', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


def _repository(fields):
    return CrudRepository(
        connection_factory=_connection,
        table='pacient',
        id_column='codcli',
        writable_columns=tuple(fields.values()),
        generate_integer_id=True,
        tenant_column=TENANT_COLUMN,
        tenant_value_factory=current_company_id,
    )


def _patient_option_expression(column_name, alias):
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(alias))
    return sql.SQL("COALESCE({}, '') AS {}").format(
        sql.Identifier(column_name),
        sql.Identifier(alias),
    )


@paciente_api_bp.route('/api/pacientes/opcoes', methods=['POST'])
def patient_options():
    """Lista pacientes da empresa ativa para seleções da agenda."""
    try:
        data = request.get_json(silent=True) or {}
        term = str(data.get('termo') or '').strip()
        fields = _detect_fields()
        if 'nome' not in fields:
            raise ValueError('Campo de nome não encontrado na tabela public.PACIENT.')
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier('codcli')),
            sql.SQL('{} AS nome').format(sql.Identifier(fields['nome'])),
            _patient_option_expression(fields.get('telefone'), 'telefone'),
            _patient_option_expression(fields.get('email'), 'email'),
            _patient_option_expression(fields.get('plano'), 'plano'),
        ]
        statement = sql.SQL('''
            SELECT {}
            FROM public.pacient
            WHERE codclin = %s
        ''').format(sql.SQL(', ').join(select_items))
        parameters = [current_company_id()]
        if fields.get('ativo'):
            statement += sql.SQL(
                " AND LOWER(COALESCE(CAST({} AS TEXT), '')) NOT IN ('n', 'nao', 'não', 'false', '0', 'inativo')"
            ).format(sql.Identifier(fields['ativo']))
        if term:
            statement += sql.SQL(' AND ({} ILIKE %s OR CAST(codcli AS TEXT) = %s)').format(
                sql.Identifier(fields['nome'])
            )
            parameters.extend([f'%{term}%', term])
        statement += sql.SQL(' ORDER BY {}').format(sql.Identifier(fields['nome']))
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        return jsonify({
            'success': True,
            'pacientes': [
                {
                    'id': row[0],
                    'nome': row[1] or '',
                    'telefone': row[2] or '',
                    'email': row[3] or '',
                    'plano': row[4] or '',
                }
                for row in rows
            ],
        })
    except Exception as exc:
        return _error_response(exc)


@paciente_api_bp.route('/api/pacientes/itens', methods=['POST'])
def create_patient():
    try:
        fields = _detect_fields()
        item = _patient_data(request.get_json(silent=True) or {}, fields)
        patient_id = _repository(fields).create(item)
        return jsonify({
            'success': True,
            'message': 'Paciente incluído com sucesso.',
            'id': patient_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@paciente_api_bp.route('/api/pacientes/itens/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    try:
        fields = _detect_fields()
        item = _patient_data(request.get_json(silent=True) or {}, fields)
        updated = _repository(fields).update(patient_id, item)
        if not updated:
            return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Paciente alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@paciente_api_bp.route('/api/pacientes/itens/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    try:
        fields = _detect_fields()
        active_column = fields.get('ativo')
        if not active_column:
            raise ValueError('Campo Ativo não encontrado no cadastro de pacientes.')
        updated = _repository(fields).update(patient_id, {active_column: _active_storage_value(False)})
        if not updated:
            return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Paciente marcado como inativo com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
