import os

# Tipo de banco padrão: 'firebird' ou 'postgres'
DB_TYPE = os.environ.get('MEDSOFT_DB_TYPE', 'postgres').lower()

# Firebird (fdb) defaults
FB_HOST = os.environ.get('MEDSOFT_FB_HOST', '24.152.36.178')
FB_PORT = int(os.environ.get('MEDSOFT_FB_PORT', '3050'))
FB_USER = os.environ.get('MEDSOFT_FB_USER', 'sysdba')
FB_PASS = os.environ.get('MEDSOFT_FB_PASS', 'masterkey')
if os.name == 'nt':
    FB_BASE_DIR = os.environ.get('MEDSOFT_FB_BASE_DIR', r'C:\JTN\Medsoft\2-Migracao\BD')
else:
    FB_BASE_DIR = os.environ.get('MEDSOFT_FB_BASE_DIR', '/opt/medsoft/bd')

# PostgreSQL defaults
PG_HOST = os.environ.get('MEDSOFT_PG_HOST', '177.85.99.66')
PG_PORT = int(os.environ.get('MEDSOFT_PG_PORT', '5432'))
PG_DB = os.environ.get('MEDSOFT_PG_DB', 'medsoft_medmigra')
PG_USER = os.environ.get('MEDSOFT_PG_USER', 'medsoft_master')
PG_PASS = os.environ.get('MEDSOFT_PG_PASS', 'Alemanha2025@')

# Secret
SECRET_KEY = os.environ.get('MEDSOFT_SECRET_KEY', 'medsoft-umasecret-temporaria')

# SMTP / Email settings (opcional — se não configurado, a aplicação mostrará link de debug)
SMTP_HOST = os.environ.get('MEDSOFT_SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('MEDSOFT_SMTP_PORT', '0'))
SMTP_USER = os.environ.get('MEDSOFT_SMTP_USER', '')
SMTP_PASS = os.environ.get('MEDSOFT_SMTP_PASS', '')
# Use TLS (STARTTLS) or SSL (smtplib.SMTP_SSL). Prefer TLS when possible.
SMTP_USE_TLS = os.environ.get('MEDSOFT_SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
SMTP_USE_SSL = os.environ.get('MEDSOFT_SMTP_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
SMTP_FROM = os.environ.get('MEDSOFT_SMTP_FROM', 'no-reply@medsoft.com.br')


def validate_config():
    """Valida as variáveis de ambiente necessárias conforme `DB_TYPE`.

    Retorna uma lista de mensagens de erro (vazia se tudo ok).
    """
    errors = []
    db_type = DB_TYPE
    if db_type in ('postgres', 'pg'):
        if not PG_HOST:
            errors.append('MEDSOFT_PG_HOST is required for Postgres')
        if not PG_DB:
            errors.append('MEDSOFT_PG_DB is required for Postgres')
        if not PG_USER:
            errors.append('MEDSOFT_PG_USER is required for Postgres')
        if not PG_PASS:
            errors.append('MEDSOFT_PG_PASS is required for Postgres')
    else:
        # Firebird defaults
        if not FB_HOST:
            errors.append('MEDSOFT_FB_HOST is required for Firebird')
        if not FB_BASE_DIR:
            errors.append('MEDSOFT_FB_BASE_DIR is required for Firebird')
        if not FB_USER:
            errors.append('MEDSOFT_FB_USER is required for Firebird')
        if not FB_PASS:
            errors.append('MEDSOFT_FB_PASS is required for Firebird')

    # SECRET
    # Em ambientes de desenvolvimento permitimos o valor padrão, mas emitimos um aviso.
    if not SECRET_KEY or SECRET_KEY == 'medsoft-umasecret-temporaria':
        print('Warning: MEDSOFT_SECRET_KEY not set. Using development default; set MEDSOFT_SECRET_KEY for production.')

    # SMTP is optional; if partially configured, warn the developer
    smtp_fields = [SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS]
    if any(smtp_fields) and not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS]):
        errors.append('SMTP partially configured: set MEDSOFT_SMTP_HOST, _PORT, _USER and _PASS or leave all empty')

    return errors
