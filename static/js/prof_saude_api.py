from contextlib import contextmanager
import base64
import re

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import errors, sql

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import TENANT_COLUMN, current_company_id

prof_saude_api_bp = Blueprint('prof_saude_api', __name__)

TABLE_CANDIDATES = ('nomed',)
ID_CANDIDATES = ('codmed', 'cod', 'codigo', 'id')
FIELD_CANDIDATES = {
    'nome': ('nomed', 'nome', 'nomeprof', 'nome_prof'),
    'cep': ('cep',),
    'uf': ('uf', 'ufmed', 'uf_prof'),
    'municipio': ('municipio', 'cidade', 'cidmed'),
    'endereco': ('endereco', 'end', 'ender'),
    'bairro': ('bairro', 'bai', 'baimed'),
    'email': ('email', 'e_mail'),
    'telefone': ('telefone', 'tel', 'fone'),
    'celular': ('celular', 'cel'),
    'cpf': ('cpf',),
    'conselho': ('conselho', 'cons'),
    'nrconselho': ('nrconselho', 'nr_conselho', 'numconselho', 'crm'),
    'especialidade': ('especialidade', 'especialid', 'especial'),
    'subespecialidade': ('subespecialidade', 'sub_especialidade', 'subespecial'),
    'observacao': ('observacao', 'obs'),
    'segunda_ativo': ('seg', 'segunda_ativo'),
    'segunda_inicio': ('iseg', 'segunda_inicio', 'seg_inicio', 'seg_ini', 'horainiseg', 'segundaini'),
    'segunda_termino': ('fseg', 'segunda_termino', 'seg_termino', 'seg_fim', 'horafimseg', 'segundafim'),
    'terca_ativo': ('terc', 'terca_ativo'),
    'terca_inicio': ('iter', 'terca_inicio', 'ter_inicio', 'ter_ini', 'horainiter', 'tercaini'),
    'terca_termino': ('fter', 'terca_termino', 'ter_termino', 'ter_fim', 'horafimter', 'tercafim'),
    'quarta_ativo': ('qua', 'quarta_ativo'),
    'quarta_inicio': ('iqua', 'quarta_inicio', 'qua_inicio', 'qua_ini', 'horainiqua', 'quartaini'),
    'quarta_termino': ('tqua', 'quarta_termino', 'qua_termino', 'qua_fim', 'horafimqua', 'quartafim'),
    'quinta_ativo': ('qui', 'quinta_ativo'),
    'quinta_inicio': ('iqui', 'quinta_inicio', 'qui_inicio', 'qui_ini', 'horainiqui', 'quintaini'),
    'quinta_termino': ('tqui', 'quinta_termino', 'qui_termino', 'qui_fim', 'horafimqui', 'quintafim'),
    'sexta_ativo': ('sex', 'sexta_ativo'),
    'sexta_inicio': ('isex', 'sexta_inicio', 'sex_inicio', 'sex_ini', 'horainisex', 'sextaini'),
    'sexta_termino': ('tsex', 'sexta_termino', 'sex_termino', 'sex_fim', 'horafimsex', 'sextafim'),
    'sabado_ativo': ('sab', 'sabado_ativo'),
    'sabado_inicio': ('isab', 'sabado_inicio', 'sab_inicio', 'sab_ini', 'horainisab', 'sabadoini'),
    'sabado_termino': ('tsab', 'sabado_termino', 'sab_termino', 'sab_fim', 'horafimsab', 'sabadofim'),
    'domingo_ativo': ('dom', 'domingo_ativo'),
    'domingo_inicio': ('idom', 'domingo_inicio', 'dom_inicio', 'dom_ini', 'horainidom', 'domingoini'),
    'domingo_termino': ('tdom', 'domingo_termino', 'dom_termino', 'dom_fim', 'horafimdom', 'domingofim'),
}

SCHEDULE_DAYS = ('segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo')

MAX_LENGTHS = {
    'nome': 40,
    'cep': 9,
    'uf': 2,
    'municipio': 30,
    'endereco': 60,
    'bairro': 30,
    'email': 60,
    'telefone': 14,
    'celular': 14,
    'cpf': 14,
    'conselho': 10,
    'nrconselho': 20,
    'especialidade': 40,
    'subespecialidade': 40,
    'observacao': 400,
}


PREFERE_FIELD_CANDIDATES = {
    'tit1': ('nomeclin',),
    'tit2': ('tit2',),
    'tit3': ('tit3',),
    'rod1': ('rod1',),
    'rod2': ('rod2',),
    'cidade_receita': ('cidade',),
    'logoprin': ('logoprin',),
    'logorec': ('logorec',),
    'fonte_cabecalho': ('fonte_cabecalho', 'fontecab', 'fonte_cab'),
    'tamanho_cabecalho': ('tamanho_cabecalho', 'tamcab', 'tamanho_cab'),
    'fonte_cabecalho2': ('fonte_cabecalho2', 'fontecab2', 'fonte_cab2'),
    'tamanho_cabecalho2': ('tamanho_cabecalho2', 'tamcab2', 'tamanho_cab2'),
    'fonte_cabecalho3': ('fonte_cabecalho3', 'fontecab3', 'fonte_cab3'),
    'tamanho_cabecalho3': ('tamanho_cabecalho3', 'tamcab3', 'tamanho_cab3'),
    'fonte_rodape': ('fonte_rodape', 'fonterod', 'fonte_rod'),
    'tamanho_rodape': ('tamanho_rodape', 'tamrod', 'tamanho_rod'),
    'linha_cabecalho': ('linha_cabecalho', 'linhacab'),
    'espessura_linha_cabecalho': ('espessura_linha_cabecalho', 'esp_linha_cabecalho', 'esp_linhacab'),
    'linha_rodape': ('linha_rodape', 'linharod'),
    'espessura_linha_rodape': ('espessura_linha_rodape', 'esp_linha_rodape', 'esp_linharod'),
}
PREFERE_IMAGE_FIELDS = {'logoprin', 'logorec'}
PREFERE_MAX_LENGTHS = {
    'tit1': 60,
    'tit2': 60,
    'tit3': 60,
    'rod1': 60,
    'rod2': 60,
    'cidade_receita': 20,
    'fonte_cabecalho': 40,
    'fonte_cabecalho2': 40,
    'fonte_cabecalho3': 40,
    'fonte_rodape': 40,
    'linha_cabecalho': 1,
    'linha_rodape': 1,
}

PREFERE_NUMERIC_FIELDS = {'tamanho_cabecalho', 'tamanho_cabecalho2', 'tamanho_cabecalho3', 'tamanho_rodape'}
PREFERE_DECIMAL_FIELDS = {'espessura_linha_cabecalho', 'espessura_linha_rodape'}
PREFERE_YES_NO_FIELDS = {'linha_cabecalho', 'linha_rodape'}

TEXTO_FIELD_CANDIDATES = {
    'nome': ('nome',),
    'texto': ('texto',),
    'atalho': ('atalho',),
    'msghtml': ('msghtml',),
    'codclin': ('codclin',),
}



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


def _fetch_table_columns(cursor, table_name):
    cursor.execute("""
        SELECT column_name, data_type, column_default, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = %s
    """, (table_name,))
    return {
        row[0].lower(): {
            'name': row[0],
            'data_type': row[1] or '',
            'default': row[2],
            'max_length': row[3],
        }
        for row in cursor.fetchall()
    }


def _pick(columns, candidates):
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def _detect_layout(cursor):
    for table_candidate in TABLE_CANDIDATES:
        columns = _fetch_table_columns(cursor, table_candidate)
        if not columns:
            continue
        id_column = _pick(columns, ID_CANDIDATES)
        nome_column = _pick(columns, FIELD_CANDIDATES['nome'])
        if not id_column or not nome_column:
            continue
        fields = {}
        field_metadata = {}
        for logical_name, candidates in FIELD_CANDIDATES.items():
            column = _pick(columns, candidates)
            if column:
                fields[logical_name] = column['name']
                field_metadata[logical_name] = column
        generate_integer_id = (
            id_column['default'] is None and
            any(kind in id_column['data_type'].lower() for kind in ('integer', 'bigint', 'smallint'))
        )
        generate_legacy_id = id_column['default'] is None and (
            generate_integer_id or id_column['data_type'].lower() in ('character', 'character varying', 'text')
        )
        return {
            'table': table_candidate,
            'id_column': id_column['name'],
            'id_metadata': id_column,
            'fields': fields,
            'field_metadata': field_metadata,
            'generate_integer_id': generate_integer_id,
            'generate_legacy_id': generate_legacy_id,
            'tenant_column': (_pick(columns, (TENANT_COLUMN,)) or {}).get('name'),
        }
    raise ValueError('Tabela public.NOMED nao encontrada no banco.')



def _prefere_layout(cursor):
    columns = _fetch_table_columns(cursor, 'prefere')
    if not columns:
        return None
    codmed_column = _pick(columns, ('codmed',))
    if not codmed_column:
        return None
    fields = {}
    for logical_name, candidates in PREFERE_FIELD_CANDIDATES.items():
        column = _pick(columns, candidates)
        if column:
            fields[logical_name] = column['name']
    return {
        'table': 'prefere', 'id_column': codmed_column['name'], 'fields': fields,
        'tenant_column': (_pick(columns, (TENANT_COLUMN,)) or {}).get('name'),
    }


def _texto_layout(cursor):
    columns = _fetch_table_columns(cursor, 'texto')
    if not columns:
        return None
    nome_column = _pick(columns, TEXTO_FIELD_CANDIDATES['nome'])
    texto_column = _pick(columns, TEXTO_FIELD_CANDIDATES['texto'])
    if not nome_column or not texto_column:
        return None
    fields = {}
    for logical_name, candidates in TEXTO_FIELD_CANDIDATES.items():
        column = _pick(columns, candidates)
        if column:
            fields[logical_name] = column['name']
    codigo_column = _pick(columns, ('codigo', 'codtexto', 'cod', 'idtexto', 'id'))
    return {
        'table': 'texto', 'id_column': nome_column['name'], 'fields': fields,
        'tenant_column': fields.get(TENANT_COLUMN),
        'codigo_column': codigo_column['name'] if codigo_column else None,
    }


def _texto_key(record_id):
    return f'ANAMNESE {str(record_id).strip()}'[:30]


def _decode_image(value):
    if not value:
        return None
    value = str(value)
    if not value.startswith('data:image'):
        return None
    try:
        return base64.b64decode(value.split(',', 1)[1])
    except Exception as exc:
        raise ValueError('Imagem do receituario invalida.') from exc


def _encode_image(value):
    if value is None:
        return ''
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return 'data:image/png;base64,' + base64.b64encode(value).decode('ascii')
    return ''


def _prefere_values(data, layout):
    if not layout:
        return {}
    values = {}
    for logical_name, column_name in layout['fields'].items():
        if logical_name in PREFERE_IMAGE_FIELDS:
            if logical_name in data and data.get(logical_name):
                values[column_name] = _decode_image(data.get(logical_name))
            continue
        raw_value = data.get(logical_name)
        value = '' if raw_value is None else str(raw_value).strip()
        if logical_name in PREFERE_YES_NO_FIELDS:
            normalized = value.upper()
            if normalized in ('TRUE', '1', 'SIM', 'YES'):
                normalized = 'S'
            elif normalized in ('FALSE', '0', 'NAO', 'NÃO', 'NO'):
                normalized = 'N'
            if normalized not in ('S', 'N'):
                raise ValueError(f'O campo {logical_name} deve ser S ou N.')
            values[column_name] = normalized
            continue
        if value and logical_name in PREFERE_MAX_LENGTHS and len(value) > PREFERE_MAX_LENGTHS[logical_name]:
            raise ValueError(f'O campo {logical_name} excede {PREFERE_MAX_LENGTHS[logical_name]} caracteres.')
        if logical_name in PREFERE_DECIMAL_FIELDS:
            if value == '':
                values[column_name] = None
                continue
            try:
                number = float(value.replace(',', '.'))
            except ValueError as exc:
                raise ValueError(f'O campo {logical_name} deve ser numérico.') from exc
            if number < 0.5 or number > 3:
                raise ValueError(f'O campo {logical_name} deve estar entre 0.5 e 3.')
            values[column_name] = number
            continue
        if logical_name in PREFERE_NUMERIC_FIELDS:
            if value == '':
                values[column_name] = None
                continue
            try:
                number = int(value)
            except ValueError as exc:
                raise ValueError(f'O campo {logical_name} deve ser numérico.') from exc
            if number < 8 or number > 30:
                raise ValueError(f'O campo {logical_name} deve estar entre 8 e 30.')
            values[column_name] = number
            continue
        values[column_name] = None if value == '' else value
    return values


def _upsert_prefere(cursor, record_id, data):
    """Grava as preferências do receituário e confirma no próprio banco.

    A confirmação é especialmente importante para linha_cabecalho/linha_rodape,
    pois evita informar sucesso quando o UPDATE não atingiu o registro esperado.
    """
    layout = _prefere_layout(cursor)
    if not layout:
        raise ValueError('Tabela public.PREFERE não encontrada no banco.')
    values = _prefere_values(data, layout)
    if not values:
        return {}
    id_col = layout['id_column']
    tenant_col = layout.get('tenant_column')
    if not tenant_col:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.PREFERE.')
    company_id = current_company_id()

    cursor.execute(
        sql.SQL('SELECT 1 FROM {}.{} WHERE CAST({} AS TEXT) = %s AND {} = %s LIMIT 1').format(
            sql.Identifier('public'), sql.Identifier(layout['table']), sql.Identifier(id_col),
            sql.Identifier(tenant_col),
        ),
        (str(record_id), company_id)
    )
    exists = cursor.fetchone() is not None
    if not exists and not any(value is not None for value in values.values()):
        return {}

    title_column = layout['fields'].get('tit1')
    if not exists and title_column and values.get(title_column) is None:
        values[title_column] = (data.get('nome') or '').strip()

    if exists:
        statement = sql.SQL('UPDATE {}.{} SET {} WHERE CAST({} AS TEXT) = %s AND {} = %s').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(', ').join(
                sql.SQL('{} = %s').format(sql.Identifier(column)) for column in values
            ),
            sql.Identifier(id_col),
            sql.Identifier(tenant_col),
        )
        cursor.execute(statement, list(values.values()) + [str(record_id), company_id])
        if cursor.rowcount != 1:
            raise ValueError(
                f'Não foi possível atualizar PREFERE para CODMED={record_id} e CODCLIN={company_id}.'
            )
    else:
        columns = [id_col, tenant_col] + list(values.keys())
        statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(', ').join(sql.Identifier(column) for column in columns),
            sql.SQL(', ').join(sql.Placeholder() for _ in columns),
        )
        cursor.execute(statement, [str(record_id), company_id] + list(values.values()))
        if cursor.rowcount != 1:
            raise ValueError(
                f'Não foi possível inserir PREFERE para CODMED={record_id} e CODCLIN={company_id}.'
            )

    # Lê imediatamente os campos que acabaram de ser gravados. Assim um retorno
    # "sucesso" só ocorre quando o PostgreSQL realmente contém os valores enviados.
    verify_logical = [
        name for name in (
            'fonte_cabecalho', 'tamanho_cabecalho',
            'fonte_cabecalho2', 'tamanho_cabecalho2',
            'fonte_cabecalho3', 'tamanho_cabecalho3',
            'fonte_rodape', 'tamanho_rodape',
            'linha_cabecalho', 'espessura_linha_cabecalho',
            'linha_rodape', 'espessura_linha_rodape',
        ) if name in layout['fields']
    ]
    if not verify_logical:
        return {}

    verify_columns = [layout['fields'][name] for name in verify_logical]
    cursor.execute(
        sql.SQL('SELECT {} FROM {}.{} WHERE CAST({} AS TEXT) = %s AND {} = %s LIMIT 1').format(
            sql.SQL(', ').join(sql.Identifier(column) for column in verify_columns),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.Identifier(id_col),
            sql.Identifier(tenant_col),
        ),
        (str(record_id), company_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError('PREFERE foi gravada, mas não pôde ser relida para confirmação.')

    saved = dict(zip(verify_logical, row))

    # Confirma todos os campos de configuração do receituário, não apenas S/N.
    # Isso evita retornar sucesso quando fonte/tamanho 2 ou 3 não foram realmente persistidos.
    for logical_name in verify_logical:
        if logical_name not in data:
            continue

        raw_expected = data.get(logical_name)
        if logical_name in PREFERE_YES_NO_FIELDS:
            expected = str(raw_expected or '').strip().upper()
            if expected in ('TRUE', '1', 'SIM', 'YES'):
                expected = 'S'
            elif expected in ('FALSE', '0', 'NAO', 'NÃO', 'NO'):
                expected = 'N'
            actual = '' if saved.get(logical_name) is None else str(saved.get(logical_name)).strip().upper()
        elif logical_name in PREFERE_NUMERIC_FIELDS:
            expected = None if raw_expected in (None, '') else int(str(raw_expected).strip())
            actual = None if saved.get(logical_name) is None else int(saved.get(logical_name))
        elif logical_name in PREFERE_DECIMAL_FIELDS:
            expected = None if raw_expected in (None, '') else float(str(raw_expected).strip().replace(',', '.'))
            actual = None if saved.get(logical_name) is None else float(saved.get(logical_name))
        else:
            expected = '' if raw_expected is None else str(raw_expected).strip()
            actual = '' if saved.get(logical_name) is None else str(saved.get(logical_name)).strip()

        if actual != expected:
            raise ValueError(
                f'Falha ao confirmar {logical_name}: enviado {expected}, banco retornou {actual if actual not in (None, "") else "vazio"}.'
            )
    return saved


def _load_prefere_for_ids(cursor, profissionais):
    if not profissionais:
        return
    layout = _prefere_layout(cursor)
    if not layout:
        return
    fields = layout['fields']
    if not fields:
        return
    ids = [str(item.get('id')) for item in profissionais if item.get('id') is not None]
    if not ids:
        return
    select_items = [sql.SQL('{} AS codmed').format(sql.Identifier(layout['id_column']))]
    for logical_name, column_name in fields.items():
        select_items.append(sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name)))
    tenant_col = layout.get('tenant_column')
    if not tenant_col:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.PREFERE.')
    statement = sql.SQL('SELECT {} FROM {}.{} WHERE CAST({} AS TEXT) = ANY(%s) AND {} = %s').format(
        sql.SQL(', ').join(select_items),
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.Identifier(layout['id_column']),
        sql.Identifier(tenant_col),
    )
    cursor.execute(statement, (ids, current_company_id()))
    names = ['codmed'] + list(fields.keys())
    by_id = {}
    for row in cursor.fetchall():
        pref = _row_dict(names, row)
        for image_field in PREFERE_IMAGE_FIELDS:
            if image_field in pref:
                pref[image_field] = _encode_image(pref[image_field])
        by_id[str(pref.get('codmed')).strip()] = pref
    for item in profissionais:
        pref = by_id.get(str(item.get('id')).strip())
        if pref:
            item.update({k: v for k, v in pref.items() if k != 'codmed'})


def _upsert_texto(cursor, record_id, data):
    nome_value = (data.get('anamnese_nome') or '').strip()
    texto_value = (data.get('anamnese_texto') or '').strip()
    if len(nome_value) > 30:
        raise ValueError('O campo Nome da anamnese excede 30 caracteres.')
    if not nome_value:
        if texto_value:
            raise ValueError('Informe o nome da anamnese.')
        return
    layout = _texto_layout(cursor)
    if not layout:
        return
    key = nome_value
    id_col = layout['id_column']
    tenant_col = layout.get('tenant_column')
    if not tenant_col:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.TEXTO.')
    company_id = current_company_id()
    cursor.execute(
        sql.SQL('SELECT 1 FROM {}.{} WHERE {} = %s AND {} = %s LIMIT 1').format(
            sql.Identifier('public'), sql.Identifier(layout['table']), sql.Identifier(id_col),
            sql.Identifier(tenant_col),
        ),
        (key, company_id)
    )
    exists = cursor.fetchone() is not None
    if not exists and not texto_value:
        return

    values = {
        layout['fields']['texto']: None if texto_value == '' else texto_value,
    }

    if exists:
        statement = sql.SQL('UPDATE {}.{} SET {} WHERE {} = %s AND {} = %s').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(', ').join(
                sql.SQL('{} = %s').format(sql.Identifier(column)) for column in values
            ),
            sql.Identifier(id_col),
            sql.Identifier(tenant_col),
        )
        cursor.execute(statement, list(values.values()) + [key, company_id])
    else:
        columns = [id_col, tenant_col] + list(values.keys())
        statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
            sql.SQL(', ').join(sql.Identifier(column) for column in columns),
            sql.SQL(', ').join(sql.Placeholder() for _ in columns),
        )
        cursor.execute(statement, [key, company_id] + list(values.values()))


def _load_texto_for_ids(cursor, profissionais):
    if not profissionais:
        return
    layout = _texto_layout(cursor)
    if not layout:
        return
    id_col = layout['id_column']
    texto_col = layout['fields']['texto']
    keys = {
        _texto_key(item.get('id')): item
        for item in profissionais
        if item.get('id') is not None
    }
    if not keys:
        return
    select_items = [
        sql.SQL('{} AS nome').format(sql.Identifier(id_col)),
        sql.SQL('{} AS anamnese_texto').format(sql.Identifier(texto_col)),
    ]
    tenant_col = layout.get('tenant_column')
    if not tenant_col:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.TEXTO.')
    statement = sql.SQL('SELECT {} FROM {}.{} WHERE {} = ANY(%s) AND {} = %s').format(
        sql.SQL(', ').join(select_items),
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.Identifier(id_col),
        sql.Identifier(tenant_col),
    )
    cursor.execute(statement, (list(keys), current_company_id()))
    for row in cursor.fetchall():
        texto = _row_dict(['nome', 'anamnese_texto'], row)
        item = keys.get(texto.get('nome'))
        if item:
            item['anamnese_nome'] = texto.get('nome') or ''
            item['anamnese_texto'] = texto.get('anamnese_texto') or ''


def _layout():
    with _connection() as connection:
        with connection.cursor() as cursor:
            return _detect_layout(cursor)


def _repository(layout):
    if not layout['tenant_column']:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.NOMED.')
    return CrudRepository(
        connection_factory=_connection,
        table=layout['table'],
        id_column=layout['id_column'],
        writable_columns=tuple(layout['fields'].values()),
        generate_integer_id=layout['generate_integer_id'],
        tenant_column=layout['tenant_column'],
        tenant_value_factory=current_company_id,
    )


def _find_professional_id_by_name(layout, name):
    name = (name or '').strip()
    if not name:
        return None
    tenant_column = layout.get('tenant_column')
    name_column = layout['fields'].get('nome')
    if not tenant_column or not name_column:
        return None
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL('''
                    SELECT {}
                    FROM {}.{}
                    WHERE UPPER(BTRIM({})) = UPPER(BTRIM(%s))
                      AND {} = %s
                    LIMIT 1
                ''').format(
                    sql.Identifier(layout['id_column']),
                    sql.Identifier('public'),
                    sql.Identifier(layout['table']),
                    sql.Identifier(name_column),
                    sql.Identifier(tenant_column),
                ),
                (name, current_company_id()),
            )
            row = cursor.fetchone()
    return row[0] if row else None


def _update_profissional(layout, record_id, item):
    repository = _repository(layout)
    record_id_text = str(record_id or '').strip().lower()
    has_valid_record_id = record_id_text not in ('', 'none', 'null', 'undefined')
    if has_valid_record_id and repository.update(record_id, item):
        return record_id
    actual_id = _find_professional_id_by_name(layout, item.get(layout['fields']['nome']))
    if actual_id is not None and repository.update(actual_id, item):
        return actual_id
    generated_id = _update_professional_without_id_by_name(layout, item)
    if generated_id is not None:
        return generated_id
    return None


def _insert_profissional(cursor, layout, item):
    if not layout.get('tenant_column'):
        raise ValueError('Campo CODCLIN nao encontrado na tabela public.NOMED.')
    values = dict(item)
    values[layout['tenant_column']] = current_company_id()
    if layout.get('generate_legacy_id'):
        cursor.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s))',
            (f"public.{layout['table']}",),
        )
        values[layout['id_column']] = _next_professional_id(cursor, layout)
    columns = list(values)
    statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}').format(
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.SQL(', ').join(map(sql.Identifier, columns)),
        sql.SQL(', ').join(sql.Placeholder() for _ in columns),
        sql.Identifier(layout['id_column']),
    )
    cursor.execute(statement, [values[column] for column in columns])
    return cursor.fetchone()[0]


def _create_profissional(layout, item):
    if not layout.get('tenant_column'):
        raise ValueError('Campo CODCLIN não encontrado na tabela public.NOMED.')
    if not layout.get('generate_legacy_id') or layout.get('generate_integer_id'):
        return _repository(layout).create(item)
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock(hashtext(%s))',
                (f"public.{layout['table']}",),
            )
            record_id = _next_professional_id(cursor, layout)
            values = dict(item)
            values[layout['id_column']] = record_id
            values[layout['tenant_column']] = current_company_id()
            columns = list(values)
            statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}').format(
                sql.Identifier('public'),
                sql.Identifier(layout['table']),
                sql.SQL(', ').join(map(sql.Identifier, columns)),
                sql.SQL(', ').join(sql.Placeholder() for _ in columns),
                sql.Identifier(layout['id_column']),
            )
            cursor.execute(statement, [values[column] for column in columns])
            return cursor.fetchone()[0]


def _update_professional_without_id_by_name(layout, item):
    tenant_column = layout.get('tenant_column')
    name_column = layout['fields'].get('nome')
    if not tenant_column or not name_column:
        return False
    name = (item.get(name_column) or '').strip()
    if not name:
        return None
    values = dict(item)
    generated_id = None
    with _connection() as connection:
        with connection.cursor() as cursor:
            if layout.get('generate_legacy_id'):
                cursor.execute(
                    'SELECT pg_advisory_xact_lock(hashtext(%s))',
                    (f"public.{layout['table']}",),
                )
                generated_id = _next_professional_id(cursor, layout)
                values[layout['id_column']] = generated_id
            columns = list(values)
            assignments = sql.SQL(', ').join(
                sql.SQL('{} = %s').format(sql.Identifier(column))
                for column in columns
            )
            statement = sql.SQL('''
                UPDATE {}.{}
                SET {}
                WHERE UPPER(BTRIM({})) = UPPER(BTRIM(%s))
                  AND {} = %s
                  AND {} IS NULL
            ''').format(
                sql.Identifier('public'),
                sql.Identifier(layout['table']),
                assignments,
                sql.Identifier(name_column),
                sql.Identifier(tenant_column),
                sql.Identifier(layout['id_column']),
            )
            parameters = [values[column] for column in columns] + [name, current_company_id()]
            cursor.execute(statement, parameters)
            if cursor.rowcount == 0:
                return None
            return generated_id if generated_id is not None else name


def _next_professional_id(cursor, layout):
    id_metadata = layout.get('id_metadata') or {}
    data_type = (id_metadata.get('data_type') or '').lower()
    id_column = layout['id_column']
    if any(kind in data_type for kind in ('integer', 'bigint', 'smallint')):
        cursor.execute(sql.SQL('SELECT COALESCE(MAX({}), 0) + 1 FROM {}.{}').format(
            sql.Identifier(id_column),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        ))
        return cursor.fetchone()[0]
    cursor.execute(sql.SQL("""
        SELECT COALESCE(MAX(CAST(BTRIM({}) AS INTEGER)), 0) + 1
        FROM {}.{}
        WHERE BTRIM(COALESCE({}, '')) ~ '^[0-9]+$'
    """).format(
        sql.Identifier(id_column),
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.Identifier(id_column),
    ))
    next_id = str(cursor.fetchone()[0])
    max_length = id_metadata.get('max_length')
    if max_length and len(next_id) > max_length:
        raise ValueError('Limite de codigos de profissionais atingido.')
    return next_id


def _prof_data(data, layout):
    nome = (data.get('nome') or '').strip()
    if not nome:
        raise ValueError('Informe o nome do profissional.')

    values = {}
    for logical_name, column_name in layout['fields'].items():
        value = (data.get(logical_name) or '').strip()
        metadata = layout.get('field_metadata', {}).get(logical_name, {})
        if value and logical_name in MAX_LENGTHS and len(value) > MAX_LENGTHS[logical_name]:
            raise ValueError(f'O campo {logical_name} excede {MAX_LENGTHS[logical_name]} caracteres.')
        if logical_name.endswith('_inicio') or logical_name.endswith('_termino'):
            values[column_name] = _format_schedule_value(value, metadata)
            continue
        values[column_name] = None if value == '' else value
    for day in SCHEDULE_DAYS:
        active_column = layout['fields'].get(f'{day}_ativo')
        if not active_column:
            continue
        metadata = layout.get('field_metadata', {}).get(f'{day}_ativo', {})
        has_schedule = bool((data.get(f'{day}_inicio') or '').strip() and (data.get(f'{day}_termino') or '').strip())
        values[active_column] = _active_schedule_value(has_schedule, metadata)
    values[layout['fields']['nome']] = nome
    return values


def _format_schedule_value(value, metadata):
    value = (value or '').strip()
    if not value:
        return None
    max_length = (metadata or {}).get('max_length')
    if max_length and max_length <= 4:
        return value.replace(':', '')[:max_length]
    return value


def _active_schedule_value(has_schedule, metadata):
    if not has_schedule:
        return None
    data_type = ((metadata or {}).get('data_type') or '').lower()
    max_length = (metadata or {}).get('max_length')
    if 'bool' in data_type:
        return True
    if any(kind in data_type for kind in ('integer', 'bigint', 'smallint', 'numeric')):
        return 1
    if max_length == 1:
        return 'S'
    return 'S'


def _select_expression(layout, logical_name):
    column_name = layout['fields'].get(logical_name)
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _clean_value(value):
    if isinstance(value, str):
        return value.strip()
    return value


def _row_dict(field_names, row):
    return {
        field_name: _clean_value(value)
        for field_name, value in zip(field_names, row)
    }


def _error_response(exc):
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({'success': False, 'message': 'Ja existe um profissional com este codigo.'}), 409
    if isinstance(exc, errors.StringDataRightTruncation):
        return jsonify({'success': False, 'message': 'Um dos campos ultrapassa o tamanho permitido.'}), 400
    current_app.logger.exception('Falha na operacao do profissional de saude', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@prof_saude_api_bp.route('/api/prof-saude', methods=['POST'])
def list_profissionais():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        layout = _layout()
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
        ] + [_select_expression(layout, field) for field in FIELD_CANDIDATES]

        statement = sql.SQL('SELECT {} FROM {}.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        if not layout['tenant_column']:
            raise ValueError('Campo CODCLIN não encontrado na tabela public.NOMED.')
        conditions = [sql.SQL('{} = %s').format(sql.Identifier(layout['tenant_column']))]
        parameters = [current_company_id()]
        if term:
            conditions.append(sql.SQL('(CAST({} AS TEXT) ILIKE %s OR {} ILIKE %s)').format(
                sql.Identifier(layout['id_column']),
                sql.Identifier(layout['fields']['nome']),
            ))
            parameters.extend([f'%{term}%', f'%{term}%'])
        statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
        statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(layout['fields']['nome']))

        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        field_names = ['id'] + list(FIELD_CANDIDATES)
        profissionais = [_row_dict(field_names, row) for row in rows]
        with _connection() as connection:
            with connection.cursor() as cursor:
                _load_prefere_for_ids(cursor, profissionais)
                _load_texto_for_ids(cursor, profissionais)
        return jsonify({
            'success': True,
            'profissionais': profissionais,
        })
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/prof-saude/itens', methods=['POST'])
def create_profissional():
    try:
        layout = _layout()
        data = request.get_json(silent=True) or {}
        item = _prof_data(data, layout)
        with _connection() as connection:
            with connection.cursor() as cursor:
                record_id = _insert_profissional(cursor, layout, item)
                saved_prefere = _upsert_prefere(cursor, record_id, data)
                _upsert_texto(cursor, record_id, data)
        return jsonify({
            'success': True,
            'message': 'Profissional incluido com sucesso.',
            'id': record_id,
            'prefere': saved_prefere,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/prof-saude/itens/<record_id>', methods=['PUT'])
def update_profissional(record_id):
    try:
        layout = _layout()
        data = request.get_json(silent=True) or {}
        item = _prof_data(data, layout)
        actual_id = _update_profissional(layout, record_id, item)
        if actual_id is None:
            return jsonify({'success': False, 'message': 'Profissional nao encontrado.'}), 404
        with _connection() as connection:
            with connection.cursor() as cursor:
                saved_prefere = _upsert_prefere(cursor, actual_id, data)
                _upsert_texto(cursor, actual_id, data)
        return jsonify({
            'success': True,
            'message': 'Profissional alterado com sucesso.',
            'prefere': saved_prefere,
        })
    except Exception as exc:
        return _error_response(exc)



def _anamnese_values(data):
    nome = (data.get('nome') or data.get('anamnese_nome') or '').strip()
    texto = (data.get('texto') or data.get('anamnese_texto') or '').strip()
    atalho = (data.get('atalho') or data.get('tipo') or '').strip().upper()
    if not nome:
        raise ValueError('Informe o nome do padrão.')
    if len(nome) > 30:
        raise ValueError('O campo Nome do padrão excede 30 caracteres.')
    if atalho not in ('R', 'X', 'P', 'A', 'E', 'Z'):
        raise ValueError('Selecione o tipo do padrão: Rec, Ex, Pr, An, Me ou Mz.')
    message_html = str(data.get('msghtml') or '').strip().lower() in (
        '1', 'true', 't', 'sim', 's', 'on'
    )
    if atalho == 'E' and message_html and texto:
        unsafe_patterns = (
            r'<\s*(?:script|iframe|object|embed|form)\b',
            r'\bon[a-z]+\s*=',
            r'javascript\s*:',
        )
        if any(re.search(pattern, texto, re.I) for pattern in unsafe_patterns):
            raise ValueError('O HTML do e-mail contém conteúdo não permitido.')
    return nome, texto, atalho


@prof_saude_api_bp.route('/api/anamnese', methods=['POST'])
def list_anamneses():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        tipo = (data.get('tipo') or data.get('atalho') or '').strip().upper()
        if tipo and tipo not in ('R', 'X', 'P', 'A', 'E', 'Z'):
            raise ValueError('Tipo de padrão inválido.')
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _texto_layout(cursor)
                if not layout:
                    return jsonify({'success': True, 'anamneses': []})
                id_col = layout['id_column']
                texto_col = layout['fields']['texto']
                tenant_col = layout.get('tenant_column')
                if not tenant_col:
                    raise ValueError('Campo CODCLIN não encontrado na tabela public.TEXTO.')
                atalho_col = layout['fields'].get('atalho')
                atalho_select = (
                    sql.SQL('{} AS atalho').format(sql.Identifier(atalho_col))
                    if atalho_col else sql.SQL("'A' AS atalho")
                )
                html_col = layout['fields'].get('msghtml')
                html_select = (
                    sql.SQL('COALESCE({}, FALSE) AS msghtml').format(sql.Identifier(html_col))
                    if html_col else sql.SQL('FALSE AS msghtml')
                )
                statement = sql.SQL('SELECT {} AS id, {} AS nome, {} AS texto, {}, {} FROM {}.{}').format(
                    sql.Identifier(id_col),
                    sql.Identifier(id_col),
                    sql.Identifier(texto_col),
                    atalho_select,
                    html_select,
                    sql.Identifier('public'),
                    sql.Identifier(layout['table']),
                )
                conditions = [sql.SQL('{} = %s').format(sql.Identifier(tenant_col))]
                parameters = [current_company_id()]
                if term:
                    conditions.append(sql.SQL('({} ILIKE %s OR {} ILIKE %s)').format(
                        sql.Identifier(id_col), sql.Identifier(texto_col)
                    ))
                    parameters.extend([f'%{term}%', f'%{term}%'])
                if tipo and atalho_col:
                    if tipo == 'A':
                        conditions.append(sql.SQL("({} = %s OR {} IS NULL OR BTRIM({}) = '')").format(
                            sql.Identifier(atalho_col),
                            sql.Identifier(atalho_col),
                            sql.Identifier(atalho_col),
                        ))
                    else:
                        conditions.append(sql.SQL('{} = %s').format(sql.Identifier(atalho_col)))
                    parameters.append(tipo)
                if conditions:
                    statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
                statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(id_col))
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        return jsonify({
            'success': True,
            'anamneses': [_row_dict(['id', 'nome', 'texto', 'atalho', 'msghtml'], row) for row in rows],
        })
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/anamnese/opcoes', methods=['POST'])
def list_all_anamnese_options():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _texto_layout(cursor)
                if not layout:
                    return jsonify({'success': True, 'anamneses': []})
                id_col = layout['id_column']
                texto_col = layout['fields']['texto']
                tenant_col = layout.get('tenant_column')
                if not tenant_col:
                    raise ValueError('Campo CODCLIN nao encontrado na tabela public.TEXTO.')
                atalho_col = layout['fields'].get('atalho')
                html_col = layout['fields'].get('msghtml')
                atalho_select = (
                    sql.SQL('{} AS atalho').format(sql.Identifier(atalho_col))
                    if atalho_col else sql.SQL("'A' AS atalho")
                )
                html_select = (
                    sql.SQL('COALESCE({}, FALSE) AS msghtml').format(sql.Identifier(html_col))
                    if html_col else sql.SQL('FALSE AS msghtml')
                )
                statement = sql.SQL(
                    'SELECT {} AS id, {} AS nome, {} AS texto, {}, {}, {} AS empresa_id FROM public.{}'
                ).format(
                    sql.Identifier(id_col), sql.Identifier(id_col), sql.Identifier(texto_col),
                    atalho_select, html_select, sql.Identifier(tenant_col), sql.Identifier(layout['table'])
                )
                parameters = []
                if term:
                    statement += sql.SQL(' WHERE ({} ILIKE %s OR {} ILIKE %s)').format(
                        sql.Identifier(id_col), sql.Identifier(texto_col)
                    )
                    parameters.extend([f'%{term}%', f'%{term}%'])
                statement += sql.SQL(' ORDER BY {}, {} LIMIT 500').format(
                    sql.Identifier(id_col), sql.Identifier(tenant_col)
                )
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()
        items = [_row_dict(['id', 'nome', 'texto', 'atalho', 'msghtml', 'empresa_id'], row) for row in rows]
        for item in items:
            item['_option_key'] = str(item['id']) + ':' + str(item['empresa_id'])
        return jsonify({'success': True, 'anamneses': items})
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/anamnese/itens', methods=['POST'])
def create_anamnese():
    try:
        data = request.get_json(silent=True) or {}
        nome, texto, atalho = _anamnese_values(data)
        message_html = str(data.get('msghtml') or '').strip().lower() in (
            '1', 'true', 't', 'sim', 's', 'on'
        )
        message_html = atalho == 'E' and message_html
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _texto_layout(cursor)
                if not layout:
                    raise ValueError('Tabela public.TEXTO nao encontrada no banco.')
                id_col = layout['id_column']
                texto_col = layout['fields']['texto']
                tenant_col = layout.get('tenant_column')
                if not tenant_col:
                    raise ValueError('Campo CODCLIN não encontrado na tabela public.TEXTO.')
                atalho_col = layout['fields'].get('atalho')
                if not atalho_col:
                    raise ValueError('Campo ATALHO não encontrado na tabela public.TEXTO.')
                cursor.execute(
                    sql.SQL('SELECT 1 FROM {}.{} WHERE {} = %s AND {} = %s LIMIT 1').format(
                        sql.Identifier('public'), sql.Identifier(layout['table']), sql.Identifier(id_col),
                        sql.Identifier(tenant_col),
                    ),
                    (nome, current_company_id())
                )
                if cursor.fetchone() is not None:
                    raise ValueError('Já existe um padrão com este nome.')
                columns = [id_col, texto_col, atalho_col, tenant_col]
                values = [nome, None if texto == '' else texto, atalho, current_company_id()]
                html_col = layout['fields'].get('msghtml')
                if html_col:
                    columns.append(html_col)
                    values.append(message_html)
                codigo_col = layout.get('codigo_column')
                if codigo_col and codigo_col not in columns:
                    cursor.execute(
                        'SELECT pg_advisory_xact_lock(hashtext(%s))',
                        ('public.texto.codigo',),
                    )
                    cursor.execute(
                        sql.SQL('SELECT COALESCE(MAX({}), 0) + 1 FROM public.texto').format(
                            sql.Identifier(codigo_col)
                        )
                    )
                    columns.append(codigo_col)
                    values.append(cursor.fetchone()[0])
                cursor.execute(
                    sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(
                        sql.Identifier('public'),
                        sql.Identifier(layout['table']),
                        sql.SQL(', ').join(map(sql.Identifier, columns)),
                        sql.SQL(', ').join(sql.Placeholder() for _ in columns),
                    ),
                    values,
                )
        return jsonify({'success': True, 'message': 'Padrão incluído com sucesso.', 'id': nome}), 201
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/anamnese/itens/<path:record_id>', methods=['PUT'])
def update_anamnese(record_id):
    try:
        data = request.get_json(silent=True) or {}
        nome, texto, atalho = _anamnese_values(data)
        message_html = str(data.get('msghtml') or '').strip().lower() in (
            '1', 'true', 't', 'sim', 's', 'on'
        )
        message_html = atalho == 'E' and message_html
        old_id = str(record_id).strip()
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _texto_layout(cursor)
                if not layout:
                    raise ValueError('Tabela public.TEXTO nao encontrada no banco.')
                id_col = layout['id_column']
                texto_col = layout['fields']['texto']
                tenant_col = layout.get('tenant_column')
                if not tenant_col:
                    raise ValueError('Campo CODCLIN não encontrado na tabela public.TEXTO.')
                atalho_col = layout['fields'].get('atalho')
                if not atalho_col:
                    raise ValueError('Campo ATALHO não encontrado na tabela public.TEXTO.')
                if nome != old_id:
                    cursor.execute(
                        sql.SQL('SELECT 1 FROM {}.{} WHERE {} = %s AND {} = %s LIMIT 1').format(
                            sql.Identifier('public'), sql.Identifier(layout['table']), sql.Identifier(id_col),
                            sql.Identifier(tenant_col),
                        ),
                        (nome, current_company_id())
                    )
                    if cursor.fetchone() is not None:
                        raise ValueError('Já existe um padrão com este nome.')
                update_columns = [id_col, texto_col, atalho_col]
                update_values = [nome, None if texto == '' else texto, atalho]
                html_col = layout['fields'].get('msghtml')
                if html_col:
                    update_columns.append(html_col)
                    update_values.append(message_html)
                assignments = sql.SQL(', ').join(
                    sql.SQL('{} = %s').format(sql.Identifier(column))
                    for column in update_columns
                )
                cursor.execute(
                    sql.SQL('UPDATE {}.{} SET {} WHERE {} = %s AND {} = %s').format(
                        sql.Identifier('public'),
                        sql.Identifier(layout['table']),
                        assignments,
                        sql.Identifier(id_col),
                        sql.Identifier(tenant_col),
                    ),
                    update_values + [old_id, current_company_id()],
                )
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Padrão não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Padrão alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/anamnese/itens/<path:record_id>', methods=['DELETE'])
def delete_anamnese(record_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                layout = _texto_layout(cursor)
                if not layout:
                    raise ValueError('Tabela public.TEXTO nao encontrada no banco.')
                id_col = layout['id_column']
                tenant_col = layout.get('tenant_column')
                if not tenant_col:
                    raise ValueError('Campo CODCLIN não encontrado na tabela public.TEXTO.')
                cursor.execute(
                    sql.SQL('DELETE FROM {}.{} WHERE {} = %s AND {} = %s').format(
                        sql.Identifier('public'), sql.Identifier(layout['table']), sql.Identifier(id_col),
                        sql.Identifier(tenant_col),
                    ),
                    (str(record_id).strip(), current_company_id())
                )
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': 'Padrão não encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Padrão excluído com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@prof_saude_api_bp.route('/api/prof-saude/itens/<record_id>', methods=['DELETE'])
def delete_profissional(record_id):
    try:
        deleted = _repository(_layout()).delete(record_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Profissional nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Profissional excluido com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
