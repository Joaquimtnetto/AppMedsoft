from flask import Blueprint, request, jsonify, session
from medsoft_core import get_db_connection, DBConnectionError
import datetime

agenda_api_bp = Blueprint('agenda_api', __name__)

@agenda_api_bp.route('/api/agenda', methods=['POST'])
def api_agenda():
    data = request.json
    data_str = data.get('data')
    nome_medico = session.get('nome_medico', '')
    if not data_str or not nome_medico:
        return jsonify({'success': False, 'message': 'Dados insuficientes.'}), 400
    try:
        # Para Postgres, usamos data como date
        data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
        con = get_db_connection()
        cur = con.cursor()
        query = '''
            SELECT a.HORACONS, a.NOMEPACI, a.TELEFONE, a.NOMEPLANO, a.PROCED
              FROM agenda a
                 JOIN nomed m ON m.CODCLIN  =  a.CODCLIN AND m.COD = a.NOMED AND m.NOMED = %s
            WHERE a.DATACONS = %s
            ORDER BY a.HORACONS
        '''
        cur.execute(query, (nome_medico, data_obj))
        rows = cur.fetchall()
        resultados = []
        for row in rows:
            resultados.append({
                'HORACONS': row[0],
                'NOMEPACI': row[1],
                'TELEFONE': row[2],
                'NOMEPLANO': row[3],
                'PROCED': row[4],
            })
        con.close()
        return jsonify({'success': True, 'resultados': resultados})
    except DBConnectionError as e:
        return jsonify({'success': False, 'message': str(e)}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500
