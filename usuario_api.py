from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, session
from psycopg2 import errors, sql

from crud_repository import CrudRepository
from medsoft_core import DBConnectionError, get_db_connection
from tenant_context import TENANT_COLUMN, current_company_id

usuario_api_bp = Blueprint('usuario_api', __name__)

TABLE_CANDIDATES = ('senha',)
ID_CANDIDATES = ('nome',)
FIELD_CANDIDATES = {
    'nome': ('nome',),
    'senha': ('senha',),
    'direitos': ('direitos',),
    'codmed': ('codmed',),
    'codclin': ('codclin',),
    'perfil': ('perfil',),
    'datahoracontato': ('datahoracontato', 'data_hora_contato'),
}

MAX_LENGTHS = {
    'nome': 40,
    'senha': 40,
    'direitos': 30,
    'perfil': 30,
}

INTEGER_FIELDS = {'codmed', 'codclin'}


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
        SELECT table_name, column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = %s
        ORDER BY ordinal_position
    """, (table_name,))
    rows = cursor.fetchall()
    actual_table = rows[0][0] if rows else None
    columns = {
        row[1].lower(): {
            'name': row[1],
            'data_type': row[2] or '',
            'default': row[3],
        }
        for row in rows
    }
    return actual_table, columns


def _pick(columns, candidates):
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def _general_users_available(cursor):
    cursor.execute("SELECT to_regclass('public.ic_usuario_geral')")
    return cursor.fetchone()[0] is not None


def _ensure_general_user_columns(cursor):
    return None


def _general_user_column_exists(cursor, column_name):
    cursor.execute('''
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'ic_usuario_geral'
              AND column_name = %s
        )
    ''', (column_name,))
    return bool(cursor.fetchone()[0])


def _professional_id_column(cursor):
    cursor.execute('''
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'nomed'
          AND lower(column_name) IN ('codmed', 'cod', 'codigo', 'id')
        ORDER BY CASE lower(column_name)
            WHEN 'codmed' THEN 1 WHEN 'cod' THEN 2 WHEN 'codigo' THEN 3 ELSE 4 END
        LIMIT 1
    ''')
    row = cursor.fetchone()
    return row[0] if row else None


def _profile_table_available(cursor):
    cursor.execute("SELECT to_regclass('public.ic_perfil_geral')")
    return cursor.fetchone()[0] is not None


def _next_general_user_id(cursor):
    cursor.execute(
        'SELECT pg_advisory_xact_lock(hashtext(%s))',
        ('public.ic_usuario_geral',),
    )
    cursor.execute('SELECT COALESCE(MAX(idusuario), 0) + 1 FROM public.ic_usuario_geral')
    return cursor.fetchone()[0]


def _validate_company_user_limit(cursor, company_id):
    """Impede inclusoes acima da quantidade de usuarios contratada pela empresa."""
    try:
        company_id = int(company_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('Informe uma empresa valida.') from exc

    # Serializa inclusoes da mesma empresa para duas requisicoes simultaneas
    # nao ultrapassarem o limite do plano.
    cursor.execute(
        'SELECT pg_advisory_xact_lock(hashtext(%s))',
        (f'limite-usuarios-empresa-{company_id}',),
    )
    cursor.execute('''
        SELECT plano.qtdusuarios, COUNT(usuario.idusuario)
        FROM public.ic_empresa_geral empresa
        LEFT JOIN public.ic_plano_geral plano ON plano.idplano = empresa.idplano
        LEFT JOIN public.ic_usuario_geral usuario ON usuario.idempresa = empresa.idempresa
        WHERE empresa.idempresa = %s
        GROUP BY plano.qtdusuarios
    ''', (company_id,))
    row = cursor.fetchone()
    if not row or row[0] in (None, ''):
        return
    try:
        maximum_users = int(row[0])
    except (TypeError, ValueError):
        maximum_users = 0
    if maximum_users <= 0:
        return
    current_users = int(row[1] or 0)
    if current_users >= maximum_users:
        raise ValueError(
            'O plano da empresa permite no maximo {} usuario(s). '
            'Exclua um usuario ou altere o plano para realizar uma nova inclusao.'.format(
                maximum_users
            )
        )


def _profile_id(cursor, value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    if not _profile_table_available(cursor):
        return None
    cursor.execute('''
        SELECT idperfil
        FROM public.ic_perfil_geral
        WHERE lower(nome) = lower(%s) OR lower(descricao) = lower(%s)
        LIMIT 1
    ''', (value, value))
    row = cursor.fetchone()
    return row[0] if row else None


def _is_master_profile(value):
    return (value or '').strip().upper() == 'MASTER'


def _current_user_is_master(cursor):
    if _is_master_profile(session.get('perfil')):
        return True
    user_id = session.get('idusuario')
    if not user_id or not _general_users_available(cursor) or not _profile_table_available(cursor):
        return False
    cursor.execute('''
        SELECT COALESCE(perfil.nome, perfil.descricao, '')
        FROM public.ic_usuario_geral usuario
        LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = usuario.idperfil
        WHERE usuario.idusuario = %s
        LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    return _is_master_profile(row[0] if row else '')


def _current_user_has_global_scope(cursor):
    return _current_user_is_master(cursor)


def _validate_master_profile_permission(data, is_current_user_master):
    if _is_master_profile(data.get('perfil')) and not is_current_user_master:
        raise PermissionError('Apenas usuarios com perfil MASTER podem criar ou alterar usuario MASTER.')


def _record_is_master_user(cursor, record_id):
    if not _profile_table_available(cursor):
        return False
    cursor.execute('''
        SELECT COALESCE(perfil.nome, perfil.descricao, '')
        FROM public.ic_usuario_geral usuario
        LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = usuario.idperfil
        WHERE usuario.idusuario = %s
        LIMIT 1
    ''', (record_id,))
    row = cursor.fetchone()
    return _is_master_profile(row[0] if row else '')


def _general_user_values(data, cursor, allow_company_choice=False):
    nome = (data.get('nome') or '').strip()
    senha = (data.get('senha') or '').strip()
    requested_company = data.get('idempresa') or data.get('codclin')
    codclin = requested_company if allow_company_choice and requested_company else current_company_id()
    if not nome:
        raise ValueError('Informe o nome do usuario.')
    if not senha:
        raise ValueError('Informe a senha.')
    try:
        codclin = int(codclin)
    except (TypeError, ValueError) as exc:
        raise ValueError('Informe uma empresa valida.') from exc
    if len(nome) > 100:
        raise ValueError('O nome do usuario deve ter no maximo 100 caracteres.')
    if len(senha) > 50:
        raise ValueError('A senha deve ter no maximo 50 caracteres.')
    return {
        'nome': nome,
        'login': nome,
        'senha': senha,
        'ativo': True,
        'idperfil': _profile_id(cursor, data.get('perfil')),
        'idempresa': codclin,
        'idcodmed': _clean_integer(str(data.get('idcodmed') or data.get('idprefere') or data.get('codmed') or ''), 'Prof. Saúde'),
    }


def _list_general_usuarios(cursor, term, include_all_companies=False):
    has_idcodmed = _general_user_column_exists(cursor, 'idcodmed')
    has_idprefere = _general_user_column_exists(cursor, 'idprefere')
    has_codmed = _general_user_column_exists(cursor, 'codmed')
    has_profile = _profile_table_available(cursor)
    profile_select = (
        'COALESCE(perfil.nome, perfil.descricao, geral.idperfil::text, \'\')'
        if has_profile else
        'COALESCE(geral.idperfil::text, \'\')'
    )
    join_profile = (
        ' LEFT JOIN public.ic_perfil_geral perfil ON perfil.idperfil = geral.idperfil '
        if has_profile else ' '
    )
    professional_value = (
        'geral.idcodmed' if has_idcodmed else
        ('geral.idprefere' if has_idprefere else ('geral.codmed' if has_codmed else None))
    )
    professional_id_column = _professional_id_column(cursor) if professional_value else None
    codmed_select = f"COALESCE(CAST({professional_value} AS TEXT), '')" if professional_value else "''"
    codmed_nome_select = "COALESCE(prof.nomed, '')" if professional_value and professional_id_column else "''"
    codmed_join = '''
        LEFT JOIN public.nomed prof
          ON CAST(prof.{professional_id_column} AS TEXT) = CAST({professional_value} AS TEXT)
         AND prof.codclin = geral.idempresa
    '''.format(
        professional_id_column=professional_id_column,
        professional_value=professional_value,
    ) if professional_value and professional_id_column else ''
    query = '''
        SELECT geral.idusuario AS id,
               geral.nome,
               geral.senha,
               '' AS direitos,
               {codmed_select} AS codmed,
               {codmed_select} AS idprefere,
               {codmed_select} AS idcodmed,
               geral.idempresa AS codclin,
               geral.idempresa AS idempresa,
               {profile_select} AS perfil,
               NULL AS datahoracontato,
               {codmed_nome_select} AS codmed_nome,
               COALESCE(empresa.nome, '') AS codclin_nome,
               COALESCE(empresa.nome, '') AS empresa_nome
        FROM public.ic_usuario_geral geral
        {join_profile}
        {codmed_join}
        LEFT JOIN public.ic_empresa_geral empresa
          ON empresa.idempresa = geral.idempresa
    '''.format(
        codmed_select=codmed_select,
        codmed_nome_select=codmed_nome_select,
        profile_select=profile_select,
        join_profile=join_profile,
        codmed_join=codmed_join,
    )
    conditions = []
    parameters = []
    if not include_all_companies:
        conditions.append('geral.idempresa = %s')
        parameters.append(current_company_id())
    if term:
        conditions.append('(geral.nome ILIKE %s OR geral.login ILIKE %s OR ' + profile_select + ' ILIKE %s)')
        parameters.extend([f'%{term}%', f'%{term}%', f'%{term}%'])
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY geral.nome LIMIT 100'
    cursor.execute(query, parameters)
    rows = cursor.fetchall()
    field_names = [
        'id', 'nome', 'senha', 'direitos', 'codmed', 'idprefere', 'idcodmed', 'codclin', 'idempresa',
        'perfil', 'datahoracontato', 'codmed_nome', 'codclin_nome', 'empresa_nome',
    ]
    return [dict(zip(field_names, row)) for row in rows]


def _detect_layout(cursor):
    for table_candidate in TABLE_CANDIDATES:
        table_name, columns = _fetch_table_columns(cursor, table_candidate)
        if not columns:
            continue
        id_column = _pick(columns, ID_CANDIDATES)
        if not id_column:
            continue
        fields = {}
        for logical_name, candidates in FIELD_CANDIDATES.items():
            column = _pick(columns, candidates)
            if column:
                fields[logical_name] = column['name']
        if 'nome' not in fields:
            continue
        return {
            'table': table_name or table_candidate,
            'id_column': id_column['name'],
            'fields': fields,
            'generate_integer_id': False,
        }
    raise ValueError('Tabela public.SENHA nao encontrada no banco.')


def _layout():
    with _connection() as connection:
        with connection.cursor() as cursor:
            return _detect_layout(cursor)


def _legacy_record_is_master(cursor, layout, record_id):
    profile_column = layout['fields'].get('perfil')
    if not profile_column:
        return False
    cursor.execute(sql.SQL('SELECT {} FROM {}.{} WHERE {} = %s LIMIT 1').format(
        sql.Identifier(profile_column),
        sql.Identifier('public'),
        sql.Identifier(layout['table']),
        sql.Identifier(layout['id_column']),
    ), (record_id,))
    row = cursor.fetchone()
    return _is_master_profile(row[0] if row else '')


def _repository(layout):
    tenant_column = layout['fields'].get(TENANT_COLUMN)
    if not tenant_column:
        raise ValueError('Campo CODCLIN não encontrado na tabela public.SENHA.')
    return CrudRepository(
        connection_factory=_connection,
        table=layout['table'],
        id_column=layout['id_column'],
        writable_columns=tuple(layout['fields'].values()),
        generate_integer_id=layout['generate_integer_id'],
        tenant_column=tenant_column,
        tenant_value_factory=current_company_id,
    )


def _clean_integer(value, label):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f'O campo {label} deve ser numerico.')


def _usuario_data(data, layout):
    nome = (data.get('nome') or '').strip()
    senha = (data.get('senha') or '').strip()
    if not nome:
        raise ValueError('Informe o nome do usuario.')
    if not senha:
        raise ValueError('Informe a senha.')

    values = {}
    for logical_name, column_name in layout['fields'].items():
        if logical_name == TENANT_COLUMN:
            continue
        if logical_name in INTEGER_FIELDS:
            values[column_name] = _clean_integer(data.get(logical_name), logical_name)
            continue
        value = (data.get(logical_name) or '').strip()
        if value and logical_name in MAX_LENGTHS and len(value) > MAX_LENGTHS[logical_name]:
            raise ValueError(f'O campo {logical_name} excede {MAX_LENGTHS[logical_name]} caracteres.')
        values[column_name] = None if value == '' else value
    values[layout['fields']['nome']] = nome
    values[layout['fields']['senha']] = senha
    return values


def _select_expression(layout, logical_name):
    column_name = layout['fields'].get(logical_name)
    if not column_name:
        return sql.SQL("'' AS {}").format(sql.Identifier(logical_name))
    return sql.SQL('{} AS {}').format(sql.Identifier(column_name), sql.Identifier(logical_name))


def _error_response(exc):
    if isinstance(exc, PermissionError):
        return jsonify({'success': False, 'message': str(exc)}), 403
    if isinstance(exc, ValueError):
        return jsonify({'success': False, 'message': str(exc)}), 400
    if isinstance(exc, DBConnectionError):
        return jsonify({'success': False, 'message': str(exc)}), 503
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({'success': False, 'message': 'Ja existe um usuario com este nome.'}), 409
    if isinstance(exc, errors.StringDataRightTruncation):
        return jsonify({'success': False, 'message': 'Um dos campos ultrapassa o tamanho permitido.'}), 400
    current_app.logger.exception('Falha na operacao do usuario', exc_info=exc)
    return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500


@usuario_api_bp.route('/api/usuarios', methods=['POST'])
def list_usuarios():
    try:
        data = request.get_json(silent=True) or {}
        term = (data.get('termo') or '').strip()
        with _connection() as connection:
            with connection.cursor() as cursor:
                if _general_users_available(cursor):
                    usuario_master = _current_user_is_master(cursor)
                    include_all_companies = _current_user_has_global_scope(cursor)
                    return jsonify({
                        'success': True,
                        'usuarios': _list_general_usuarios(cursor, term, include_all_companies),
                        'usuario_master': usuario_master,
                    })
        layout = _layout()
        select_items = [
            sql.SQL('{} AS id').format(sql.Identifier(layout['id_column'])),
        ] + [_select_expression(layout, field) for field in FIELD_CANDIDATES]

        statement = sql.SQL('SELECT {} FROM {}.{}').format(
            sql.SQL(', ').join(select_items),
            sql.Identifier('public'),
            sql.Identifier(layout['table']),
        )
        tenant_column = layout['fields'].get(TENANT_COLUMN)
        if not tenant_column:
            raise ValueError('Campo CODCLIN não encontrado na tabela public.SENHA.')
        conditions = [sql.SQL('{} = %s').format(sql.Identifier(tenant_column))]
        parameters = [current_company_id()]
        if term:
            conditions.append(sql.SQL('({} ILIKE %s OR COALESCE({}, %s) ILIKE %s)').format(
                sql.Identifier(layout['fields']['nome']),
                sql.Identifier(layout['fields'].get('perfil', layout['fields']['nome'])),
                sql.Placeholder(),
            ))
            parameters.extend([f'%{term}%', '', f'%{term}%'])
        statement += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
        statement += sql.SQL(' ORDER BY {} LIMIT 100').format(sql.Identifier(layout['fields']['nome']))

        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                rows = cursor.fetchall()

        field_names = ['id'] + list(FIELD_CANDIDATES)
        return jsonify({
            'success': True,
            'usuarios': [dict(zip(field_names, row)) for row in rows],
            'usuario_master': _is_master_profile(session.get('perfil')),
        })
    except Exception as exc:
        return _error_response(exc)


@usuario_api_bp.route('/api/usuarios/permissao', methods=['POST'])
def usuario_permission():
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                return jsonify({'success': True, 'usuario_master': _current_user_is_master(cursor)})
    except Exception as exc:
        return _error_response(exc)


@usuario_api_bp.route('/api/usuarios/itens', methods=['POST'])
def create_usuario():
    try:
        data = request.get_json(silent=True) or {}
        with _connection() as connection:
            with connection.cursor() as cursor:
                if _general_users_available(cursor):
                    is_current_user_master = _current_user_is_master(cursor)
                    has_global_scope = _current_user_has_global_scope(cursor)
                    _validate_master_profile_permission(data, is_current_user_master)
                    has_idcodmed = _general_user_column_exists(cursor, 'idcodmed')
                    has_idprefere = _general_user_column_exists(cursor, 'idprefere')
                    has_codmed = _general_user_column_exists(cursor, 'codmed')
                    item = _general_user_values(data, cursor, allow_company_choice=has_global_scope)
                    _validate_company_user_limit(cursor, item['idempresa'])
                    item['idusuario'] = _next_general_user_id(cursor)
                    if has_idcodmed:
                        cursor.execute('''
                            INSERT INTO public.ic_usuario_geral
                                (idusuario, nome, login, senha, ativo, idperfil, idempresa, idcodmed)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING idusuario
                        ''', (
                            item['idusuario'], item['nome'], item['login'], item['senha'],
                            item['ativo'], item['idperfil'], item['idempresa'], item['idcodmed'],
                        ))
                    elif has_idprefere:
                        cursor.execute('''
                            INSERT INTO public.ic_usuario_geral
                                (idusuario, nome, login, senha, ativo, idperfil, idempresa, idprefere)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING idusuario
                        ''', (
                            item['idusuario'], item['nome'], item['login'], item['senha'],
                            item['ativo'], item['idperfil'], item['idempresa'], item['idcodmed'],
                        ))
                    elif has_codmed:
                        cursor.execute('''
                            INSERT INTO public.ic_usuario_geral
                                (idusuario, nome, login, senha, ativo, idperfil, idempresa, codmed)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING idusuario
                        ''', (
                            item['idusuario'], item['nome'], item['login'], item['senha'],
                            item['ativo'], item['idperfil'], item['idempresa'], item['idcodmed'],
                        ))
                    else:
                        cursor.execute('''
                            INSERT INTO public.ic_usuario_geral
                                (idusuario, nome, login, senha, ativo, idperfil, idempresa)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING idusuario
                        ''', (
                            item['idusuario'], item['nome'], item['login'], item['senha'],
                            item['ativo'], item['idperfil'], item['idempresa'],
                        ))
                    record_id = cursor.fetchone()[0]
                    return jsonify({
                        'success': True,
                        'message': 'Usuario incluido com sucesso.',
                        'id': record_id,
                    }), 201
        layout = _layout()
        with _connection() as connection:
            with connection.cursor() as cursor:
                is_current_user_master = _current_user_is_master(cursor)
                _validate_master_profile_permission(data, is_current_user_master)
        item = _usuario_data(data, layout)
        record_id = _repository(layout).create(item)
        return jsonify({
            'success': True,
            'message': 'Usuario incluido com sucesso.',
            'id': record_id,
        }), 201
    except Exception as exc:
        return _error_response(exc)


@usuario_api_bp.route('/api/usuarios/itens/<record_id>', methods=['PUT'])
def update_usuario(record_id):
    try:
        data = request.get_json(silent=True) or {}
        with _connection() as connection:
            with connection.cursor() as cursor:
                if _general_users_available(cursor):
                    is_current_user_master = _current_user_is_master(cursor)
                    has_global_scope = _current_user_has_global_scope(cursor)
                    if not is_current_user_master and _record_is_master_user(cursor, record_id):
                        raise PermissionError('Apenas usuários com perfil MASTER podem alterar usuário MASTER.')
                    _validate_master_profile_permission(data, is_current_user_master)
                    has_idcodmed = _general_user_column_exists(cursor, 'idcodmed')
                    has_idprefere = _general_user_column_exists(cursor, 'idprefere')
                    has_codmed = _general_user_column_exists(cursor, 'codmed')
                    item = _general_user_values(data, cursor, allow_company_choice=has_global_scope)
                    where_clause = 'WHERE idusuario = %s'
                    where_parameters = [record_id]
                    if not has_global_scope:
                        where_clause += ' AND idempresa = %s'
                        where_parameters.append(current_company_id())
                    if has_idcodmed:
                        cursor.execute(('''
                            UPDATE public.ic_usuario_geral SET
                                nome = %s, login = %s, senha = %s, ativo = %s,
                                idperfil = %s, idempresa = %s, idcodmed = %s
                            {where_clause}
                        ''').format(where_clause=where_clause), (
                            item['nome'], item['login'], item['senha'], item['ativo'],
                            item['idperfil'], item['idempresa'], item['idcodmed'],
                            *where_parameters,
                        ))
                    elif has_idprefere:
                        cursor.execute(('''
                            UPDATE public.ic_usuario_geral SET
                                nome = %s, login = %s, senha = %s, ativo = %s,
                                idperfil = %s, idempresa = %s, idprefere = %s
                            {where_clause}
                        ''').format(where_clause=where_clause), (
                            item['nome'], item['login'], item['senha'], item['ativo'],
                            item['idperfil'], item['idempresa'], item['idcodmed'],
                            *where_parameters,
                        ))
                    elif has_codmed:
                        cursor.execute(('''
                            UPDATE public.ic_usuario_geral SET
                                nome = %s,
                                login = %s,
                                senha = %s,
                                ativo = %s,
                                idperfil = %s,
                                idempresa = %s,
                                codmed = %s
                            {where_clause}
                        ''').format(where_clause=where_clause), (
                            item['nome'], item['login'], item['senha'], item['ativo'],
                            item['idperfil'], item['idempresa'], item['idcodmed'],
                            *where_parameters,
                        ))
                    else:
                        cursor.execute(('''
                            UPDATE public.ic_usuario_geral SET
                                nome = %s,
                                login = %s,
                                senha = %s,
                                ativo = %s,
                                idperfil = %s,
                                idempresa = %s
                            {where_clause}
                        ''').format(where_clause=where_clause), (
                            item['nome'], item['login'], item['senha'], item['ativo'],
                            item['idperfil'], item['idempresa'],
                            *where_parameters,
                        ))
                    updated = cursor.rowcount > 0
                    if not updated:
                        return jsonify({'success': False, 'message': 'Usuario nao encontrado.'}), 404
                    return jsonify({'success': True, 'message': 'Usuario alterado com sucesso.'})
        layout = _layout()
        with _connection() as connection:
            with connection.cursor() as cursor:
                is_current_user_master = _current_user_is_master(cursor)
                if not is_current_user_master and _legacy_record_is_master(cursor, layout, record_id):
                    raise PermissionError('Apenas usuários com perfil MASTER podem alterar usuário MASTER.')
                _validate_master_profile_permission(data, is_current_user_master)
        item = _usuario_data(data, layout)
        updated = _repository(layout).update(record_id, item)
        if not updated:
            return jsonify({'success': False, 'message': 'Usuario nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Usuario alterado com sucesso.'})
    except Exception as exc:
        return _error_response(exc)


@usuario_api_bp.route('/api/usuarios/itens/<record_id>', methods=['DELETE'])
def delete_usuario(record_id):
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                if _general_users_available(cursor):
                    is_current_user_master = _current_user_is_master(cursor)
                    has_global_scope = _current_user_has_global_scope(cursor)
                    if not is_current_user_master and _record_is_master_user(cursor, record_id):
                        raise PermissionError('Apenas usuarios com perfil MASTER podem excluir usuario MASTER.')
                    if has_global_scope:
                        cursor.execute('''
                            DELETE FROM public.ic_usuario_geral
                            WHERE idusuario = %s
                        ''', (record_id,))
                    else:
                        cursor.execute('''
                        DELETE FROM public.ic_usuario_geral
                        WHERE idusuario = %s AND idempresa = %s
                        ''', (record_id, current_company_id()))
                    deleted = cursor.rowcount > 0
                    if not deleted:
                        return jsonify({'success': False, 'message': 'Usuario nao encontrado.'}), 404
                    return jsonify({'success': True, 'message': 'Usuario excluido com sucesso.'})
        layout = _layout()
        with _connection() as connection:
            with connection.cursor() as cursor:
                if not _current_user_is_master(cursor) and _legacy_record_is_master(cursor, layout, record_id):
                    raise PermissionError('Apenas usuários com perfil MASTER podem excluir usuário MASTER.')
        deleted = _repository(layout).delete(record_id)
        if not deleted:
            return jsonify({'success': False, 'message': 'Usuario nao encontrado.'}), 404
        return jsonify({'success': True, 'message': 'Usuario excluido com sucesso.'})
    except Exception as exc:
        return _error_response(exc)
