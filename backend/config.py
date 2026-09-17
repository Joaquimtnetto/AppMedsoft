import os
from pathlib import Path
import secrets
import sys
from datetime import timedelta

# PostgreSQL defaults
PG_HOST = os.environ.get('MEDSOFT_PG_HOST', '177.85.99.66')
PG_PORT = int(os.environ.get('MEDSOFT_PG_PORT', '5432'))
PG_DB = os.environ.get('MEDSOFT_PG_DB', 'medsoft_medmigra')
PG_USER = os.environ.get('MEDSOFT_PG_USER', 'medsoft_master')
PG_PASS = os.environ.get('MEDSOFT_PG_PASS', 'Alemanha2025@')
PG_CLIENT_ENCODING = os.environ.get('MEDSOFT_PG_CLIENT_ENCODING', '')

# Secret
_SECRET_KEY_ENV = os.environ.get('MEDSOFT_SECRET_KEY')


def _persistent_secret_key():
    if _SECRET_KEY_ENV:
        return _SECRET_KEY_ENV, False
    if getattr(sys, 'frozen', False):
        default_file = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'MedSoft' / 'secret.key'
    else:
        default_file = Path(__file__).resolve().parent.parent / '.medsoft_secret_key'
    secret_file = Path(os.environ.get('MEDSOFT_SECRET_FILE') or default_file)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        if secret_file.exists():
            stored = secret_file.read_text(encoding='utf-8').strip()
            if len(stored) >= 32:
                return stored, False
        generated = secrets.token_hex(32)
        secret_file.write_text(generated, encoding='utf-8')
        return generated, False
    except OSError:
        return secrets.token_hex(32), True


SECRET_KEY, USING_GENERATED_SECRET_KEY = _persistent_secret_key()
SESSION_LIFETIME = timedelta(
    minutes=max(1, int(os.environ.get('MEDSOFT_SESSION_MINUTES', '720')))
)
PUBLIC_URL = os.environ.get('MEDSOFT_PUBLIC_URL', '').rstrip('/')

# SMTP / Email settings (opcional — se não configurado, a aplicação mostrará link de debug)
SMTP_HOST = os.environ.get('MEDSOFT_SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('MEDSOFT_SMTP_PORT', '0'))
SMTP_USER = os.environ.get('MEDSOFT_SMTP_USER', '')
SMTP_PASS = os.environ.get('MEDSOFT_SMTP_PASS', '')
# Use TLS (STARTTLS) or SSL (smtplib.SMTP_SSL). Prefer TLS when possible.
SMTP_USE_TLS = os.environ.get('MEDSOFT_SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
SMTP_USE_SSL = os.environ.get('MEDSOFT_SMTP_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
SMTP_FROM = os.environ.get('MEDSOFT_SMTP_FROM', 'no-reply@medsoft.com.br')

# WhatsApp Business Cloud API. O modelo aprovado deve receber, nesta ordem:
# nome do paciente, data, hora e profissional de saúde.
WHATSAPP_SENDER_NUMBER = os.environ.get('MEDSOFT_WHATSAPP_SENDER_NUMBER', '5521986496127')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('MEDSOFT_WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_ACCESS_TOKEN = os.environ.get('MEDSOFT_WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_API_VERSION = os.environ.get('MEDSOFT_WHATSAPP_API_VERSION', '')
WHATSAPP_TEMPLATE_NAME = os.environ.get('MEDSOFT_WHATSAPP_TEMPLATE_NAME', '')
WHATSAPP_TEMPLATE_LANGUAGE = os.environ.get('MEDSOFT_WHATSAPP_TEMPLATE_LANGUAGE', 'pt_BR')

# Serviço local Baileys usado pelo modo simplificado com QR Code.
BAILEYS_SERVICE_URL = os.environ.get('MEDSOFT_BAILEYS_URL', 'http://127.0.0.1:3001').rstrip('/')
BAILEYS_SERVICE_TOKEN = os.environ.get(
    'MEDSOFT_BAILEYS_TOKEN',
    'r4n0n9iHK2b13XOfgOzGz7pO-s6Zt8zZd8zro5DlwuY',
)

def validate_config():
    """Valida as variáveis de ambiente necessárias.

    Retorna uma lista de mensagens de erro (vazia se tudo ok).
    """
    errors = []
    if not PG_HOST:
        errors.append('MEDSOFT_PG_HOST is required for Postgres')
    if not PG_DB:
        errors.append('MEDSOFT_PG_DB is required for Postgres')
    if not PG_USER:
        errors.append('MEDSOFT_PG_USER is required for Postgres')
    if not PG_PASS:
        errors.append('MEDSOFT_PG_PASS is required for Postgres')

    # SECRET
    # Só usa chave temporária se não for possível persistir a chave localmente.
    if USING_GENERATED_SECRET_KEY:
        print('Warning: MEDSOFT_SECRET_KEY not set. A temporary startup key was generated.')

    # SMTP is optional; if partially configured, warn the developer
    smtp_fields = [SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS]
    if any(smtp_fields) and not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS]):
        errors.append('SMTP partially configured: set MEDSOFT_SMTP_HOST, _PORT, _USER and _PASS or leave all empty')

    whatsapp_fields = [
        WHATSAPP_PHONE_NUMBER_ID,
        WHATSAPP_ACCESS_TOKEN,
        WHATSAPP_API_VERSION,
        WHATSAPP_TEMPLATE_NAME,
    ]
    if any(whatsapp_fields) and not all(whatsapp_fields):
        errors.append(
            'WhatsApp partially configured: set MEDSOFT_WHATSAPP_PHONE_NUMBER_ID, '
            '_ACCESS_TOKEN, _API_VERSION and _TEMPLATE_NAME or leave all empty'
        )

    return errors
