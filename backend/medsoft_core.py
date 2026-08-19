import fdb
import os
from typing import Optional
import config


class DBConnectionError(Exception):
    """Exceção para problemas de conexão/permissão no banco com mensagem amigável."""
    pass


def get_postgres_connection(host: str, database: str, user: str, password: str, port: int = 5432):
    """Retorna uma conexão psycopg2 para um banco PostgreSQL.

    A função importa psycopg2 apenas quando chamada para evitar dependência obrigatória
    para quem usa somente Firebird.
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

def get_db_connection(db_path=None):
    """Retorna uma conexão com o banco configurado.

    Se `MEDSOFT_DB_TYPE` for `postgres` usa `psycopg2` (via `get_postgres_connection`).
    Caso contrário usa Firebird via `fdb`.
    """
    db_type = os.environ.get('MEDSOFT_DB_TYPE', config.DB_TYPE).lower()
    if db_type in ('postgres', 'pg'):
        # Para Postgres, db_path pode conter o nome do banco a usar
        database = db_path if db_path else os.environ.get('MEDSOFT_PG_DB', config.PG_DB)
        host = os.environ.get('MEDSOFT_PG_HOST', config.PG_HOST)
        user = os.environ.get('MEDSOFT_PG_USER', config.PG_USER)
        password = os.environ.get('MEDSOFT_PG_PASS', config.PG_PASS)
        port = int(os.environ.get('MEDSOFT_PG_PORT', config.PG_PORT))
        try:
            return get_postgres_connection(host=host, database=database, user=user, password=password, port=port)
        except DBConnectionError:
            raise
        except Exception as e:
            raise DBConnectionError(f'Erro ao conectar ao PostgreSQL: {e}') from e
    # Firebird (padrão)
    base_dir = os.environ.get('MEDSOFT_FB_BASE_DIR', config.FB_BASE_DIR)
    if not db_path:
        db_path = 'medicoraiz.fdb'
    if not os.path.isabs(db_path):
        db_path = os.path.join(base_dir, db_path)
    db_path = db_path.replace("\\", "/")
    cfg = {
        'host': os.environ.get('MEDSOFT_FB_HOST', config.FB_HOST),
        'database': db_path,
        'user': os.environ.get('MEDSOFT_FB_USER', config.FB_USER),
        'password': os.environ.get('MEDSOFT_FB_PASS', config.FB_PASS),
        'port': int(os.environ.get('MEDSOFT_FB_PORT', config.FB_PORT)),
    }
    try:
        return fdb.connect(**cfg)
    except Exception as e:
        msg = str(e)
        if 'unable to complete network request' in msg.lower() or 'connection' in msg.lower():
            raise DBConnectionError('Não foi possível conectar ao servidor Firebird: verifique rede/host/porta.') from e
        if 'unable to open database' in msg.lower():
            raise DBConnectionError('Arquivo de banco não encontrado ou sem permissão de leitura.') from e
        raise DBConnectionError(f'Erro ao conectar ao Firebird: {msg}') from e

