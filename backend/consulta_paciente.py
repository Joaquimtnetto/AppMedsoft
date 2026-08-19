from flask import Blueprint, request, jsonify
from medsoft_core import get_db_connection, DBConnectionError
import logging
from datetime import date, datetime
import unicodedata


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
consulta_paciente_bp = Blueprint('consulta_paciente', __name__)
def remover_acentos(txt):
    if not txt:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').upper()

@consulta_paciente_bp.route('/api/consulta-paciente', methods=['POST'])
def consulta_paciente():
    data = request.json
    termo = data.get('termo', '').strip() if data else ''
    nome_medico = data.get('nome_medico', '').strip() if data else ''
    usa_like_medico = False
    if not nome_medico:
        nome_medico = '%'
        usa_like_medico = True
    if not termo or not nome_medico:
        return jsonify({'success': False, 'message': 'Informe nome/código e nome do médico.', 'pacientes': []}), 400
    try:
        # Usa conexão Postgres configurada (MEDSOFT_DB_TYPE=postgres)
        db_path = request.headers.get('X-DB-PATH') or None
        con = get_db_connection(db_path)
        cur = con.cursor()
        termo_limpo = termo.strip()
        if termo_limpo and any(c != '%' for c in termo_limpo):
            termo_busca = f"%{termo_limpo}%"
            query = '''
                SELECT nomecli, codcli,
                       COALESCE(EXTRACT(YEAR FROM age(CURRENT_DATE, datanasc_)), 0)::int AS idade,
                       nomeplano1, nomed
                FROM public.pacient
                WHERE nomecli ILIKE %s
                  AND nomed ILIKE %s
                ORDER BY nomecli
            '''
            logging.info(f'Executando query public.pacient: {query} params={(termo_busca, nome_medico)} db_path={db_path}')
            cur.execute(query, (termo_busca, nome_medico))
        else:
            con.close()
            return jsonify({'success': False, 'message': 'Termo inválido.', 'pacientes': []}), 400
        pacientes = []
        rows = cur.fetchall()
        for row in rows:
            nomecli, codcli, idade, nomeplano1, nomed = row
            pacientes.append({
                'nomecli': nomecli,
                'codcli': codcli,
                'idade': idade,
                'nomeplano1': nomeplano1,
                'nomed': nomed
            })
        con.close()
        if not rows:
            return jsonify({'success': True, 'pacientes': [], 'message': 'Nenhum paciente encontrado.'})
        return jsonify({'success': True, 'pacientes': pacientes})
    except DBConnectionError as e:
        logging.error(f'Erro de conexão no consulta_paciente: {e}')
        return jsonify({'success': False, 'message': str(e), 'pacientes': []}), 503
    except Exception as e:
        import traceback
        logging.error(f'Erro na consulta de paciente: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Erro interno no servidor.' , 'pacientes': []}), 500


