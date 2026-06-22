
from flask import Blueprint, request, jsonify, session
from medsoft_core import get_db_connection, DBConnectionError

consultas_bp = Blueprint('consultas', __name__)

@consultas_bp.route('/api/consultas-paciente', methods=['POST'])
def consultas_paciente():
    data = request.json
    codpac = data.get('codpac')
    try:
        if not codpac:
            return jsonify({'success': False, 'message': 'Código do paciente não informado.', 'consultas': []}), 400
        try:
            db_path = request.headers.get('X-DB-PATH') or session.get('db_path') or None
            con = get_db_connection(db_path)
        except Exception as e:
            if isinstance(e, DBConnectionError):
                return jsonify({'success': False, 'message': str(e), 'consultas': []}), 503
            return jsonify({'success': False, 'message': f'Erro ao conectar no banco: {e}', 'consultas': []}), 500
        cur = con.cursor()
        consultas = []
        try:
            codpac_int = int(codpac)
        except Exception:
            con.close()
            return jsonify({'success': False, 'message': 'Código do paciente inválido.', 'consultas': []}), 400
        query = '''
            SELECT c.dtvisita, c.diag, c.historico, p.nomecli
            FROM public.consulta c
            INNER JOIN public.pacient p ON p.codcli = c.codpac
            WHERE c.codpac = %s
            ORDER BY c.dtvisita DESC, c.cod DESC
        '''
        cur.execute(query, (codpac_int,))
        rows = cur.fetchall()
        for idx, row in enumerate(rows):
            dtvisita, diag, historico, nomepac = row
            if isinstance(historico, memoryview):
                historico = historico.tobytes()
            if isinstance(historico, bytes):
                try:
                    historico = historico.decode('utf-8')
                except UnicodeDecodeError:
                    historico = historico.decode('latin-1', errors='replace')
            elif hasattr(historico, 'read'):
                historico = historico.read().decode(errors='ignore')
            # Formata o texto do histórico preservando quebras de linha
            if historico:
                historico = historico.replace('\r\n', '\n').replace('\r', '\n')
                historico = historico.replace('\n', '<br>')
            # Adiciona separador visual forte entre registros, exceto o primeiro
            separador = ''
            if idx > 0:
                separador = '<hr style="border:2px solid #1976d2; margin:16px 0;">'
            consultas.append({
                'dtvisita': dtvisita.strftime('%d/%m/%Y') if dtvisita else '',
                'diag': diag or '',
                'historico': historico or '',
                'clinica': '',
                'nomepac': nomepac or '',
                'separador': separador
            })
        con.close()
        return jsonify({'success': True, 'consultas': consultas})
    except DBConnectionError as e:
        return jsonify({'success': False, 'message': str(e), 'consultas': []}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': 'Erro interno no servidor.', 'consultas': []}), 500
