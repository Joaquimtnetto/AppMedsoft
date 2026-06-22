# Documentação Consolidada — backend pMobile (Medsoft)

Este documento reúne a visão geral, instruções de execução, descrição de endpoints e resumo por arquivo do backend.

---

## 1. Visão geral
- Propósito: Backend Flask que fornece autenticação, busca de pacientes, histórico de consultas e API de agenda.
- Arquivo principal que inicia a aplicação: [backend/medsoft_app.py](backend/medsoft_app.py#L1-L400).
- A aplicação usa PostgreSQL via `psycopg2`.

## 2. Dependências
- Veja [backend/requirements.txt](backend/requirements.txt#L1-L20): `flask`, `psycopg2-binary`.
- Instalação:

```bash
python -m pip install -r backend/requirements.txt
```

## 3. Como executar
1. Garanta que as variáveis de ambiente estejam configuradas (use `backend/.env.example` como referência).
  - Instale `psycopg2-binary` para Postgres:

```bash
python -m pip install psycopg2-binary
```
2. Execute:

```bash
python backend/medsoft_app.py
```

3. Acesse `http://localhost:8072/`.

---

## 4. Endpoints principais (exemplos resumidos)

- `POST /api/login`
  - Body: `{"nome":"usuario","senha":"senha"}`
  - Retorna: `{ success, nome, idusuario, idempresa, db_path, empresa_nome, nome_medico }`

- `POST /api/change-password`
  - Body: `{"nome":"...","senhaAtual":"...","novaSenha":"..."}`

-- `POST /api/consulta-paciente`
  - Header: opcional quando usando Postgres (padrão). Veja `ENDPOINTS.md`.
  - Body: `{"termo":"nome","nome_medico":"DR. SILVA"}`
  - Retorna: `{ success, pacientes: [...] }`

- `POST /api/consultas-paciente`
  - Header: `X-DB-PATH`
  - Body: `{"codpac": 123}`
  - Retorna: `{ success, consultas: [...] }`

- `POST /api/agenda`
  - Header: `X-DB-PATH`
  - Body: `{"data":"YYYY-MM-DD"}`

Observações: exemplos completos com `curl` e instruções de Postman estão em `backend/ENDPOINTS.md`.

---

## 8. Conectando ao PostgreSQL

Se você precisa conectar a um banco PostgreSQL (ex.: migração ou relatórios), adicione as dependências e use a função `get_postgres_connection` de `medsoft_core.py`.

Exemplo de configuração (credenciais fornecidas):

```python
from medsoft_core import get_postgres_connection

conn = get_postgres_connection(
  host='177.85.99.66',
  database='medsoft_medmigra',
  user='medsoft_postgres',
  password='Alemanah2025@',
  port=5432
)

cur = conn.cursor()
cur.execute('SELECT 1')
print(cur.fetchone())
conn.close()
```

Para instalar a dependência necessária:

```bash
python -m pip install psycopg2-binary
```

Observação de segurança: evite deixar credenciais em código; prefira variáveis de ambiente ou um arquivo de configuração seguro.

---

## 5. Resumo por arquivo (responsabilidades)

- `medsoft_app.py`
  - Inicializa Flask, registra Blueprints (`consultas_bp`, `consulta_paciente_bp`, `agenda_bp`, `agenda_api_bp`), rotas de templates e endpoints `login` e `change-password`.

- `medsoft_core.py`
  - `get_db_connection(database=None)` — conecta ao PostgreSQL usando as configurações de ambiente.

- `consulta_paciente.py`
  - Blueprint ativo com `POST /api/consulta-paciente` que busca pacientes no `Pacient` e retorna `nomecli`, `codcli`, `idade`, `nomeplano1`, `nomed`.

- `paciente_routes.py`
  - Versão alternativa/comentada de `consulta-paciente` (contém lógica similar; ver duplicidade).

- `consultas_routes.py`
  - `POST /api/consultas-paciente` — busca histórico de consultas para um `codpac` e formata `historico` e datas.

- `agenda.py` e `agenda_api.py`
  - `agenda.py` serve o template `/agenda`; `agenda_api.py` implementa `POST /api/agenda` para listar agenda por data.

---

## 6. Observações de segurança e manutenção
- `app.secret_key` está em claro — mover para variável de ambiente.
- Senhas parecem manipuladas em texto (tabela `senha`) — migrar para hash (bcrypt/argon2) e usar HTTPS.
- Credenciais e host do banco (`sysdba/masterkey`, `24.152.36.178`) estão hard-coded — mover para configuração/variáveis de ambiente.
- `X-DB-PATH` expõe caminho do arquivo DB: avalie permissões e validações.

---

## 7. Arquivos auxiliares criados
- `ENDPOINTS.md` — exemplos `curl` e notas para Postman.
- `FILE_SUMMARY.md` — resumo por arquivo e riscos.
- `postman_collection.json` — coleção Postman com requests básicos.
- `tests_smoke.py` — script Python para smoke tests (usa `requests`).

---

Se quiser que eu gere um arquivo Word `.docx` com este conteúdo, eu crio o `DOCUMENTATION.docx` (formato binário) aqui para download. Deseja que eu gere o `.docx` ou prefere ler o `DOCUMENTATION.md` que acabei de criar?
