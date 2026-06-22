import datetime
import re
from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, session

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection

agenda_api_bp = Blueprint('agenda_api', __name__)


def _database_name():
    return request.headers.get('X-DB-PATH') or session.get('db_path') or None


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


def _parse_date(value):
    try:
        return datetime.datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('Data inválida.') from exc


def _parse_time(value):
    try:
        parsed = datetime.datetime.strptime(value or '', '%H:%M')
        return parsed.strftime('%H:%M')
    except ValueError as exc:
        raise ValueError('Horário inválido.') from exc


def _format_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if not digits:
        return ''
    if len(digits) != 10:
        raise ValueError('Telefone inválido. Use o formato (99)9999-9999.')
    return f'({digits[:2]}){digits[2:6]}-{digits[6:]}'


def _appointment_data(data):
    patient = (data.get('paciente') or '').strip()
    if not patient:
        raise ValueError('Informe o nome do paciente.')
    return {
        'datacons': _parse_date(data.get('data')),
        'horacons': _parse_time(data.get('hora')),
        'nomepaci': patient,
        'telefone': _format_phone(data.get('telefone')),
        'nomeplano': (data.get('plano') or '').strip(),
        'proced': (data.get('procedimento') or '').strip(),
    }


def _format_time(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    return str(value)[:5]


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    current_app.logger.exception('Falha na operação da agenda', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


agenda_repository = CrudRepository(
    connection_factory=_connection,
    table='agenda',
    id_column='codagend',
    writable_columns=('datacons', 'horacons', 'nomepaci', 'telefone', 'nomeplano', 'proced'),
    generate_integer_id=True,
)


@agenda_api_bp.route('/api/agenda', methods=['POST'])
def api_agenda():
    data = request.get_json(silent=True) or {}
    data_str = data.get('data') if data else None
    if not data_str:
        return jsonify({'success': False, 'message': 'Data não informada.'}), 400
    try:
        data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
        with _connection() as con:
            with con.cursor() as cur:
                cur.execute('''
                    SELECT a.codagend, a.datacons, a.horacons, a.nomepaci,
                           a.telefone, a.nomeplano, a.proced
                    FROM public.agenda a
                    WHERE a.datacons = %s
                    ORDER BY a.horacons, a.codagend
                ''', (data_obj,))
                rows = cur.fetchall()
        resultados = [{
            'CODAGEND': row[0],
            'DATACONS': row[1].isoformat() if row[1] else '',
            'HORACONS': _format_time(row[2]),
            'NOMEPACI': row[3] or '',
            'TELEFONE': row[4] or '',
            'NOMEPLANO': row[5] or '',
            'PROCED': row[6] or '',
        } for row in rows]
        return jsonify({'success': True, 'resultados': resultados})
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens', methods=['POST'])
def create_appointment():
    try:
        item = _appointment_data(request.get_json(silent=True) or {})
        appointment_id = agenda_repository.create(item)
        return jsonify({
            'success': True,
            'message': 'Compromisso incluído com sucesso.',
            'id': appointment_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>', methods=['PUT'])
def update_appointment(appointment_id):
    try:
        item = _appointment_data(request.get_json(silent=True) or {})
        updated = agenda_repository.update(appointment_id, item)
        if not updated:
            return jsonify({'success': False, 'message': 'Compromisso não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Compromisso alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@agenda_api_bp.route('/api/agenda/itens/<int:appointment_id>', methods=['DELETE'])
def delete_appointment(appointment_id):
    try:
        deleted = agenda_repository.delete(appointment_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Compromisso não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Compromisso excluído com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
