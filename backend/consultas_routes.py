from datetime import date
import re
import unicodedata

from flask import Blueprint, request, jsonify, session, current_app
import config
from medsoft_diagnostics import log_event, log_exception
from medsoft_core import get_db_connection, DBConnectionError
from tenant_context import current_company_id

consultas_bp = Blueprint('consultas', __name__)
log_event('BOOT', 'consultas_routes carregado', file=__file__)


def _database_path():
    return session.get('db_path') or None

def _master_database_path():
    return config.PG_DB


def _logged_professional_info(company_id):
    connection = get_db_connection(_master_database_path())
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT usuario.idcodmed, COALESCE(perfil.nome, perfil.descricao, '')
                FROM public.ic_usuario_geral usuario
                LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = usuario.idperfil
                WHERE usuario.idusuario = %s AND usuario.idempresa = %s
                LIMIT 1
                ''',
                (session.get('idusuario'), company_id),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def _normalize_text(value):
    normalized = unicodedata.normalize('NFD', str(value or '').lower())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')


def _pattern_topics(pattern):
    topics = []
    for raw_line in str(pattern or '').replace('\r', '').split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        # Os padrões da anamnese usam títulos curtos terminados por dois-pontos.
        if line.endswith(':') and len(line) <= 100:
            topics.append(line)
    return list(dict.fromkeys(topics))


_SECTION_MARKERS = {
    'familia': ('historico familiar', 'historia familiar', 'antecedente familiar'),
    'medicamentos': ('medicamento', 'medicacao', 'remedio', 'farmaco'),
    'alergias': ('alergia', 'alergico'),
    'cirurgias': ('cirurg', 'procedimento cirurgico'),
    'habitos': ('habito', 'tabag', 'etil', 'alcool', 'atividade fisica'),
    'exame': ('exame fisico', 'exame clinico'),
    'diagnostico': ('hipotese diagnostica', 'diagnostico', 'cid'),
    'conduta': ('conduta', 'plano terapeutico', 'orientacao'),
    'antecedentes': ('antecedente pessoal', 'comorbidade', 'patologia pregressa'),
    'queixa': ('queixa principal', 'motivo da consulta'),
    'historia': ('historia da doenca', 'historico da doenca', 'hda'),
}

_SENTENCE_MARKERS = {
    'familia': ('mae ', 'pai ', 'irma', 'avo', 'familia', 'familiar'),
    'medicamentos': ('faz uso', 'em uso', 'toma ', 'medicamento', 'medicacao', 'remedio'),
    'alergias': ('alerg',),
    'cirurgias': ('cirurg', 'operad'),
    'habitos': ('fuma', 'tabag', 'etil', 'alcool', 'bebida', 'atividade fisica'),
    'exame': ('ao exame', 'exame fisico', 'ausculta', 'palpacao', 'pressao arterial'),
    'diagnostico': ('diagnostico', 'hipotese', 'cid '),
    'conduta': ('conduta', 'prescrev', 'solicito', 'orientad', 'encaminh'),
    'antecedentes': ('antecedente', 'comorbidade', 'portador', 'hipertens', 'diabet'),
}


_INLINE_SECTION_CUES = {
    'queixa': (r'queixa principal', r'motivo da consulta', r'queixa'),
    'familia': (
        r'hist[oó]ri(?:co|ca) familiar', r'antecedente familiar',
        r'hist[oó]rico da fam[ií]lia', r'hist[oó]rico\s+fam[ií]lia',
        r'familiar\s+fam[ií]lia',
    ),
    'medicamentos': (r'medicamentos?', r'medica[cç][aã]o', r'rem[eé]dios?'),
    'alergias': (r'alergias?',),
    'cirurgias': (r'cirurgias?',),
    'habitos': (r'h[aá]bitos?',),
    'exame': (r'exame f[ií]sico', r'exame cl[ií]nico'),
    'diagnostico': (r'hip[oó]tese diagn[oó]stica', r'diagn[oó]stico'),
    'conduta': (r'conduta', r'plano terap[eê]utico'),
    'antecedentes': (r'antecedentes? pessoais?', r'comorbidades?'),
    'historia': (r'hist[oó]ria da doen[cç]a atual', r'hda'),
}


def _inline_clauses(sentence, topics=None):
    """Divide um ditado continuo quando o usuario fala os nomes das secoes."""
    matches = []
    for category, cues in _INLINE_SECTION_CUES.items():
        for cue in cues:
            for match in re.finditer(r'\b(?:' + cue + r')\b', sentence, re.IGNORECASE):
                matches.append((match.start(), match.end(), category))

    # Marcadores falados sao mais seguros do que numeros isolados, que podem
    # representar dose, idade ou frequencia: "topico um", "topico dois" etc.
    number_words = ('1|um|primeiro', '2|dois|segundo', '3|tr[eê]s|terceiro',
                    '4|quatro|quarto', '5|cinco|quinto', '6|seis|sexto',
                    '7|sete|s[eé]timo', '8|oito|oitavo', '9|nove|nono')
    for index, topic in enumerate(topics or []):
        if index >= len(number_words):
            break
        category = _topic_category(topic)
        if not category:
            continue
        cue = r'\b(?:t[oó]pico|campo|se[cç][aã]o)\s+(?:' + number_words[index] + r')\b'
        for match in re.finditer(cue, sentence, re.IGNORECASE):
            matches.append((match.start(), match.end(), category))

    # Mantem o marcador mais longo quando expressoes se sobrepoem.
    selected = []
    for item in sorted(matches, key=lambda value: (value[0], -(value[1] - value[0]))):
        if any(item[0] < other[1] and item[1] > other[0] for other in selected):
            continue
        selected.append(item)
    selected.sort()
    if len({item[2] for item in selected}) < 2:
        return []

    clauses = []
    for index, (_, end, category) in enumerate(selected):
        # Marcadores repetidos da mesma secao ("familiar, familia") nao
        # criam conteudo artificial; o ultimo deles inicia o relato.
        if index + 1 < len(selected) and selected[index + 1][2] == category:
            continue
        next_start = selected[index + 1][0] if index + 1 < len(selected) else len(sentence)
        content = sentence[end:next_start]
        content = re.sub(
            r'^\s*(?:[,:;\-]|e\b|[eé]\b|[ée]\s+que\b|estou\b|ent[aã]o\b|temos\b|aqui\b|que\b)+\s*',
            '', content, flags=re.IGNORECASE,
        ).strip(' ,:;-')
        if content:
            clauses.append((category, content[0].upper() + content[1:]))
    return clauses


def _topic_category(topic):
    normalized = _normalize_text(topic)
    for category, markers in _SECTION_MARKERS.items():
        if any(marker in normalized for marker in markers):
            return category
    return None


def _sentence_category(sentence):
    normalized = ' ' + _normalize_text(sentence) + ' '
    for category, markers in _SENTENCE_MARKERS.items():
        if any(marker in normalized for marker in markers):
            return category
    return None


def _organizar_historico_local(texto_livre, padrao):
    topics = _pattern_topics(padrao)
    if not topics:
        raise ValueError('O padrão não possui tópicos terminados por dois-pontos.')

    # O formulário contém o padrão e o ditado no mesmo campo; retira apenas a
    # primeira cópia do padrão para que seus títulos não sejam tratados como relato.
    clinical_text = str(texto_livre or '').replace('\r', '').strip()
    pattern_text = str(padrao or '').replace('\r', '').strip()
    if pattern_text and pattern_text in clinical_text:
        clinical_text = clinical_text.replace(pattern_text, '', 1).strip()

    sentences = [
        part.strip(' \t\n')
        for part in re.split(r'(?<=[.!?;])\s+|\n+', clinical_text)
        if part.strip(' \t\n')
    ]
    categories = {_topic_category(topic): topic for topic in topics if _topic_category(topic)}
    default_topic = (
        categories.get('historia') or categories.get('queixa') or topics[0]
    )
    grouped = {topic: [] for topic in topics}
    for sentence in sentences:
        clauses = _inline_clauses(sentence, topics)
        if clauses:
            for category, content in clauses:
                target = categories.get(category) or default_topic
                grouped[target].append(content)
        else:
            target = categories.get(_sentence_category(sentence)) or default_topic
            grouped[target].append(sentence)

    blocks = []
    for topic in topics:
        content = '\n'.join(grouped[topic])
        blocks.append(topic + ('\n' + content if content else ''))
    return '\n\n'.join(blocks)


@consultas_bp.route('/api/consultas-paciente/organizar', methods=['POST'])
def organizar_consulta_local():
    data = request.get_json(silent=True) or {}
    texto_livre = str(data.get('texto_livre') or '').strip()
    padrao = str(data.get('padrao') or '').strip()
    if not texto_livre:
        return jsonify({'success': False, 'message': 'Informe o texto do histórico.'}), 400
    if not padrao:
        return jsonify({'success': False, 'message': 'Selecione e inclua um padrão antes de organizar.'}), 400
    if len(texto_livre) > 20000 or len(padrao) > 10000:
        return jsonify({'success': False, 'message': 'O texto é muito grande para organização.'}), 400
    try:
        historico = _organizar_historico_local(texto_livre, padrao)
        return jsonify({'success': True, 'historico': historico})
    except ValueError as error:
        return jsonify({'success': False, 'message': str(error)}), 400

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
        log_exception('HISTORICO', 'falha ao listar históricos', e)
        return jsonify({'success': False, 'message': f'ERRO_LISTA_HISTORICO_DIAG: {e}', 'consultas': []}), 500


@consultas_bp.route('/api/consultas-paciente/itens', methods=['POST'])
def incluir_consulta_paciente():
    log_event('HISTORICO', 'entrou no endpoint de inclusão')
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
        user_row = _logged_professional_info(company_id)
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
    except Exception as exc:
        log_exception('HISTORICO', 'falha ao incluir histórico', exc)
        current_app.logger.exception('Falha ao incluir historico do paciente')
        if con:
            con.rollback()
        return jsonify({'success': False, 'message': f'ERRO_HISTORICO_DIAG: {exc}'}), 500
    finally:
        if con:
            con.close()


@consultas_bp.route('/api/consultas-paciente/itens/<int:consulta_cod>', methods=['PUT'])
def alterar_consulta_paciente(consulta_cod):
    data = request.get_json(silent=True) or {}
    codpac = data.get('codpac')
    historico = str(data.get('historico') or '').strip()

    try:
        codpac = int(codpac)
        if codpac <= 0 or consulta_cod <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Código da consulta ou do paciente inválido.'}), 400

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
        user_row = _logged_professional_info(company_id)
        logged_professional_id = user_row[0] if user_row else None
        logged_profile = str(user_row[1] or '').strip().upper() if user_row else ''
        if logged_profile in ('PROFSAÚDE', 'PROFSAUDE', 'PROF. SAÚDE', 'PROF. SAUDE') and not logged_professional_id:
            return jsonify({
                'success': False,
                'message': 'O usuário Prof. Saúde não possui profissional relacionado.',
            }), 400

        cur.execute(
            '''
            UPDATE public.consulta
               SET dtvisita = %s,
                   historico = %s,
                   datatualiza = CURRENT_TIMESTAMP,
                   codmed = %s
             WHERE cod = %s
               AND codpac = %s
               AND codclin = %s
             RETURNING cod
            ''',
            (dtvisita, historico.encode('utf-8'), logged_professional_id, consulta_cod, codpac, company_id),
        )
        if not cur.fetchone():
            return jsonify({'success': False, 'message': 'Histórico não encontrado para alteração.'}), 404

        cur.execute(
            '''
            UPDATE public.pacient
               SET datult_ = (SELECT MAX(dtvisita) FROM public.consulta WHERE codpac = %s AND codclin = %s)
             WHERE codcli = %s
               AND codclin = %s
            RETURNING datult_
            ''',
            (codpac, company_id, codpac, company_id),
        )
        if not cur.fetchone():
            raise ValueError('Não foi possível atualizar a data da última consulta do paciente.')

        con.commit()
        return jsonify({
            'success': True,
            'message': 'Histórico alterado com sucesso.',
            'consulta': {
                'cod': consulta_cod,
                'codpac': codpac,
                'dtvisita': dtvisita.strftime('%d/%m/%Y'),
                'historico': historico,
                'codmed': logged_professional_id,
            },
        })
    except DBConnectionError as e:
        return jsonify({'success': False, 'message': str(e)}), 503
    except Exception as exc:
        log_exception('HISTORICO', 'falha ao alterar histórico', exc)
        current_app.logger.exception('Falha ao alterar historico do paciente')
        if con:
            con.rollback()
        return jsonify({'success': False, 'message': f'ERRO_HISTORICO_ALTERACAO_DIAG: {exc}'}), 500
    finally:
        if con:
            con.close()
