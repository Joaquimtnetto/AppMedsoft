from flask import session


TENANT_COLUMN = 'codclin'


def current_company_id():
    """Retorna a empresa autenticada; nunca aceita o código enviado pelo cliente."""
    value = session.get('idempresa')
    legacy_value = session.get('codclin')
    if value not in (None, '') and legacy_value not in (None, ''):
        try:
            if int(value) != int(legacy_value):
                raise ValueError('Empresa da sessao inconsistente. Faca login novamente.')
        except (TypeError, ValueError) as exc:
            raise ValueError('Empresa da sessao inconsistente. Faca login novamente.') from exc
    if value in (None, ''):
        value = legacy_value
    try:
        company_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Empresa da sessão não identificada. Faça login novamente.') from exc
    if company_id <= 0:
        raise ValueError('Empresa da sessão não identificada. Faça login novamente.')
    return company_id
