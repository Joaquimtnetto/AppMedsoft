import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[DEBUG] %(message)s',
    handlers=[logging.StreamHandler()]  # Keeping the logging setup
)
from flask import Blueprint, request, jsonify
from medsoft_core import get_db_connection
from datetime import date, datetime
import unicodedata

def get_db_path_from_request():
    db_path = request.headers.get('X-DB-PATH') or (request.json.get('db_path') if request.is_json else None)
    if not db_path:
        raise Exception('Banco da empresa não informado (db_path).')
    print(f"[DEBUG] 127.0.0.1 - - O VALOR DO DATABASE É: {db_path}", flush=True)
    return db_path

def remover_acentos(txt):
    if not txt:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').upper()

paciente_bp = Blueprint('paciente', __name__)

@paciente_bp.route('/api/consulta-paciente', methods=['POST'])
def consulta_paciente():
    data = request.json
    db_path = get_db_path_from_request()
    termo = data.get('termo', '').strip() if data else ''
    nome_medico = data.get('nome_medico', '').strip() if data else ''
    if not termo or not nome_medico:
        return jsonify({'success': False, 'message': 'Informe nome/código e nome do médico.', 'pacientes': []}), 400
    try:
        db_path = request.headers.get('X-DB-PATH')
        print(f'[DEBUG] Chamando get_db_connection em consulta_paciente | db_path: {db_path}')
        if not db_path:
            return jsonify({'success': False, 'message': 'Banco da empresa não informado.', 'pacientes': []}), 400
        try:
            con = get_db_connection(db_path)
        except Exception as e:
            raise
        cur = con.cursor()
        termo_limpo = termo.strip()
        print(f"[DEBUG] termo_limpo: '{termo_limpo}'")
        if termo_limpo and any(c != '%' for c in termo_limpo):
            termo_busca = f"%{termo_limpo}%"
            query = '''
                SELECT nomecli, codcli,        
                       DATEDIFF(YEAR, datanasc_, CURRENT_DATE)
                        - CASE 
                            WHEN EXTRACT(MONTH FROM CURRENT_DATE) < EXTRACT(MONTH FROM datanasc_)
                                OR (EXTRACT(MONTH FROM CURRENT_DATE) = EXTRACT(MONTH FROM datanasc_) 
                                    AND EXTRACT(DAY FROM CURRENT_DATE) < EXTRACT(DAY FROM datanasc_))
                            THEN 1 
                            ELSE 0 
                            END AS idade, nomeplano1, nomed
                FROM Pacient
                WHERE UPPER(nomecli) LIKE UPPER(?)
                  AND UPPER(nomed) = UPPER(?)
                ORDER BY nomecli
            '''
            print(f"[DEBUG] Query montada: {query.strip()} | Parâmetros: termo_busca={termo_busca}, nome_medico={nome_medico}")
            cur.execute(query, (termo_busca, nome_medico))
        else:
            con.close()
            return jsonify({'success': False, 'message': 'Termo inválido.', 'pacientes': []}), 400
        pacientes = []
        rows = cur.fetchall()
        for row in rows:
            nomecli, codcli, datnasc_, nomeplano1, nomed = row
            idade = ''
            if datnasc_:
                try:
## Endpoint /api/consulta-paciente comentado para evitar duplicidade com consulta_paciente.py
#@paciente_bp.route('/api/consulta-paciente', methods=['POST'])
#def consulta_paciente():
#    data = request.json
#    db_path = get_db_path_from_request()
#    termo = data.get('termo', '').strip() if data else ''
#    if not termo:
#        return jsonify({'success': False, 'message': 'Informe um nome ou código.', 'pacientes': []}), 400
#    print("[DEBUG] Entrou em consulta_paciente")
#    data = request.json
#    print(f"[DEBUG] JSON recebido: {data}")
#    termo = data.get('termo', '').strip() if data else ''
#    nome_medico = data.get('nome_medico', '').strip() if data else ''
#    print(f"[DEBUG] termo recebido: '{termo}' | nome_medico recebido: '{nome_medico}'")
#    if not termo or not nome_medico:
#        print("[DEBUG] Falta termo ou nome_medico no JSON recebido!")
#        return jsonify({'success': False, 'message': 'Informe nome/código e nome do médico.', 'pacientes': []}), 400
#    try:
#        db_path = request.headers.get('X-DB-PATH')
#        print(f'[DEBUG] Chamando get_db_connection em consulta_paciente | db_path: {db_path}')
#        if not db_path:
#            print("[DEBUG] db_path não informado no header!")
#            return jsonify({'success': False, 'message': 'Banco da empresa não informado.', 'pacientes': []}), 400
#        try:
#            con = get_db_connection(db_path)
#            print("[DEBUG] Conexão com o banco estabelecida com sucesso!")
#        except Exception as e:
#            print(f"[DEBUG] Erro ao conectar no banco: {e}")
#            raise
#        cur = con.cursor()
#        termo_limpo = termo.strip()
#        print(f"[DEBUG] termo_limpo: '{termo_limpo}'")
#        if termo_limpo and any(c != '%' for c in termo_limpo):
#            termo_busca = f"%{termo_limpo}%"
#            query = '''
#                SELECT nomecli, codcli,        
#                       DATEDIFF(YEAR, datanasc_, CURRENT_DATE)
#                        - CASE 
#                            WHEN EXTRACT(MONTH FROM CURRENT_DATE) < EXTRACT(MONTH FROM datanasc_)
#                                OR (EXTRACT(MONTH FROM CURRENT_DATE) = EXTRACT(MONTH FROM datanasc_) 
#                                    AND EXTRACT(DAY FROM CURRENT_DATE) < EXTRACT(DAY FROM datanasc_))
#                            THEN 1 
#                            ELSE 0 
#                            END AS idade, nomeplano1, nomed
#                FROM Pacient
#                WHERE UPPER(nomecli) LIKE UPPER(?)
#                  AND UPPER(nomed) = UPPER(?)
#                ORDER BY nomecli
#            '''
#            print(f"[DEBUG] Query montada: {query.strip()} | Parâmetros: termo_busca={termo_busca}, nome_medico={nome_medico}")
#            cur.execute(query, (termo_busca, nome_medico))
#            print("[DEBUG] Query executada com sucesso!")
#        else:
#            print("[DEBUG] Termo inválido para busca!")
#            con.close()
#            return jsonify({'success': False, 'message': 'Termo inválido.', 'pacientes': []}), 400
#        pacientes = []
#        rows = cur.fetchall()
#        print(f"[DEBUG] Total de linhas retornadas: {len(rows)}")
#        for row in rows:
#            nomecli, codcli, datnasc_, nomeplano1, nomed = row
#            idade = ''
#            if datnasc_:
#                try:
                    if isinstance(datnasc_, str):
                        datanasc = datetime.strptime(datnasc_, '%Y-%m-%d').date()
                    else:
                        datanasc = datanasc_.date() if hasattr(datanasc_, 'date') else datanasc_
                    hoje = date.today()
                    idade = hoje.year - datanasc.year - ((hoje.month, hoje.day) < (datanasc.month, datanasc.day))
                except Exception:
                    idade = ''
            pacientes.append({
                'nomecli': nomecli,
                'codcli': codcli,
        con.close()
        if not rows:
            return jsonify({'success': True, 'pacientes': [], 'message': 'Nenhum paciente encontrado.'})
        return jsonify({'success': True, 'pacientes': pacientes})
    except Exception as e:
        import traceback
        logging.error(f'Erro na consulta de paciente: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e), 'pacientes': []}), 500
