"""Regressão da busca por situação, sem acesso ao banco de produção."""
import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock


class SQLText(str):
    def format(self, *args):
        return SQLText(str(self).format(*args))

    def join(self, items):
        return SQLText(str(self).join(items))


class PatientStatusTests(unittest.TestCase):
    def run_search(self, status=None, active_column=True):
        source = Path(__file__).with_name('consulta_paciente.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'consulta_paciente')
        func.decorator_list = []
        data = {'termo': 'Mariana', 'campo': 'nome'}
        if status is not None:
            data['situacao'] = status
        cursor = Mock()
        cursor.fetchall.return_value = []
        connection = Mock()
        connection.cursor.return_value = cursor
        columns = {'nomecli': 'nomecli', 'codcli': 'codcli', 'codclin': 'codclin'}
        if active_column:
            columns['ativo'] = 'ativo'
        namespace = {
            'request': types.SimpleNamespace(json=data), 'jsonify': lambda value: value,
            'session': {}, 'get_db_connection': lambda _: connection,
            '_fetch_columns': lambda _: columns,
            '_pick': lambda cols, candidates: next((cols[c] for c in candidates if c in cols), None),
            'BASE_FIELD_CANDIDATES': {k: (k,) for k in ['nomecli', 'codcli', 'codclin']},
            'FIELD_CANDIDATES': {'ativo': ('ativo',), 'nascimento': ('datanasc_',)},
            '_select_base_optional': lambda *args: SQLText('NULL'),
            '_select_optional': lambda *args: SQLText('NULL'),
            '_phone_expression': lambda _: SQLText('NULL'),
            'sql': types.SimpleNamespace(SQL=SQLText, Identifier=lambda value: SQLText('"' + value + '"')),
            'current_company_id': lambda: 7, 'logging': Mock(), 'DBConnectionError': ConnectionError,
        }
        exec(compile(ast.Module(body=[func], type_ignores=[]), '<patient-search>', 'exec'), namespace)
        response = namespace['consulta_paciente']()
        return cursor, response

    def test_default_keeps_active_only(self):
        cursor, _ = self.run_search()
        query, params = cursor.execute.call_args.args
        self.assertIn("NOT IN ('n'", query)
        self.assertIn('"codclin" = %s', query)
        self.assertEqual(params, (7, 'Mariana%'))

    def test_inactive_keeps_clinic_and_name_scope(self):
        cursor, _ = self.run_search('inativos')
        query, params = cursor.execute.call_args.args
        self.assertIn("IN ('n'", query)
        self.assertNotIn('NOT IN', query)
        self.assertIn('"codclin" = %s', query)
        self.assertIn('"nomecli" ILIKE %s', query)
        self.assertEqual(params, (7, 'Mariana%'))

    def test_all_removes_only_status_filter(self):
        cursor, _ = self.run_search('todos')
        query, params = cursor.execute.call_args.args
        self.assertNotIn("IN ('n'", query)
        self.assertIn('AND TRUE', query)
        self.assertEqual(params, (7, 'Mariana%'))

    def test_invalid_status_rejected_before_database(self):
        cursor, response = self.run_search('invalido')
        self.assertEqual(response[1], 400)
        cursor.execute.assert_not_called()

    def test_without_status_column_no_inactive_results(self):
        cursor, _ = self.run_search('inativos', active_column=False)
        self.assertIn('AND FALSE', cursor.execute.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
