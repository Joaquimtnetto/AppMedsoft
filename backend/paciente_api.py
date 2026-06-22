from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, session

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection

paciente_api_bp = Blueprint('paciente_api', __name__)


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


def _error_response(exc):
    nome = (data.get('nome') or '').strip()
    if not nome:
        raise ValueError('Informe o nome do paciente.')
    return {
        'nomecli': nome,
    }


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    current_app.logger.exception('Falha na operação do paciente', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


paciente_repository = CrudRepository(
    connection_factory=_connection,
    table='pacient',
    id_column='codcli',
    writable_columns=('nomecli',),
    generate_integer_id=True,
)


@paciente_api_bp.route('/api/pacientes/itens', methods=['POST'])
def create_patient():
    try:
        item = _patient_data(request.get_json(silent=True) or {})
        patient_id = paciente_repository.create(item)
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
        item = _patient_data(request.get_json(silent=True) or {})
        updated = paciente_repository.update(patient_id, item)
        if not updated:
            return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Paciente alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@paciente_api_bp.route('/api/pacientes/itens/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    try:
        deleted = paciente_repository.delete(patient_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Paciente excluído com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
