# Manual do Desenvolvedor - Parte 1

## medsoft_app.py

### Objetivo
Arquivo principal da aplicação responsável por iniciar o Flask, registrar rotas e configurar a aplicação.

### Imports identificados
- `agenda`
- `agenda_api`
- `build_info`
- `clinica_api`
- `config`
- `configuracao_api`
- `consulta_paciente`
- `consultas_routes`
- `datetime`
- `email.message`
- `empresa_api`
- `exame_api`
- `faturamento_api`
- `flask`
- `itsdangerous`

### Classes
- Nenhuma classe identificada.

### Funções
- `get_user_empresa_db()`
- `resource_path()`
- `enforce_utf8_response()`
- `handle_unexpected_error()`
- `_has_valid_session()`
- `require_authentication()`
- `send_email()`
- `consultas_paciente_html()`
- `login()`
- `logout()`
- `change_password()`
- `esqueci_senha_form()`
- `esqueci_senha_post()`
- `reset_password_form()`
- `reset_password_post()`
- `index()`
- `principal()`
- `menu()`
- `consulta_paciente_html()`
- `plano_html()`
- `prof_saude_html()`
- `clinica_html()`
- `anamnese_html()`
- `usuario_html()`
- `procedimentos_html()`
- `faturamento_html()`
- `help_html()`
- `configuracao_html()`
- `config_email_html()`
- `config_whatsapp_html()`
- `perfil_html()`
- `empresa_html()`

### Recomendações
- Adicionar docstrings.
- Documentar parâmetros e retornos.
- Manter funções pequenas e reutilizáveis.

---

## config.py

### Objetivo
Centraliza configurações da aplicação e acesso a parâmetros do ambiente.

### Imports identificados
- `os`

### Classes
- Nenhuma classe identificada.

### Funções
- `validate_config()`

### Recomendações
- Adicionar docstrings.
- Documentar parâmetros e retornos.
- Manter funções pequenas e reutilizáveis.

---

## medsoft_core.py

### Objetivo
Contém funcionalidades compartilhadas utilizadas por diversos módulos.

### Imports identificados
- `config`
- `os`
- `psycopg2`

### Classes
- `DBConnectionError`

### Funções
- `_client_encoding()`
- `get_postgres_connection()`
- `get_db_connection()`

### Recomendações
- Adicionar docstrings.
- Documentar parâmetros e retornos.
- Manter funções pequenas e reutilizáveis.

---

## tenant_context.py

### Objetivo
Implementa o contexto de tenant para isolamento entre empresas.

### Imports identificados
- `flask`

### Classes
- Nenhuma classe identificada.

### Funções
- `current_company_id()`

### Recomendações
- Adicionar docstrings.
- Documentar parâmetros e retornos.
- Manter funções pequenas e reutilizáveis.

---
