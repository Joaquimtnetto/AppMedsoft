from contextlib import contextmanager
from datetime import date
from io import BytesIO
import base64

from flask import Blueprint, current_app, jsonify, request, send_file, session
from psycopg2 import Binary, errors, sql

from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import current_company_id


exame_api_bp = Blueprint('exame_api', __name__)
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = (
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
)


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


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({
            'success': False,
            'message': 'Já existe um exame com este nome na estrutura atual do banco.',
        }), 409
    current_app.logger.exception('Falha na operação do exame', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


def _patient_exists(cursor, patient_id, company_id):
    cursor.execute(
        'SELECT 1 FROM public.pacient WHERE codcli = %s AND codclin = %s',
        (patient_id, company_id),
    )
    return cursor.fetchone() is not None


def _exam_layout(cursor):
    cursor.execute('''
        SELECT lower(column_name)
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'exame'
    ''')
    columns = {row[0] for row in cursor.fetchall()}
    required = {'nome', 'codcli', 'codpac', 'data', 'imagem'}
    if not required.issubset(columns):
        raise ValueError('A tabela public.EXAME não possui todos os campos obrigatórios.')
    return {
        'id_column': 'idexame' if 'idexame' in columns else 'nome',
        'has_codclin': 'codclin' in columns,
        'has_observation': 'observacao' in columns,
    }


def _exam_scope(layout, alias=''):
    prefix = f'{alias}.' if alias else ''
    if layout['has_codclin']:
        return f'{prefix}codpac = %s AND {prefix}codclin = %s'
    return (
        f'{prefix}codpac = %s AND EXISTS ('
        f'SELECT 1 FROM public.pacient scope_patient '
        f'WHERE scope_patient.codcli = {prefix}codpac AND scope_patient.codclin = %s)'
    )


def _exam_values(data):
    name = str(data.get('nome') or '').strip()
    if not name:
        raise ValueError('Informe o nome do exame.')
    if len(name) > 20:
        raise ValueError('O nome do exame deve ter no máximo 20 caracteres.')
    try:
        exam_date = date.fromisoformat(str(data.get('data') or ''))
    except ValueError as exc:
        raise ValueError('Informe uma data válida para o exame.') from exc
    observation = str(data.get('observacao') or '').strip()
    if len(observation) > 300:
        raise ValueError('A observação deve ter no máximo 300 caracteres.')
    image = data.get('imagem')
    remove_image = data.get('remover_imagem') is True
    decoded_image = None
    if image:
        text = str(image)
        image_type = text[5:text.find(';')].lower() if ';' in text else ''
        if image_type not in ALLOWED_DOCUMENT_TYPES or ',' not in text:
            raise ValueError('Selecione um documento JPG, PNG, GIF, WebP, PDF, DOC ou DOCX.')
        try:
            decoded_image = base64.b64decode(text.split(',', 1)[1], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('Não foi possível ler o documento selecionado.') from exc
        if len(decoded_image) > MAX_DOCUMENT_BYTES:
            raise ValueError('O documento do exame deve ter no máximo 10 MB.')
    return name, exam_date, observation, decoded_image, remove_image


def _document_mimetype(value):
    if value.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if value.startswith(b'GIF87a') or value.startswith(b'GIF89a'):
        return 'image/gif'
    if value.startswith(b'RIFF') and value[8:12] == b'WEBP':
        return 'image/webp'
    if value.startswith(b'%PDF-'):
        return 'application/pdf'
    if value.startswith(b'PK\x03\x04'):
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if value.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return 'application/msword'
    return 'image/jpeg'


@exame_api_bp.route('/api/pacientes/<int:patient_id>/exames', methods=['GET'])
def list_exams(patient_id):
    try:
        company_id = current_company_id()
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _patient_exists(cursor, patient_id, company_id):
                    return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404
                layout = _exam_layout(cursor)
                observation = "COALESCE(e.observacao, '')" if layout['has_observation'] else "''"
                cursor.execute(sql.SQL('''
                    SELECT e.{} AS id, e.nome, e.codcli, e.codpac, e.data,
                           e.imagem IS NOT NULL, {}
                    FROM public.exame e
                    WHERE {}
                    ORDER BY e.data DESC NULLS LAST, e.nome
                ''').format(
                    sql.Identifier(layout['id_column']),
                    sql.SQL(observation),
                    sql.SQL(_exam_scope(layout, 'e')),
                ), (patient_id, company_id))
                rows = cursor.fetchall()
        return jsonify({
            'success': True,
            'exames': [
                {
                    'id': row[0], 'nome': row[1] or '', 'codcli': row[2],
                    'codpac': row[3], 'data': row[4].isoformat() if row[4] else '',
                    'tem_imagem': bool(row[5]), 'observacao': row[6] or '',
                }
                for row in rows
            ],
        })
    except Exception as exc:
        return _error_response(exc)


@exame_api_bp.route('/api/pacientes/<int:patient_id>/exames', methods=['POST'])
def create_exam(patient_id):
    try:
        name, exam_date, observation, image, _remove = _exam_values(request.get_json(silent=True) or {})
        company_id = current_company_id()
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _patient_exists(cursor, patient_id, company_id):
                    return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404
                layout = _exam_layout(cursor)
                columns = ['nome', 'codcli', 'codpac', 'data', 'imagem']
                values = [name, patient_id, patient_id, exam_date, Binary(image) if image is not None else None]
                if layout['has_observation']:
                    columns.append('observacao')
                    values.append(observation or None)
                if layout['has_codclin']:
                    columns.append('codclin')
                    values.append(company_id)
                cursor.execute(
                    sql.SQL('INSERT INTO public.exame ({}) VALUES ({}) RETURNING {}').format(
                        sql.SQL(', ').join(map(sql.Identifier, columns)),
                        sql.SQL(', ').join(sql.Placeholder() for _ in columns),
                        sql.Identifier(layout['id_column']),
                    ),
                    values,
                )
                exam_id = cursor.fetchone()[0]
        return jsonify({
            'success': True, 'message': 'Exame incluído com sucesso.', 'id': exam_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@exame_api_bp.route('/api/pacientes/<int:patient_id>/exames/<path:exam_id>', methods=['PUT'])
def update_exam(patient_id, exam_id):
    try:
        name, exam_date, observation, image, remove_image = _exam_values(request.get_json(silent=True) or {})
        company_id = current_company_id()
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _exam_layout(cursor)
                assignments = ['nome = %s', 'data = %s']
                parameters = [name, exam_date]
                if layout['has_observation']:
                    assignments.append('observacao = %s')
                    parameters.append(observation or None)
                if image is not None or remove_image:
                    assignments.append('imagem = %s')
                    parameters.append(Binary(image) if image is not None else None)
                identifier = int(exam_id) if layout['id_column'] == 'idexame' else exam_id
                parameters.extend([identifier, patient_id, company_id])
                cursor.execute(
                    sql.SQL('UPDATE public.exame SET {} WHERE {} = %s AND {}').format(
                        sql.SQL(', ').join(map(sql.SQL, assignments)),
                        sql.Identifier(layout['id_column']),
                        sql.SQL(_exam_scope(layout)),
                    ),
                    parameters,
                )
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Exame não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Exame alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@exame_api_bp.route('/api/pacientes/<int:patient_id>/exames/<path:exam_id>', methods=['DELETE'])
def delete_exam(patient_id, exam_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _exam_layout(cursor)
                identifier = int(exam_id) if layout['id_column'] == 'idexame' else exam_id
                cursor.execute(
                    sql.SQL('DELETE FROM public.exame WHERE {} = %s AND {}').format(
                        sql.Identifier(layout['id_column']), sql.SQL(_exam_scope(layout))
                    ),
                    (identifier, patient_id, current_company_id()),
                )
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Exame não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Exame excluído com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@exame_api_bp.route('/api/pacientes/<int:patient_id>/exames/<path:exam_id>/imagem', methods=['GET'])
def exam_image(patient_id, exam_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _exam_layout(cursor)
                identifier = int(exam_id) if layout['id_column'] == 'idexame' else exam_id
                cursor.execute(
                    sql.SQL('SELECT imagem FROM public.exame WHERE {} = %s AND {} LIMIT 1').format(
                        sql.Identifier(layout['id_column']), sql.SQL(_exam_scope(layout))
                    ),
                    (identifier, patient_id, current_company_id()),
                )
                row = cursor.fetchone()
        if not row or row[0] is None:
            return jsonify({'success': False, 'message': 'Documento não encontrado.'}), 404
        value = row[0].tobytes() if isinstance(row[0], memoryview) else bytes(row[0])
        return send_file(BytesIO(value), mimetype=_document_mimetype(value), max_age=0)
    except Exception as exc:
        return _error_response(exc)
