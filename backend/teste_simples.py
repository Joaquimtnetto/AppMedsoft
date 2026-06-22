from medsoft_core import get_db_connection


try:
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT 1')
    print(cursor.fetchone())
    connection.close()
except Exception as exc:
    print(f'Erro ao testar a conexão: {exc}')
