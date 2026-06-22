import unittest
from contextlib import contextmanager

from flask import Flask

import agenda_api
from crud_repository import CrudRepository


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
        self.app = Flask(__name__)
        self.app.secret_key = 'test'
        self.app.register_blueprint(agenda_api.agenda_api_bp)
        self.repository = FakeAgendaRepository()
        self.original_repository = agenda_api.agenda_repository
        agenda_api.agenda_repository = self.repository
        self.client = self.app.test_client()
        self.payload = {
            'data': '2026-06-22',
            'hora': '09:30',
            'paciente': 'Paciente Teste',
            'telefone': '(11)2222-3333',
            'plano': 'Plano',
            'procedimento': 'Consulta',
        }

    def tearDown(self):
        agenda_api.agenda_repository = self.original_repository

    def test_create_update_and_delete_endpoints(self):
        self.assertEqual(self.client.post('/api/agenda/itens', json=self.payload).status_code, 201)
        self.assertEqual(self.client.put('/api/agenda/itens/15', json=self.payload).status_code, 200)
        self.assertEqual(self.client.delete('/api/agenda/itens/15').status_code, 200)
        self.assertEqual([call[0] for call in self.repository.calls], ['create', 'update', 'delete'])
        saved = self.repository.calls[0][1]
        self.assertEqual(saved['horacons'], '09:30')
        self.assertEqual(saved['telefone'], '(11)2222-3333')

    def test_required_patient_validation(self):
        payload = dict(self.payload, paciente='')
        response = self.client.post('/api/agenda/itens', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_phone_validation(self):
        payload = dict(self.payload, telefone='119999')
        response = self.client.post('/api/agenda/itens', json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('(99)9999-9999', response.get_json()['message'])


if __name__ == '__main__':
    unittest.main()
