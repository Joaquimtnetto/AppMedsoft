import unittest
from unittest.mock import patch
from contextlib import contextmanager
from datetime import date

from flask import Flask

import agenda_api
import baileys_api
import email_robot
import clinica_api
import configuracao_api
import consulta_paciente
import consultas_routes
import empresa_api
import exame_api
import medsoft_app
import medsoft_core
import paciente_api
import perfil_api
import prof_saude_api
import tenant_context
import usuario_api
from crud_repository import CrudRepository


class EncodingTest(unittest.TestCase):
    def test_uses_utf8_for_regular_postgres_databases(self):
        self.assertEqual(medsoft_core._client_encoding('UTF8'), 'UTF8')

    def test_uses_latin1_to_decode_legacy_sql_ascii_database(self):
        self.assertEqual(medsoft_core._client_encoding('SQL_ASCII'), 'LATIN1')

    def test_allows_explicit_client_encoding_override(self):
        self.assertEqual(medsoft_core._client_encoding('SQL_ASCII', 'UTF8'), 'UTF8')


class AuthenticationGuardTest(unittest.TestCase):
    def test_core_menus_are_always_open_and_editable(self):
        permissions = medsoft_app._ensure_core_menu_permissions([
            '1-AM-NET', '2-NAM-NET', '3-AM-NET', '4-NAM-NET', '5-AM-NET'
        ])
        self.assertIn('1-AM-ET', permissions)
        self.assertIn('2-AM-ET', permissions)
        self.assertIn('3-AM-ET', permissions)
        self.assertIn('4-AM-ET', permissions)
        self.assertIn('5-AM-NET', permissions)

    def setUp(self):
        medsoft_app.app.config['TESTING'] = True
        self.client = medsoft_app.app.test_client()

    def test_menu_requires_valid_login_session(self):
        response = self.client.get('/menu.html')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/'))

    def test_menu_accepts_complete_session_after_server_restart(self):
        with self.client.session_transaction() as flask_session:
            flask_session['usuario'] = 'Carlos'
            flask_session['idusuario'] = 2
            flask_session['idempresa'] = 2
            flask_session['db_path'] = 'medsoft_medmigra'
            flask_session['authenticated'] = True

        response = self.client.get('/menu.html')

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as flask_session:
            self.assertEqual(flask_session['usuario'], 'Carlos')

    def test_api_rejects_request_without_valid_login_session(self):
        response = self.client.post('/api/clinicas', json={'termo': ''})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()['success'])

    def test_menu_accepts_legacy_codclin_session_and_hydrates_company(self):
        with self.client.session_transaction() as flask_session:
            flask_session['usuario'] = 'Tania'
            flask_session['idusuario'] = 5
            flask_session['codclin'] = 5
            flask_session['db_path'] = 'medsoft_medmigra'
            flask_session['authenticated'] = True

        response = self.client.get('/menu.html')

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as flask_session:
            self.assertEqual(flask_session['idempresa'], 5)

    def test_master_user_menu_does_not_show_clinic_header(self):
        with self.client.session_transaction() as flask_session:
            flask_session['usuario'] = 'Netto'
            flask_session['idusuario'] = 3
            flask_session['idempresa'] = 0
            flask_session['db_path'] = 'medsoft_medmigra'
            flask_session['empresa_nome'] = 'CarlosNeurologia'
            flask_session['perfil'] = 'Master'
            flask_session['authenticated'] = True

        response = self.client.get('/menu.html')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'CarlosNeurologia', response.data)

    def test_master_user_with_company_shows_company_header(self):
        with self.client.session_transaction() as flask_session:
            flask_session['usuario'] = 'Tania'
            flask_session['idusuario'] = 5
            flask_session['idempresa'] = 5
            flask_session['db_path'] = 'medsoft_medmigra'
            flask_session['empresa_nome'] = 'Empresa 5'
            flask_session['perfil'] = 'Master'
            flask_session['authenticated'] = True

        response = self.client.get('/menu.html')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'5 -', response.data)
        self.assertIn(b'Empresa 5', response.data)

    def test_master_without_company_uses_default_database_for_login(self):
        class Cursor:
            def __init__(self):
                self.parameters = None

            def execute(self, statement, parameters=None):
                self.parameters = parameters

            def fetchone(self):
                return (3, None, 'Netto', None, None, None, 'Master')

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def close(self):
                self.closed = True

        connection = Connection()
        original_get_db_connection = medsoft_app.get_db_connection
        medsoft_app.get_db_connection = lambda _db_path=None: connection
        try:
            result = medsoft_app.get_user_empresa_db('Netto', 'Netto')
        finally:
            medsoft_app.get_db_connection = original_get_db_connection

        self.assertEqual(result[0], 3)
        self.assertEqual(result[1], 0)
        self.assertEqual(result[3], medsoft_app.config.PG_DB)
        self.assertEqual(result[6], 'Master')

    def test_master_with_company_keeps_company_id_when_company_is_inactive(self):
        class Cursor:
            def execute(self, statement, parameters=None):
                self.parameters = parameters

            def fetchone(self):
                return (5, 5, 'Tania', 'medsoft_medmigra', 'Empresa 5', None, 'Master')

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

            def close(self):
                pass

        original_get_db_connection = medsoft_app.get_db_connection
        medsoft_app.get_db_connection = lambda _db_path=None: Connection()
        try:
            result = medsoft_app.get_user_empresa_db('Tania', 'Tania')
        finally:
            medsoft_app.get_db_connection = original_get_db_connection

        self.assertEqual(result[1], 5)
        self.assertEqual(result[3], 'medsoft_medmigra')
        self.assertEqual(result[4], 'Empresa 5')


    def test_company_plan_without_days_has_unlimited_usage(self):
        allowed, limit_date = self._usage_limit_for((date(2025, 1, 1), None), date(2030, 1, 1))
        self.assertTrue(allowed)
        self.assertIsNone(limit_date)

    def test_company_plan_blocks_after_start_date_plus_plan_days(self):
        allowed, limit_date = self._usage_limit_for((date(2026, 1, 1), 30), date(2026, 2, 1))
        self.assertFalse(allowed)
        self.assertEqual(limit_date, date(2026, 1, 31))

    def test_master_login_does_not_validate_company_usage_limit(self):
        original_user = medsoft_app.get_user_empresa_db
        original_limit = medsoft_app.get_company_usage_limit
        original_connection = medsoft_app.get_db_connection
        original_capabilities = medsoft_app._load_plan_capabilities
        medsoft_app.get_user_empresa_db = lambda login, password: (
            3, 2, 'Netto', 'medsoft_medmigra', 'CarlosNeurologia', None, 'Master'
        )
        medsoft_app.get_company_usage_limit = lambda company_id: self.fail(
            'O limite do plano nao deve ser consultado para usuario Master.'
        )

        class Connection:
            def close(self):
                pass

        medsoft_app.get_db_connection = lambda database=None: Connection()
        medsoft_app._load_plan_capabilities = lambda company_id, force=False: {}
        try:
            response = self.client.post('/api/login', json={'nome': 'Netto', 'senha': 'Netto'})
        finally:
            medsoft_app.get_user_empresa_db = original_user
            medsoft_app.get_company_usage_limit = original_limit
            medsoft_app.get_db_connection = original_connection
            medsoft_app._load_plan_capabilities = original_capabilities

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])

    def _usage_limit_for(self, database_row, today):
        class Cursor:
            def execute(self, statement, parameters=None):
                pass

            def fetchone(self):
                return database_row

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                pass

        class Connection:
            def cursor(self):
                return Cursor()

            def close(self):
                pass

        original = medsoft_app.get_db_connection
        medsoft_app.get_db_connection = lambda _db_path=None: Connection()
        try:
            return medsoft_app.get_company_usage_limit(5, today)
        finally:
            medsoft_app.get_db_connection = original


class ConfigurationTest(unittest.TestCase):
    def test_maps_whatsapp_automation_fields(self):
        values = configuracao_api._automation_values({
            'autlembraagendawhatzap': '1440',
            'autlembraretagendawhatzap': '720',
            'autlembraniverwahtzap': '60',
            'autlembraeventowahtzap': '30',
            'textolembraagendawahtzap': '2',
            'textolembraretagendawahtzap': '3',
            'textolembraniverwahtzap': '7',
            'textolembraeventwahtzap': '8',
        })
        self.assertEqual(values['autlembraagendawhatzap'], 1440)
        self.assertEqual(values['autlembraretagendawhatzap'], 720)
        self.assertEqual(values['autlembraniverwahtzap'], 60)
        self.assertEqual(values['autlembraeventowahtzap'], 30)
        self.assertEqual(values['textolembraagendawahtzap'], 2)
        self.assertEqual(values['textolembraretagendawahtzap'], 3)
        self.assertEqual(values['textolembraniverwahtzap'], 7)
        self.assertEqual(values['textolembraeventwahtzap'], 8)

    def test_maps_notification_configuration(self):
        values = configuracao_api._configuration_values({
            'smtp_porta': '587',
            'smtp_tls': True,
            'whatsapp_remetente': '(21) 98649-6127',
        })
        self.assertEqual(values['smtp_porta'], 587)
        self.assertTrue(values['smtp_tls'])
        self.assertEqual(values['whatsapp_remetente'], '5521986496127')
        self.assertFalse(values['whatzapsimplificado'])

    def test_maps_simplified_whatsapp_mode(self):
        values = configuracao_api._configuration_values({
            'whatsapp_remetente': '5521986496127',
            'whatzapsimplificado': True,
        })
        self.assertTrue(values['whatzapsimplificado'])

    def test_rejects_tls_and_ssl_together(self):
        with self.assertRaises(ValueError):
            configuracao_api._configuration_values({
                'smtp_tls': True,
                'smtp_ssl': True,
                'whatsapp_remetente': '5521986496127',
            })

    def test_maps_smtp_connection_test_values(self):
        values = configuracao_api._smtp_test_values({
            'smtp_host': 'h66.servidorhh.com',
            'smtp_porta': '587',
            'smtp_usuario': 'agenda@medsoft.com.br',
            'smtp_tls': True,
        })
        self.assertEqual(values['port'], 587)
        self.assertEqual(values['host'], 'h66.servidorhh.com')
        self.assertTrue(values['use_tls'])

    def test_updates_existing_configuration_without_insert(self):
        class ConfigurationCursor:
            def __init__(self):
                self.executions = []
                self.rowcount = 1

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return ('public.medsoft_configuracao',)

            def fetchall(self):
                columns = ('codclin', 'whatsapp_remetente', 'whatzapsimplificado')
                if 'data_type' in self.executions[-1][0]:
                    return [(name, 'character varying') for name in columns]
                return [(name,) for name in columns]

        class ConfigurationConnection:
            def __init__(self):
                self.cursor_instance = ConfigurationCursor()

            def cursor(self):
                return self.cursor_instance

        connection = ConfigurationConnection()

        @contextmanager
        def fake_connection():
            yield connection

        original_connection = configuracao_api._connection
        configuracao_api._connection = fake_connection
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(configuracao_api.configuracao_api_bp)
        try:
            client = app.test_client()
            with client.session_transaction() as flask_session:
                flask_session['idempresa'] = 8
            response = client.put('/api/configuracao', json={
                'whatsapp_remetente': '5521986496127',
                'whatzapsimplificado': True,
            })
        finally:
            configuracao_api._connection = original_connection
        self.assertEqual(response.status_code, 200)
        statements = [str(item[0]).upper() for item in connection.cursor_instance.executions]
        self.assertTrue(any('UPDATE PUBLIC.MEDSOFT_CONFIGURACAO' in item for item in statements))
        self.assertFalse(any('INSERT INTO PUBLIC.MEDSOFT_CONFIGURACAO' in item for item in statements))

    def test_loads_legacy_configuration_without_company_column(self):
        class LegacyConfigurationCursor:
            def __init__(self):
                self.executions = []
                self.results = [
                    ('public.medsoft_configuracao',),
                    (False,),
                    (False,),
                    ('smtp.example.com', 587, 'agenda', True, 'agenda@example.com',
                     True, False, '5521986496127', '', False, '', '', 'pt_BR', 'N'),
                ]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return self.results.pop(0)

            def fetchall(self):
                return [(name,) for name in (
                    'smtp_host', 'smtp_porta', 'smtp_usuario', 'smtp_senha',
                    'smtp_remetente', 'smtp_tls', 'smtp_ssl', 'whatsapp_remetente',
                    'whatsapp_phone_number_id', 'whatsapp_token', 'whatsapp_api_version',
                    'whatsapp_template', 'whatsapp_idioma', 'whatzapsimplificado',
                )]

        class LegacyConfigurationConnection:
            def __init__(self):
                self.cursor_instance = LegacyConfigurationCursor()

            def cursor(self):
                return self.cursor_instance

        connection = LegacyConfigurationConnection()

        @contextmanager
        def fake_connection():
            yield connection

        original_connection = configuracao_api._connection
        configuracao_api._connection = fake_connection
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(configuracao_api.configuracao_api_bp)
        try:
            response = app.test_client().post('/api/configuracao')
        finally:
            configuracao_api._connection = original_connection

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['configuracao']['smtp_host'], 'smtp.example.com')
        statements = [str(item[0]).upper() for item in connection.cursor_instance.executions]
        self.assertFalse(any('WHERE CODCLIN' in item for item in statements))


class TenantContextTest(unittest.TestCase):
    def test_current_company_uses_legacy_codclin_when_idempresa_is_missing(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context('/'):
            from flask import session
            session['codclin'] = 5
            self.assertEqual(tenant_context.current_company_id(), 5)


class PerfilTest(unittest.TestCase):
    def test_maps_profile_values(self):
        layout = {
            'fields': {
                'nome': 'perfil',
                'descricao': 'descricao',
                'ativo': 'ativo',
            }
        }
        values = perfil_api._profile_values({
            'nome': 'Administrador',
            'descricao': 'Acesso total',
            'ativo': True,
        }, layout)
        self.assertEqual(values['perfil'], 'Administrador')
        self.assertEqual(values['descricao'], 'Acesso total')
        self.assertTrue(values['ativo'])

    def test_requires_profile_name(self):
        with self.assertRaises(ValueError):
            perfil_api._profile_values({'nome': ''}, {'fields': {'nome': 'perfil'}})


class ClinicaPermissionTest(unittest.TestCase):
    def test_only_master_profile_matches_include_permission(self):
        self.assertTrue(clinica_api._profile_is_master('Master'))
        self.assertTrue(clinica_api._profile_is_master(' MASTER '))
        self.assertFalse(clinica_api._profile_is_master('Administrador'))
        self.assertFalse(clinica_api._profile_is_master(''))

    def test_create_clinica_requires_master_profile(self):
        original_can_include = clinica_api._can_include_clinica
        clinica_api._can_include_clinica = lambda: False

        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(clinica_api.clinica_api_bp)
        client = app.test_client()

        try:
            response = client.post('/api/clinicas/itens', json={'nome': 'Clinica Teste'})
        finally:
            clinica_api._can_include_clinica = original_can_include

        self.assertEqual(response.status_code, 403)
        self.assertIn('MASTER', response.get_json()['message'])

    def test_clinica_repository_generates_new_id_without_current_company_tenant(self):
        repository = clinica_api._repository({
            'table': 'clinica',
            'id_column': 'codclin',
            'fields': {'nome': 'nome'},
            'generate_integer_id': True,
        })

        self.assertIsNone(repository.tenant_column)
        self.assertTrue(repository.generate_integer_id)

    def test_clinica_values_include_company_relation(self):
        values = clinica_api._clinica_data({
            'idempresa': '2',
            'nome': 'Clinica Matriz',
        }, {
            'fields': {
                'idempresa': 'idempresa',
                'nome': 'nome',
            }
        })

        self.assertEqual(values['idempresa'], 2)
        self.assertEqual(values['nome'], 'Clinica Matriz')


class EmpresaApiTest(unittest.TestCase):
    def test_master_linked_to_company_has_global_company_scope(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context('/'):
            from flask import session
            session['perfil'] = 'Master'
            session['idempresa'] = 2
            self.assertTrue(empresa_api._current_user_has_global_scope(None))

    def test_generates_company_id_when_sequence_exists_but_is_not_accessible(self):
        layout = {
            'id_type': 'integer',
            'id_default': "nextval('ic_empresa_geral_idempresa_seq'::regclass)",
        }
        self.assertTrue(empresa_api._should_generate_integer_id(layout))

    def test_maps_company_values(self):
        layout = {
            'fields': {
                'nome': 'nome',
                'database': 'database',
                'ativo': 'ativo',
            }
        }
        values = empresa_api._empresa_values({
            'nome': 'Clinica Nova',
            'database': 'medsoft_nova',
            'ativo': False,
        }, layout)

        self.assertEqual(values['nome'], 'Clinica Nova')
        self.assertEqual(values['database'], 'medsoft_nova')
        self.assertFalse(values['ativo'])

    def test_requires_company_name_and_database(self):
        layout = {'fields': {'nome': 'nome', 'database': 'database'}}
        with self.assertRaises(ValueError):
            empresa_api._empresa_values({'nome': '', 'database': 'medsoft'}, layout)
        with self.assertRaises(ValueError):
            empresa_api._empresa_values({'nome': 'Empresa', 'database': ''}, layout)

    def test_only_master_profile_can_edit_company(self):
        self.assertTrue(empresa_api._is_master_profile('Master'))
        self.assertFalse(empresa_api._is_master_profile('Usuario'))

    def test_company_lock_returns_clear_conflict_message(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(empresa_api.empresa_api_bp)
        with app.test_request_context('/'):
            response, status = empresa_api._error_response(
                empresa_api.errors.LockNotAvailable('registro bloqueado')
            )
        self.assertEqual(status, 409)
        self.assertIn('outra conexao', response.get_json()['message'])

    def test_maps_optional_commercial_company_values(self):
        field_names = (
            'nome', 'database', 'email', 'telefone', 'whatsapp',
            'datainico', 'pago', 'titulo1', 'titulo2'
        )
        layout = {'fields': {name: name for name in field_names}}
        layout['fields']['plano'] = 'idplano'
        values = empresa_api._empresa_values({
            'nome': 'Clinica Nova', 'database': 'medsoft_nova',
            'email': 'contato@clinica.com.br', 'telefone': '(21) 2222-3333',
            'whatsapp': '(21) 99999-8888', 'plano': '1',
            'datainico': '2026-07-20', 'pago': 'S',
            'titulo1': 'Clinica Nova', 'titulo2': 'Atendimento medico',
        }, layout)

        self.assertEqual(values['email'], 'contato@clinica.com.br')
        self.assertEqual(values['datainico'].isoformat(), '2026-07-20')
        self.assertEqual(values['idplano'], 1)
        self.assertEqual(values['pago'], 'S')

    def test_maps_subscription_plan_values(self):
        values = empresa_api._subscription_plan_values({
            'plano': 'Profissional', 'descricao': 'Plano da clinica', 'valor': '199,90',
            'qtdusuarios': '5', 'confagenda': 'S', 'qtdpacientes': '500',
            'teleconsulta': 'S', 'financeiro': 'N', 'ditadovoz': 'S',
            'datamax': '2027-12-31',
            'diasmax': '365',
        })

        self.assertEqual(values['plano'], 'Profissional')
        self.assertEqual(values['valor'], 199.90)
        self.assertEqual(values['qtdusuarios'], 5)
        self.assertEqual(values['teleconsulta'], 'S')
        self.assertEqual(values['datamax'].isoformat(), '2027-12-31')
        self.assertEqual(values['diasmax'], 365)

    def test_rejects_subscription_plan_quantity_above_database_limit(self):
        with self.assertRaisesRegex(ValueError, '2.147.483.647'):
            empresa_api._subscription_plan_values({
                'plano': 'Basico', 'qtdusuarios': '1',
                'qtdpacientes': '10000000000000',
            })


class EmailRobotPlanRestrictionTest(unittest.TestCase):
    def test_agenda_confirmation_requires_enabled_plan_flag(self):
        class Cursor:
            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, parameters=None):
                self.parameters = parameters

            def fetchone(self):
                return (self.value,)

        class Connection:
            def __init__(self, value):
                self.value = value

            def cursor(self):
                return Cursor(self.value)

            def close(self):
                pass

        original_connection = email_robot.get_db_connection
        try:
            email_robot.get_db_connection = lambda _database=None: Connection('SIM')
            self.assertTrue(email_robot._agenda_confirmation_enabled(2))
            email_robot.get_db_connection = lambda _database=None: Connection('NÃO')
            self.assertFalse(email_robot._agenda_confirmation_enabled(2))
        finally:
            email_robot.get_db_connection = original_connection


class FakeCursor:
    def __init__(self):
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters=None):
        self.executions.append((statement, parameters))

    def fetchone(self):
        return (7,)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


class CrudRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()

        @contextmanager
        def connection_factory():
            yield self.connection

        self.repository = CrudRepository(
            connection_factory, 'example', 'id', ('name', 'active')
        )

    def test_create_update_and_delete(self):
        self.assertEqual(self.repository.create({'name': 'Teste'}), 7)
        self.assertTrue(self.repository.update(7, {'active': True}))
        self.assertTrue(self.repository.delete(7))
        self.assertEqual(len(self.connection.cursor_instance.executions), 3)

    def test_rejects_columns_outside_allowlist(self):
        with self.assertRaises(ValueError):
            self.repository.create({'not_allowed': 'value'})

    def test_generates_integer_id_for_legacy_table(self):
        repository = CrudRepository(
            self.repository.connection_factory,
            'legacy_example',
            'id',
            ('name',),
            generate_integer_id=True,
        )
        self.assertEqual(repository.create({'name': 'Teste'}), 7)
        self.assertEqual(len(self.connection.cursor_instance.executions), 3)

    def test_tenant_is_forced_on_create_update_and_delete(self):
        repository = CrudRepository(
            self.repository.connection_factory,
            'example',
            'id',
            ('name',),
            tenant_column='codclin',
            tenant_value_factory=lambda: 23,
        )
        repository.create({'name': 'Empresa 23'})
        repository.update(7, {'name': 'Alterado'})
        repository.delete(7)
        executions = self.connection.cursor_instance.executions[-3:]
        self.assertEqual(executions[0][1], ['Empresa 23', 23])
        self.assertEqual(executions[1][1], ['Alterado', 7, 23])
        self.assertEqual(executions[2][1], [7, 23])


class PatientOptionsApiTest(unittest.TestCase):
    def test_lists_only_patients_from_session_company(self):
        class Cursor:
            def __init__(self):
                self.executions = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchall(self):
                return [(42, 'Paciente Teste', '(21)99999-9999', 'p@teste.com', 'Plano A')]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        connection = Connection()

        @contextmanager
        def fake_connection():
            yield connection

        original_connection = paciente_api._connection
        original_detect_fields = paciente_api._detect_fields
        paciente_api._connection = fake_connection
        paciente_api._detect_fields = lambda: {
            'nome': 'nomecli', 'telefone': 'telres', 'email': 'email', 'plano': 'nomeplano1'
        }
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(paciente_api.paciente_api_bp)
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session['idempresa'] = 23
        try:
            response = client.post('/api/pacientes/opcoes', json={'termo': ''})
        finally:
            paciente_api._connection = original_connection
            paciente_api._detect_fields = original_detect_fields

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['pacientes'][0]['id'], 42)
        self.assertEqual(connection.cursor_instance.executions[0][1], [23])


class PatientSearchApiTest(unittest.TestCase):
    def test_patient_report_excludes_internal_columns(self):
        for column in ('codclin', 'ID', 'doença1', 'doenca1', 'nomed', 'Mes', 'Cident'):
            with self.subTest(column=column):
                self.assertFalse(consulta_paciente._patient_report_column_allowed(column))
        self.assertTrue(consulta_paciente._patient_report_column_allowed('nomecli'))

    def test_search_tolerates_missing_optional_patient_columns(self):
        class Cursor:
            def __init__(self):
                self.executions = []
                self.fetch_count = 0

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchall(self):
                self.fetch_count += 1
                if self.fetch_count == 1:
                    return [('nomecli',), ('codcli',), ('codclin',)]
                return [('Ana Teste', 72, 0, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def close(self):
                self.closed = True

        connection = Connection()
        original_get_db_connection = consulta_paciente.get_db_connection
        consulta_paciente.get_db_connection = lambda _db_path=None: connection
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(consulta_paciente.consulta_paciente_bp)
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session['idempresa'] = 5
            flask_session['db_path'] = 'medsoft_medmigra'
        try:
            response = client.post('/api/consulta-paciente', json={'termo': 'A'})
        finally:
            consulta_paciente.get_db_connection = original_get_db_connection

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['pacientes'][0]['codcli'], 72)
        self.assertEqual(connection.cursor_instance.executions[1][1], (5, '%A%', 'A'))


class UsuarioApiTest(unittest.TestCase):
    def test_master_linked_to_company_has_global_user_scope(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context('/'):
            from flask import session
            session['perfil'] = 'Master'
            session['idempresa'] = 2
            self.assertTrue(usuario_api._current_user_has_global_scope(None))

    def test_rejects_new_user_when_company_plan_limit_is_reached(self):
        class Cursor:
            def __init__(self):
                self.executions = []

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return (4, 4)

        cursor = Cursor()
        with self.assertRaisesRegex(ValueError, 'no maximo 4 usuario'):
            usuario_api._validate_company_user_limit(cursor, 2)
        self.assertEqual(cursor.executions[-1][1], (2,))

    def test_allows_new_user_below_company_plan_limit(self):
        class Cursor:
            def execute(self, statement, parameters=None):
                pass

            def fetchone(self):
                return (5, 4)

        usuario_api._validate_company_user_limit(Cursor(), 2)

    def test_plan_without_user_quantity_is_unlimited(self):
        class Cursor:
            def execute(self, statement, parameters=None):
                pass

            def fetchone(self):
                return (None, 100)

        usuario_api._validate_company_user_limit(Cursor(), 2)

    def test_lists_general_login_users_from_session_company(self):
        class Cursor:
            def __init__(self):
                self.executions = []
                self.results = [
                    ('public.ic_usuario_geral',),
                    (False,),
                    (False,),
                    (False,),
                    ('public.ic_perfil_geral',),
                ]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return self.results.pop(0)

            def fetchall(self):
                return [(2, 'Carlos', 'Carlos', '', '', '', '', 2, 2, '', None, '', 'CarlosNeurologia', 'CarlosNeurologia')]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        connection = Connection()

        @contextmanager
        def fake_connection():
            yield connection

        original_connection = usuario_api._connection
        usuario_api._connection = fake_connection
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(usuario_api.usuario_api_bp)
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session['idempresa'] = 2
        try:
            response = client.post('/api/usuarios', json={'termo': ''})
        finally:
            usuario_api._connection = original_connection

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['usuarios'][0]['nome'], 'Carlos')
        self.assertEqual(response.get_json()['usuarios'][0]['empresa_nome'], 'CarlosNeurologia')
        self.assertEqual(connection.cursor_instance.executions[-1][1], [2])


class ExamApiTest(unittest.TestCase):
    def test_creates_exam_for_patient_and_session_company(self):
        class Cursor:
            def __init__(self):
                self.executions = []
                self.results = [(1,), (77,)]
                self.rowcount = 1

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return self.results.pop(0)

            def fetchall(self):
                return [(name,) for name in (
                    'nome', 'codcli', 'codpac', 'data', 'imagem',
                    'observacao', 'idexame', 'codclin',
                )]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        connection = Connection()

        @contextmanager
        def fake_connection():
            yield connection

        original_connection = exame_api._connection
        exame_api._connection = fake_connection
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(exame_api.exame_api_bp)
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session['idempresa'] = 23
        try:
            response = client.post('/api/pacientes/42/exames', json={
                'nome': 'Hemograma', 'data': '2026-07-02'
            })
        finally:
            exame_api._connection = original_connection

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['id'], 77)
        insert_parameters = connection.cursor_instance.executions[2][1]
        self.assertEqual(insert_parameters[0], 'Hemograma')
        self.assertEqual(insert_parameters[1:3], [42, 42])
        self.assertEqual(insert_parameters[-1], 23)

    def test_rejects_invalid_exam_name_and_date(self):
        with self.assertRaises(ValueError):
            exame_api._exam_values({'nome': 'X' * 21, 'data': '2026-07-02'})
        with self.assertRaises(ValueError):
            exame_api._exam_values({'nome': 'Hemograma', 'data': ''})


class FakeAgendaRepository:
    def __init__(self):
        self.calls = []

    def create(self, values):
        self.calls.append(('create', values))
        return 15

    def update(self, record_id, values):
        self.calls.append(('update', record_id, values))
        return True

    def delete(self, record_id):
        self.calls.append(('delete', record_id))
        return True


class AgendaCrudApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder='../templates')
        self.app.secret_key = 'test'
        self.app.register_blueprint(agenda_api.agenda_api_bp)
        self.repository = FakeAgendaRepository()
        self.original_repository = agenda_api.agenda_repository
        self.original_registered_patient = agenda_api._registered_patient
        self.original_appointment_schedule = agenda_api._appointment_schedule
        agenda_api.agenda_repository = self.repository
        def fake_registered_patient(patient_id):
            if not patient_id:
                raise ValueError('Selecione um paciente cadastrado.')
            return {'id': 42, 'nome': 'Paciente Teste', 'telefone': '', 'email': '', 'plano': ''}
        agenda_api._registered_patient = fake_registered_patient
        agenda_api._appointment_schedule = lambda _appointment_id: (
            agenda_api.datetime.date(2026, 6, 22), '09:30'
        )
        self.client = self.app.test_client()
        self.payload = {
            'data': '2026-06-22',
            'hora': '09:30',
            'paciente': 'Paciente Teste',
            'codpac': 42,
            'telefone': '(11)2222-3333',
            'email': 'paciente@exemplo.com',
            'profissional': 'Dra. Teste',
            'plano': 'Plano',
            'status': 'AG',
            'procedimento': 'Consulta',
            'observacao': 'Paciente prefere atendimento pela manhã.',
        }

    def tearDown(self):
        agenda_api.agenda_repository = self.original_repository
        agenda_api._registered_patient = self.original_registered_patient
        agenda_api._appointment_schedule = self.original_appointment_schedule

    def test_create_update_and_delete_endpoints(self):
        self.assertEqual(self.client.post('/api/agenda/itens', json=self.payload).status_code, 201)
        self.assertEqual(self.client.put('/api/agenda/itens/15', json=self.payload).status_code, 200)
        self.assertEqual(self.client.delete('/api/agenda/itens/15').status_code, 200)
        self.assertEqual([call[0] for call in self.repository.calls], ['create', 'update', 'delete'])
        saved = self.repository.calls[0][1]
        self.assertEqual(saved['horacons'], '09:30')
        self.assertEqual(saved['telefone'], '(11)2222-3333')
        self.assertEqual(saved['email'], 'paciente@exemplo.com')
        self.assertEqual(saved['nomed'], 'Dra. Teste')
        self.assertEqual(saved['atend'], 'AG')
        self.assertEqual(saved['observacao'], 'Paciente prefere atendimento pela manhã.')

    def test_required_patient_validation(self):
        payload = dict(self.payload, codpac=None)
        response = self.client.post('/api/agenda/itens', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_required_professional_validation(self):
        payload = dict(self.payload, profissional='')
        response = self.client.post('/api/agenda/itens', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_phone_validation(self):
        payload = dict(self.payload, telefone='119999')
        response = self.client.post('/api/agenda/itens', json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('(99)9999-9999', response.get_json()['message'])

    def test_status_validation(self):
        payload = dict(self.payload, status='XX')
        response = self.client.post('/api/agenda/itens', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_builds_availability_slots_from_professional_schedule(self):
        schedule = {
            'seg': 'S',
            'iseg': '08:00',
            'fseg': '10:00',
            'iiseg': '14:00',
            'tiseg': '15:00',
        }
        intervals = agenda_api._schedule_intervals(schedule, 0)
        occupied = {'09:00': {'paciente': 'Paciente Teste', 'status': 'AG'}}
        slots = agenda_api._build_slots(intervals, 60, occupied)
        self.assertEqual([slot['hora'] for slot in slots], ['08:00', '09:00', '14:00'])
        self.assertTrue(slots[0]['disponivel'])
        self.assertFalse(slots[1]['disponivel'])
        self.assertEqual(slots[1]['paciente'], 'Paciente Teste')

    def test_includes_appointments_outside_configured_schedule(self):
        occupied = {'09:26': {'paciente': 'Ana', 'status': 'CO'}}
        slots = agenda_api._build_slots([], 30, occupied)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['hora'], '09:26')
        self.assertFalse(slots[0]['disponivel'])
        self.assertEqual(slots[0]['paciente'], 'Ana')

    def test_slot_interval_defaults_to_30_and_allows_configured_values(self):
        self.assertEqual(agenda_api._parse_slot_interval(''), 30)
        self.assertEqual(agenda_api._parse_slot_interval('30'), 30)
        self.assertEqual(agenda_api._parse_slot_interval('60'), 60)
        self.assertEqual(agenda_api._parse_slot_interval('15'), 30)

    def test_formats_whatsapp_phone_with_brazil_country_code(self):
        self.assertEqual(agenda_api._whatsapp_phone('(21) 98649-6127'), '5521986496127')
        self.assertEqual(agenda_api._whatsapp_phone('5521986496127'), '5521986496127')

    def test_rejects_invalid_whatsapp_phone(self):
        with self.assertRaises(ValueError):
            agenda_api._whatsapp_phone('1234')

    def test_sends_text_to_company_baileys_session(self):
        with patch.object(baileys_api, '_service_request') as service_request:
            service_request.return_value = {'success': True, 'messageId': 'ABC'}
            result = baileys_api.send_baileys_text(8, '5521999999999', 'Mensagem de teste')
        self.assertTrue(result['success'])
        service_request.assert_called_once_with(
            'POST', '/sessions/8/messages/text',
            {'phone': '5521999999999', 'text': 'Mensagem de teste'},
        )

    def test_formats_confirmation_message_pattern_placeholders(self):
        appointment = {
            'data': __import__('datetime').date(2026, 7, 1),
            'hora': '09:30',
            'paciente': 'João da Silva',
            'profissional': 'Dra. Maria',
            'procedimento': 'consulta',
            'nomeclinica': 'Clínica Exemplo',
        }
        message = agenda_api._confirmation_message(
            appointment,
            'Prezado {paciente}, confirme {procedimento} em {data} às {hora} '
            'com {profissional}. {NomeClinica).',
        )
        self.assertEqual(
            message,
            'Prezado João da Silva, confirme consulta em 01/07/2026 às 09:30 '
            'com Dra. Maria. Clínica Exemplo.',
        )

    def test_whatsapp_confirmation_message_contains_confirmation_link(self):
        appointment = {
            'data': __import__('datetime').date(2026, 7, 1),
            'hora': '09:30', 'paciente': 'Joao', 'profissional': 'Dr Carlos',
            'procedimento': 'Consulta', 'nomeclinica': 'MedSoft',
        }
        link = 'https://medsoft.com.br/confirmar-agendamento/token'
        message = agenda_api._confirmation_message(
            appointment, 'Confirme aqui: {link_confirmacao}', link
        )
        self.assertIn(link, message)

    def test_confirmed_whatsapp_message_is_signed_by_clinic(self):
        appointment = {
            'data': __import__('datetime').date(2026, 7, 16),
            'hora': '10:14', 'paciente': 'Alice', 'profissional': 'Dr. Carlos',
            'procedimento': 'Consulta', 'nomeclinica': 'Clínica Carlos Neurologia',
        }
        message = agenda_api._confirmed_appointment_message(appointment)
        self.assertIn('Atenciosamente,\nClínica Carlos Neurologia.', message)
        self.assertNotIn('Atenciosamente,\nMedSoft.', message)

    def test_whatsapp_local_confirmation_url_uses_clickable_ip(self):
        with self.app.test_request_context('/', base_url='http://localhost:8072'):
            from flask import session
            session['idempresa'] = 8
            link = agenda_api._whatsapp_confirmation_url(15)
        self.assertTrue(link.startswith('http://127-0-0-1.sslip.io:8072/confirmar-agendamento/'))
        self.assertNotIn('localhost', link)

    def test_confirmation_email_html_uses_medsoft_brand_and_button(self):
        appointment = {
            'data': __import__('datetime').date(2026, 7, 1),
            'hora': '09:30', 'paciente': 'Joao', 'profissional': 'Dra. Maria',
            'procedimento': 'Consulta', 'nomeclinica': 'Clinica Exemplo',
        }
        with self.app.app_context():
            rendered = agenda_api._confirmation_email_html(
                appointment, 'https://medsoft.com.br/confirmar/teste'
            )
        self.assertIn('MedSoft', rendered)
        self.assertIn('Confirmar agendamento', rendered)
        self.assertIn('https://medsoft.com.br/confirmar/teste', rendered)

    def test_confirmed_appointment_message(self):
        appointment = {
            'data': __import__('datetime').date(2026, 7, 1),
            'hora': '09:30', 'paciente': 'Joao', 'profissional': 'Dr Carlos',
            'procedimento': 'Consulta',
        }
        message = agenda_api._confirmed_appointment_message(appointment)
        self.assertIn('foi confirmada', message)
        self.assertIn('01/07/2026', message)


class FakeConsultaCursor:
    def __init__(self):
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, parameters=None):
        self.executions.append((statement, parameters))

    def fetchone(self):
        statement = self.executions[-1][0] if self.executions else ''
        if 'SELECT 1 FROM public.pacient' in statement:
            return (1,)
        if 'SELECT usuario.idcodmed' in statement:
            return (3, 'ProfSaúde')
        if 'SELECT COALESCE(MAX(cod), 0) + 1' in statement:
            return (175511,)
        if 'UPDATE public.consulta' in statement:
            return (175511,)
        return (__import__('datetime').date(2026, 6, 30),)


class FakeConsultaConnection:
    def __init__(self):
        self.cursor_instance = FakeConsultaCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class ConsultaHistoryApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test'
        self.app.register_blueprint(consultas_routes.consultas_bp)
        self.connection = FakeConsultaConnection()
        self.original_connection = consultas_routes.get_db_connection
        consultas_routes.get_db_connection = lambda _db_path=None: self.connection
        self.client = self.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session['idempresa'] = 8

    def tearDown(self):
        consultas_routes.get_db_connection = self.original_connection

    def test_creates_an_additional_history_for_patient(self):
        response = self.client.post('/api/consultas-paciente/itens', json={
            'codpac': 42,
            'dtvisita': '2026-06-30',
            'historico': 'Paciente em acompanhamento.',
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.connection.committed)
        insert = next(
            execution for execution in self.connection.cursor_instance.executions
            if 'INSERT INTO public.consulta' in execution[0]
        )
        self.assertIn('INSERT INTO public.consulta', insert[0])
        self.assertEqual(insert[1][0], 42)
        self.assertEqual(insert[1][2], 175511)
        self.assertEqual(insert[1][3], b'Paciente em acompanhamento.')
        self.assertEqual(insert[1][5], 3)
        patient_update = self.connection.cursor_instance.executions[-1]
        self.assertIn('UPDATE public.pacient', patient_update[0])
        self.assertEqual(patient_update[1][1:], (42, 8))

    def test_updates_existing_history_for_patient(self):
        response = self.client.put('/api/consultas-paciente/itens/175511', json={
            'codpac': 42,
            'dtvisita': '2026-06-30',
            'historico': 'Paciente retornou sem queixas.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.connection.committed)
        update = next(
            execution for execution in self.connection.cursor_instance.executions
            if 'UPDATE public.consulta' in execution[0]
        )
        self.assertIn('UPDATE public.consulta', update[0])
        self.assertEqual(update[1][1], b'Paciente retornou sem queixas.')
        self.assertEqual(update[1][3:], (175511, 42, 8))
        patient_update = next(
            execution for execution in self.connection.cursor_instance.executions
            if 'UPDATE public.pacient' in execution[0]
        )
        self.assertIn('SELECT MAX(dtvisita)', patient_update[0])
        self.assertEqual(patient_update[1], (42, 8, 42, 8))
        self.assertEqual(response.get_json()['consulta']['codmed'], 3)

    def test_requires_date_and_history(self):
        invalid_date = self.client.post('/api/consultas-paciente/itens', json={
            'codpac': 42, 'dtvisita': '', 'historico': 'Teste',
        })
        empty_history = self.client.post('/api/consultas-paciente/itens', json={
            'codpac': 42, 'dtvisita': '2026-06-30', 'historico': '',
        })
        self.assertEqual(invalid_date.status_code, 400)
        self.assertEqual(empty_history.status_code, 400)

    def test_local_organization_requires_text_and_pattern(self):
        missing_text = self.client.post('/api/consultas-paciente/organizar', json={
            'texto_livre': '', 'padrao': 'Queixa principal:',
        })
        missing_pattern = self.client.post('/api/consultas-paciente/organizar', json={
            'texto_livre': 'Paciente com dor.', 'padrao': '',
        })
        self.assertEqual(missing_text.status_code, 400)
        self.assertEqual(missing_pattern.status_code, 400)

    def test_local_organization_groups_text_without_saving(self):
        pattern = (
            'Queixa principal:\n\nHistórico familiar:\n\n'
            'Medicamentos:\n\nAlergias:'
        )
        response = self.client.post('/api/consultas-paciente/organizar', json={
            'texto_livre': pattern + (
                '\n\nPaciente relata dor lombar. Mãe diabética. '
                'Faz uso de losartana 50 mg. Alérgico a penicilina.'
            ),
            'padrao': pattern,
        })

        self.assertEqual(response.status_code, 200)
        organized = response.get_json()['historico']
        self.assertIn('Queixa principal:\nPaciente relata dor lombar.', organized)
        self.assertIn('Histórico familiar:\nMãe diabética.', organized)
        self.assertIn('Medicamentos:\nFaz uso de losartana 50 mg.', organized)
        self.assertIn('Alergias:\nAlérgico a penicilina.', organized)
        self.assertFalse(self.connection.committed)

    def test_local_organization_splits_section_names_inside_spoken_sentence(self):
        pattern = (
            'Queixa principal:\n\nHist\u00f3rico familiar:\n\n'
            'Medicamentos:'
        )
        response = self.client.post('/api/consultas-paciente/organizar', json={
            'texto_livre': pattern + (
                '\n\nEnt\u00e3o temos aqui que a queixa principal \u00e9 dor de cabe\u00e7a, '
                'hist\u00f3rico familiar: fam\u00edlia com dor de cabe\u00e7a e '
                'medicamentos: Novalgina tr\u00eas vezes ao dia.'
            ),
            'padrao': pattern,
        })

        self.assertEqual(response.status_code, 200)
        organized = response.get_json()['historico']
        self.assertIn('Queixa principal:\nDor de cabe\u00e7a', organized)
        self.assertIn('Hist\u00f3rico familiar:\nFam\u00edlia com dor de cabe\u00e7a', organized)
        self.assertIn('Medicamentos:\nNovalgina tr\u00eas vezes ao dia.', organized)

    def test_local_organization_accepts_short_and_numbered_spoken_markers(self):
        pattern = 'Queixa Principal:\n\nHist\u00f3rico familiar:\n\nMedicamentos:'
        examples = (
            'queixa dor de cabe\u00e7a hist\u00f3rico fam\u00edlia com dor de cabe\u00e7a '
            'medicamento Novalgina quatro vezes ao dia',
            't\u00f3pico um dor de cabe\u00e7a t\u00f3pico dois fam\u00edlia com dor de cabe\u00e7a '
            't\u00f3pico tr\u00eas Novalgina quatro vezes ao dia',
        )
        for spoken_text in examples:
            with self.subTest(spoken_text=spoken_text):
                response = self.client.post('/api/consultas-paciente/organizar', json={
                    'texto_livre': pattern + '\n\n' + spoken_text,
                    'padrao': pattern,
                })
                self.assertEqual(response.status_code, 200)
                organized = response.get_json()['historico']
                self.assertIn('Queixa Principal:\nDor de cabe\u00e7a', organized)
                self.assertRegex(
                    organized,
                    r'Hist\u00f3rico familiar:\n(?:Fam\u00edlia )?[Cc]om dor de cabe\u00e7a',
                )
                self.assertIn('Medicamentos:\nNovalgina quatro vezes ao dia', organized)

class ProfSaudeScheduleMappingTest(unittest.TestCase):
    def test_maps_legacy_schedule_columns(self):
        layout = {
            'fields': {
                'nome': 'nomed',
                'segunda_ativo': 'seg',
                'segunda_inicio': 'iseg',
                'segunda_termino': 'fseg',
                'terca_ativo': 'terc',
                'terca_inicio': 'iter',
                'terca_termino': 'fter',
            }
        }
        values = prof_saude_api._prof_data({
            'nome': 'Dra. Teste',
            'segunda_inicio': '08:00',
            'segunda_termino': '12:00',
            'terca_inicio': '',
            'terca_termino': '',
        }, layout)
        self.assertEqual(values['nomed'], 'Dra. Teste')
        self.assertEqual(values['seg'], 'S')
        self.assertEqual(values['iseg'], '08:00')
        self.assertEqual(values['fseg'], '12:00')
        self.assertIsNone(values['terc'])

    def test_strips_legacy_char_values_for_time_inputs(self):
        row = prof_saude_api._row_dict(
            ['segunda_inicio', 'segunda_termino'],
            ('08:00 ', '12:00 '),
        )
        self.assertEqual(row['segunda_inicio'], '08:00')
        self.assertEqual(row['segunda_termino'], '12:00')

    def test_update_professional_falls_back_to_name_when_record_id_misses(self):
        class Repository:
            def __init__(self):
                self.calls = []

            def update(self, record_id, values):
                self.calls.append((record_id, values))
                return str(record_id) == '12'

        repository = Repository()
        original_repository = prof_saude_api._repository
        original_find = prof_saude_api._find_professional_id_by_name
        prof_saude_api._repository = lambda layout: repository
        prof_saude_api._find_professional_id_by_name = lambda layout, name: 12 if name == 'Dra Tania' else None
        try:
            updated_id = prof_saude_api._update_profissional(
                {
                    'fields': {'nome': 'nomed'},
                    'id_column': 'codmed',
                    'tenant_column': 'codclin',
                    'table': 'nomed',
                },
                '5',
                {'nomed': 'Dra Tania'},
            )
        finally:
            prof_saude_api._repository = original_repository
            prof_saude_api._find_professional_id_by_name = original_find

        self.assertEqual(updated_id, 12)
        self.assertEqual([str(call[0]) for call in repository.calls], ['5', '12'])


class ProfSaudeReceituarioMappingTest(unittest.TestCase):
    def test_professional_create_uses_same_transaction_for_complements(self):
        source = __import__('inspect').getsource(prof_saude_api.create_profissional)
        self.assertIn('_insert_profissional(cursor, layout, item)', source)
        self.assertNotIn('_create_profissional(layout, item)', source)

    def test_does_not_create_empty_prescription_preferences(self):
        class Cursor:
            def __init__(self):
                self.executions = []

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return None

        layout = {
            'table': 'prefere', 'id_column': 'codmed', 'tenant_column': 'codclin',
            'fields': {'tit1': 'nomeclin', 'tit2': 'tit2'},
        }
        cursor = Cursor()
        original_layout = prof_saude_api._prefere_layout
        prof_saude_api._prefere_layout = lambda ignored_cursor: layout
        app = Flask(__name__)
        app.secret_key = 'test'
        try:
            with app.test_request_context('/'):
                from flask import session
                session['idempresa'] = 2
                prof_saude_api._upsert_prefere(cursor, '7', {'nome': 'Dr Demo'})
        finally:
            prof_saude_api._prefere_layout = original_layout
        self.assertEqual(len(cursor.executions), 1)

    def test_uses_professional_name_when_new_preferences_have_no_title(self):
        class Cursor:
            def __init__(self):
                self.executions = []
                self.rowcount = 1

            def execute(self, statement, parameters=None):
                self.executions.append((statement, parameters))

            def fetchone(self):
                return None

        layout = {
            'table': 'prefere', 'id_column': 'codmed', 'tenant_column': 'codclin',
            'fields': {'tit1': 'nomeclin', 'tit2': 'tit2'},
        }
        cursor = Cursor()
        original_layout = prof_saude_api._prefere_layout
        prof_saude_api._prefere_layout = lambda ignored_cursor: layout
        app = Flask(__name__)
        app.secret_key = 'test'
        try:
            with app.test_request_context('/'):
                from flask import session
                session['idempresa'] = 2
                prof_saude_api._upsert_prefere(
                    cursor, '7', {'nome': 'Dr Demo', 'tit2': 'Especialista'}
                )
        finally:
            prof_saude_api._prefere_layout = original_layout
        insert_parameters = cursor.executions[-1][1]
        self.assertIn('Dr Demo', insert_parameters)
        self.assertIn('Especialista', insert_parameters)

    def test_uses_actual_prefere_title_columns(self):
        self.assertEqual(prof_saude_api.PREFERE_FIELD_CANDIDATES['tit1'], ('nomeclin',))
        self.assertEqual(prof_saude_api.PREFERE_FIELD_CANDIDATES['tit2'], ('tit2',))
        self.assertEqual(prof_saude_api.PREFERE_FIELD_CANDIDATES['tit3'], ('tit3',))

    def test_maps_receituario_fields_to_prefere_columns(self):
        layout = {
            'fields': {
                'tit1': 'nomeclin',
                'tit2': 'tit2',
                'tit3': 'tit3',
                'rod1': 'rod1',
                'rod2': 'rod2',
                'cidade_receita': 'cidade',
            }
        }
        values = prof_saude_api._prefere_values({
            'nome': 'Dra. Teste',
            'tit1': 'Titulo 1',
            'tit2': 'Titulo 2',
            'tit3': 'Titulo 3',
            'rod1': 'Rodape 1',
            'rod2': 'Rodape 2',
            'cidade_receita': 'Niteroi',
        }, layout)
        self.assertEqual(values['nomeclin'], 'Titulo 1')
        self.assertEqual(values['tit2'], 'Titulo 2')
        self.assertEqual(values['tit3'], 'Titulo 3')
        self.assertEqual(values['rod1'], 'Rodape 1')
        self.assertEqual(values['rod2'], 'Rodape 2')
        self.assertEqual(values['cidade'], 'Niteroi')

    def test_accepts_receituario_fields_with_60_characters(self):
        fields = {'tit1': 'nomeclin', 'tit2': 'tit2', 'tit3': 'tit3', 'rod1': 'rod1', 'rod2': 'rod2'}
        values = prof_saude_api._prefere_values(
            {field: 'x' * 60 for field in fields},
            {'fields': fields},
        )
        self.assertTrue(all(value == 'x' * 60 for value in values.values()))

    def test_rejects_receituario_fields_over_60_characters(self):
        for field, column in {'tit2': 'tit2', 'tit3': 'tit3', 'rod1': 'rod1', 'rod2': 'rod2'}.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                prof_saude_api._prefere_values({field: 'x' * 61}, {'fields': {field: column}})

    def test_builds_anamnese_texto_key_from_professional_id(self):
        self.assertEqual(prof_saude_api._texto_key('07'), 'ANAMNESE 07')
        self.assertLessEqual(len(prof_saude_api._texto_key('123456789012345678901234567890')), 30)

    def test_requires_anamnese_nome_when_text_is_filled(self):
        with self.assertRaises(ValueError):
            prof_saude_api._upsert_texto(
                cursor=None,
                record_id='07',
                data={'anamnese_nome': '', 'anamnese_texto': 'Texto'},
            )

    def test_maps_padrao_type_to_atalho(self):
        self.assertEqual(
            prof_saude_api._anamnese_values({'nome': 'Receita 1', 'texto': 'Uso oral', 'atalho': 'r'}),
            ('Receita 1', 'Uso oral', 'R'),
        )
        self.assertEqual(
            prof_saude_api._anamnese_values({'nome': 'Curativo', 'texto': 'Procedimento', 'atalho': 'p'}),
            ('Curativo', 'Procedimento', 'P'),
        )
        self.assertEqual(
            prof_saude_api._anamnese_values({'nome': 'Hemograma', 'texto': 'Exame', 'atalho': 'x'}),
            ('Hemograma', 'Exame', 'X'),
        )
        self.assertEqual(
            prof_saude_api._anamnese_values({'nome': 'E-mail agenda', 'texto': 'Mensagem', 'atalho': 'e'}),
            ('E-mail agenda', 'Mensagem', 'E'),
        )
        self.assertEqual(
            prof_saude_api._anamnese_values({'nome': 'WhatsApp agenda', 'texto': 'Mensagem', 'atalho': 'z'}),
            ('WhatsApp agenda', 'Mensagem', 'Z'),
        )

    def test_rejects_invalid_padrao_type(self):
        with self.assertRaises(ValueError):
            prof_saude_api._anamnese_values({'nome': 'Teste', 'texto': 'Texto', 'atalho': 'Q'})


if __name__ == '__main__':
    unittest.main()
