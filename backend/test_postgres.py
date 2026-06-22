"""
Script de teste para validar conexão com PostgreSQL usando `get_postgres_connection`.

Uso:
  python backend/test_postgres.py

Você pode sobrescrever as credenciais via variáveis de ambiente:
  MEDSOFT_PG_HOST, MEDSOFT_PG_DB, MEDSOFT_PG_USER, MEDSOFT_PG_PASS, MEDSOFT_PG_PORT

Retorna código 0 em sucesso, 1 em falha.
"""
import os
import sys
from medsoft_core import get_postgres_connection

DEFAULTS = {
    'host': '177.85.99.66',
    'database': 'medsoft_medmigra',
    'user': 'medsoft_master',
    'password': 'Alemanha2025@',
    'port': 5432,
}

def main():
    host = os.environ.get('MEDSOFT_PG_HOST', DEFAULTS['host'])
    database = os.environ.get('MEDSOFT_PG_DB', DEFAULTS['database'])
    user = os.environ.get('MEDSOFT_PG_USER', DEFAULTS['user'])
    password = os.environ.get('MEDSOFT_PG_PASS', DEFAULTS['password'])
    port = int(os.environ.get('MEDSOFT_PG_PORT', DEFAULTS['port']))

    print('Testando conexão PostgreSQL:')
    print(f' host={host} db={database} user={user} port={port}')
    try:
        conn = get_postgres_connection(host=host, database=database, user=user, password=password, port=port)
    except Exception as e:
        print('Falha ao criar conexão:', e)
        sys.exit(1)

    try:
        cur = conn.cursor()
        cur.execute('SELECT version()')
        ver = cur.fetchone()
        print('Conexão OK — versão:', ver)
        cur.close()
        conn.close()
        sys.exit(0)
    except Exception as e:
        print('Erro executando query:', e)
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(1)

if __name__ == '__main__':
    main()
