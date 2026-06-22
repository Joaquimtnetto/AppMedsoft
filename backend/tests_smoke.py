"""
Smoke tests simples para os endpoints principais do backend.

Uso:
  python backend/tests_smoke.py

Dependências:
  pip install requests

Edite as variáveis `BASE_URL`, `DB_PATH`, `USER`, `PASS` conforme seu ambiente.
"""
import requests
import os
import sys

BASE_URL = os.environ.get('MEDSOFT_BASE_URL', 'http://localhost:8072')
DB_PATH = os.environ.get('MEDSOFT_DB_PATH', os.environ.get('MEDSOFT_PG_DB', 'medsoft_medmigra'))
USER = os.environ.get('MEDSOFT_USER', 'seu_usuario')
PASS = os.environ.get('MEDSOFT_PASS', 'sua_senha')

def post(path, json=None, headers=None):
    url = BASE_URL.rstrip('/') + path
    try:
        r = requests.post(url, json=json, headers=headers, timeout=10)
        print(f"POST {url} -> {r.status_code}")
        try:
            print(r.json())
        except Exception:
            print(r.text)
        return r
    except Exception as e:
        print(f"Erro ao chamar {url}: {e}")
        return None

def test_login():
    print('\n== Teste: login ==')
    data = { 'nome': USER, 'senha': PASS }
    return post('/api/login', json=data)

def test_consulta_paciente(db_path):
    print('\n== Teste: consulta-paciente ==')
    headers = { 'X-DB-PATH': db_path }
    data = { 'termo': 'JOÃO', 'nome_medico': '%' }
    return post('/api/consulta-paciente', json=data, headers=headers)

def test_consultas_paciente(db_path):
    print('\n== Teste: consultas-paciente ==')
    headers = { 'X-DB-PATH': db_path }
    data = { 'codpac': 123 }
    return post('/api/consultas-paciente', json=data, headers=headers)

def test_agenda(db_path):
    print('\n== Teste: agenda ==')
    headers = { 'X-DB-PATH': db_path }
    data = { 'data': '2026-06-17' }
    return post('/api/agenda', json=data, headers=headers)

def main():
    print('Base URL:', BASE_URL)
    r = test_login()
    # Use db_path from login response if disponível
    db_path = DB_PATH
    if r and r.ok:
        try:
            j = r.json()
            if 'db_path' in j and j['db_path']:
                db_path = j['db_path']
                print('Usando db_path retornado pelo login:', db_path)
        except Exception:
            pass
    test_consulta_paciente(db_path)
    test_consultas_paciente(db_path)
    test_agenda(db_path)

if __name__ == '__main__':
    main()
