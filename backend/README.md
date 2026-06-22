# Documentação do backend do pMobile (Medsoft)

Este documento resume a arquitetura, os componentes principais, dependências e instruções básicas para executar o backend desta aplicação.

**Visão geral**
- **Propósito:** Backend Flask que expõe endpoints para login, busca de pacientes e consultas, além de servir templates HTML do frontend.
- **Entrada principal:** [backend/medsoft_app.py](backend/medsoft_app.py#L1-L400) roda a aplicação Flask (porta padrão 8072).

**Dependências**
- Lista de dependências: [backend/requirements.txt](backend/requirements.txt#L1-L50) (contém `flask` e `psycopg2-binary`).

**Arquitetura e componentes principais**
- `medsoft_app.py`: inicializa o Flask, registra Blueprints e define rotas estáticas e de login. Veja [backend/medsoft_app.py](backend/medsoft_app.py#L1-L400).
- `medsoft_core.py`: função `get_db_connection(database)` que cria a conexão PostgreSQL. Veja [backend/medsoft_core.py](backend/medsoft_core.py#L1-L200).
- `paciente_routes.py`: Blueprint que implementa `/api/consulta-paciente`. Veja [backend/paciente_routes.py](backend/paciente_routes.py#L1-L400).
- `consultas_routes.py`: Blueprint que implementa `/api/consultas-paciente`. Veja [backend/consultas_routes.py](backend/consultas_routes.py#L1-L400).
- `consulta_paciente.py`, `agenda.py`, `agenda_api.py`: módulos adicionais registrados como Blueprints (use para funcionalidades específicas de agenda/consulta).

**Principais endpoints (resumo)**
- `POST /api/login` — body JSON: `{ "nome": "user", "senha": "pass" }`.
  - Autentica no PostgreSQL, busca o banco da empresa e armazena `db_path` em `session`.
  - Resposta: JSON com `success`, `nome`, `idusuario`, `db_path`, `empresa_nome`, `nome_medico`.
- `POST /api/change-password` — body JSON: `{ "nome": ..., "senhaAtual": ..., "novaSenha": ... }`.
- `POST /api/consulta-paciente` — header `X-DB-PATH` ou body com `db_path`; body JSON: `{ "termo": "nome ou código", "nome_medico": "..." }`.
  - Retorna lista de pacientes compatíveis.
- `POST /api/consultas-paciente` — header `X-DB-PATH`; body JSON: `{ "codpac": 123 }`.
  - Retorna histórico de consultas do paciente.
- Rotas que servem templates: `/`, `/principal.html`, `/menu.html`, `/consulta_paciente.html`, `/consultas_paciente.html`.

**Como executar localmente (Windows)**
1. Instalar dependências:

```bash
python -m pip install -r backend/requirements.txt
```

2. Configurar as variáveis `MEDSOFT_PG_HOST`, `MEDSOFT_PG_PORT`, `MEDSOFT_PG_DB`, `MEDSOFT_PG_USER` e `MEDSOFT_PG_PASS`.

3. Executar a aplicação:

```bash
python backend/medsoft_app.py
```

4. Acesse `http://localhost:8072/` e use a tela de login.

**Observações importantes**
- Conexão ao banco: `get_db_connection` usa a configuração PostgreSQL definida em variáveis de ambiente. O `db_path` identifica o banco da empresa. Veja [backend/medsoft_core.py](backend/medsoft_core.py#L1-L200).
- Sessões: `medsoft_app.py` usa `session` do Flask para guardar `db_path`, `nome_medico` e `usuario`.
- Segurança: a `app.secret_key` está em claro; troque por uma chave segura em produção. Senhas parecem armazenadas/consultadas em tabela `senha` em texto; revise para usar hash e transporte seguro (HTTPS).
- Tratamento de erros: os endpoints retornam JSON com `success` e mensagens; logs em `print` e `logging` para debug.

**Próximos passos (sugestões)**
- Gerar documentação por arquivo (funções principais e excertos) para facilitar manutenção.
- Criar exemplos curl/Postman para cada endpoint.
- Adicionar testes básicos de integração (mock do DB) e checklist de deploy.

Se quiser, eu gero os exemplos de requests (curl/Postman) e um resumo por arquivo agora.
