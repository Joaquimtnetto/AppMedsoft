import psycopg2
import sys

HOST='177.85.99.66'
DB='medsoft_medmigra'
USER='medsoft_migra'
PASS='Alemanha2025@'
PORT=5432

try:
    conn = psycopg2.connect(host=HOST, database=DB, user=USER, password=PASS, port=PORT)
    cur = conn.cursor()
    cur.execute("SELECT has_table_privilege(current_user, 'ic_usuario_geral', 'select'), current_user")
    print('result:', cur.fetchone())
    cur.execute("SELECT has_schema_privilege(current_user, 'public', 'usage')")
    print('schema_usage:', cur.fetchone())
    cur.close()
    conn.close()
except Exception as e:
    print('error:', e)
    sys.exit(1)
