
from datetime import date

from flask import Blueprint, request, jsonify, session
from medsoft_core import get_db_connection, DBConnectionError
from tenant_context import current_company_id

consultas_bp = Blueprint('consultas', __name__)


def _database_path():
    return session.get('db_path') or None

@consultas_bp.route('/api/consultas-paciente', methods=['POST'])
def consultas_paciente():
    data = request.json
    codpac = data.get('codpac')
    try:
        if not codpac:
            return jsonify({'success': False, 'message': 'Código do paciente não informado.', 'consultas': []}), 400
        try:
            con = get_db_connection(_database_path())
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
            SELECT
                c.cod, c.codpac, c.dtvisita, c.diag, c.teraup, c.exame,
                c.temp, c.historico, c.peso, c.pressao, c.datatualiza,
                c.codmed, COALESCE(m.nomed, '') AS medico_nome
            FROM public.consulta c
            INNER JOIN public.pacient p ON p.codcli = c.codpac
            LEFT JOIN public.nomed m
              ON BTRIM(CAST(m.cod AS TEXT)) = CAST(c.codmed AS TEXT)
             AND m.codclin = c.codclin
            WHERE p.codcli = %s
              AND p.codclin = %s
              AND c.codclin = %s
            ORDER BY c.dtvisita DESC NULLS LAST, c.cod DESC
        '''
        company_id = current_company_id()
        cur.execute(query, (codpac_int, company_id, company_id))
        rows = cur.fetchall()
        for row in rows:
            cod, codpac_row, dtvisita, diag, teraup, exame, temp, historico, peso, pressao, datatualiza, codmed, medico_nome = row
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
            consultas.append({
                'cod': cod,
                'codpac': codpac_row,
                'dtvisita': dtvisita.strftime('%d/%m/%Y') if dtvisita else '',
                'diag': diag or '',
                'teraup': teraup or '',
                'exame': exame or '',
                'temp': temp or '',
                'historico': historico or '',
                'peso': peso or '',
                'pressao': pressao or '',
                'datatualiza': datatualiza.strftime('%d/%m/%Y %H:%M') if datatualiza else '',
                'codmed': codmed,
                'medico_nome': medico_nome or '',
            })
        con.close()
        return jsonify({'success': True, 'consultas': consultas})
    except DBConnectionError as e:
        return jsonify({'success': False, 'message': str(e), 'consultas': []}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': 'Erro interno no servidor.', 'consultas': []}), 500


@consultas_bp.route('/api/consultas-paciente/itens', methods=['POST'])
def incluir_consulta_paciente():
    data = request.get_json(silent=True) or {}
    codpac = data.get('codpac')
    historico = str(data.get('historico') or '').strip()

    try:
        codpac = int(codpac)
        if codpac <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Código do paciente inválido.'}), 400

    try:
        dtvisita = date.fromisoformat(str(data.get('dtvisita') or ''))
    except ValueError:
        return jsonify({'success': False, 'message': 'Data da visita inválida.'}), 400

    if not historico:
        return jsonify({'success': False, 'message': 'Informe o histórico da consulta.'}), 400

    con = None
    try:
        con = get_db_connection(_database_path())
        cur = con.cursor()
        company_id = current_company_id()
        cur.execute(
            'SELECT 1 FROM public.pacient WHERE codcli = %s AND codclin = %s',
            (codpac, company_id),
        )
        if not cur.fetchone():
            return jsonify({'success': False, 'message': 'Paciente não encontrado.'}), 404

        cur.execute('''
            SELECT usuario.idcodmed, COALESCE(perfil.nome, perfil.descricao, '')
            FROM public.ic_usuario_geral usuario
            LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = usuario.idperfil
            WHERE usuario.idusuario = %s AND usuario.idempresa = %s
            LIMIT 1
        ''', (session.get('idusuario'), company_id))
        user_row = cur.fetchone()
        logged_professional_id = user_row[0] if user_row else None
        logged_profile = str(user_row[1] or '').strip().upper() if user_row else ''
        if logged_profile in ('PROFSAÚDE', 'PROFSAUDE', 'PROF. SAÚDE', 'PROF. SAUDE') and not logged_professional_id:
            return jsonify({
                'success': False,
                'message': 'O usuário Prof. Saúde não possui profissional relacionado.',
            }), 400

        # A tabela legada nao possui sequence para cod. O lock evita cod duplicado
        # quando duas inclusoes acontecem ao mesmo tempo.
        cur.execute('LOCK TABLE public.consulta IN EXCLUSIVE MODE')
        cur.execute('SELECT COALESCE(MAX(cod), 0) + 1 FROM public.consulta')
        novo_cod = cur.fetchone()[0]
        cur.execute(
            '''
            INSERT INTO public.consulta
                (codpac, dtvisita, cod, historico, datatualiza, codclin, codmed)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
            ''',
            (codpac, dtvisita, novo_cod, historico.encode('utf-8'), company_id, logged_professional_id),
        )
        cur.execute(
            '''
            UPDATE public.pacient
               SET datult_ = %s
             WHERE codcli = %s
               AND codclin = %s
            RETURNING datult_
            ''',
            (dtvisita, codpac, company_id),
        )
        if not cur.fetchone():
            raise ValueError('Não foi possível atualizar a data da última consulta do paciente.')
        con.commit()
        return jsonify({
            'success': True,
            'message': 'Histórico incluído com sucesso.',
            'consulta': {
                'cod': novo_cod,
                'codpac': codpac,
                'dtvisita': dtvisita.strftime('%d/%m/%Y'),
                'historico': historico,
                'codmed': logged_professional_id,
            },
        }), 201
    except DBConnectionError as e:
        return jsonify({'success': False, 'message': str(e)}), 503
    except Exception:
        if con:
            con.rollback()
        return jsonify({'success': False, 'message': 'Erro interno ao incluir o histórico.'}), 500
    finally:
        if con:
            con.close()
