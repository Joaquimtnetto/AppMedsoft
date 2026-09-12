import unicodedata

from flask import Blueprint, request


paciente_bp = Blueprint('paciente', __name__)


def get_db_path_from_request():
    db_path = request.headers.get('X-DB-PATH') or (
        request.json.get('db_path') if request.is_json and request.json else None
    )
    if not db_path:
        raise Exception('Banco da empresa nao informado (db_path).')
    print(f'[DEBUG] 127.0.0.1 - - O VALOR DO DATABASE E: {db_path}', flush=True)
    return db_path


def remover_acentos(txt):
    if not txt:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    ).upper()


# A rota /api/consulta-paciente fica em consulta_paciente.py.
# Este modulo permanece para compatibilidade com imports antigos.
