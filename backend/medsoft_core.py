import os
import config


class DBConnectionError(Exception):
    """Exceção para problemas de conexão/permissão no banco com mensagem amigável."""
    pass


def get_postgres_connection(host: str, database: str, user: str, password: str, port: int = 5432):
    """Retorna uma conexão psycopg2 para um banco PostgreSQL.

    O driver é importado apenas quando a conexão é criada para produzir uma mensagem
    clara caso a dependência não esteja instalada.
    """
    try:
        import psycopg2
        from psycopg2 import OperationalError
    except Exception as e:
        raise DBConnectionError('Dependência psycopg2 ausente. Rode `pip install psycopg2-binary`.') from e

    try:
        conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
        return conn
    except Exception as e:
        msg = str(e)
        # Mapeamento simples de mensagens para respostas amigáveis
        if 'password authentication failed' in msg.lower():
            raise DBConnectionError('Autenticação falhou: usuário ou senha inválidos.') from e
        if 'permission denied' in msg.lower() or 'insufficient privilege' in msg.lower():
            raise DBConnectionError('Permissão negada: o usuário não tem privilégios suficientes no banco.') from e
        if 'could not connect to server' in msg.lower() or 'timeout' in msg.lower():
            raise DBConnectionError('Não foi possível conectar ao servidor do banco: verifique rede/host/porta.') from e
        # Genérica
        raise DBConnectionError(f'Erro ao conectar ao PostgreSQL: {msg}') from e

def get_db_connection(database=None):
    """Retorna uma conexão PostgreSQL usando a configuração da aplicação."""
    database = database or os.environ.get('MEDSOFT_PG_DB', config.PG_DB)
    host = os.environ.get('MEDSOFT_PG_HOST', config.PG_HOST)
    user = os.environ.get('MEDSOFT_PG_USER', config.PG_USER)
    password = os.environ.get('MEDSOFT_PG_PASS', config.PG_PASS)
    port = int(os.environ.get('MEDSOFT_PG_PORT', config.PG_PORT))
    try:
        return get_postgres_connection(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
        )
    except DBConnectionError:
        raise
    except Exception as e:
        raise DBConnectionError(f'Erro ao conectar ao PostgreSQL: {e}') from e

