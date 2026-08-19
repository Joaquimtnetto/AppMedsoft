# Resumo por arquivo — backend

Este documento descreve responsabilidades e funções principais dos arquivos do backend.

## medsoft_app.py
- Inicializa a aplicação Flask com `template_folder` e `static_folder` apontando para a pasta pai `templates` e `static`.
- Define `app.secret_key` e registra Blueprints: `consultas_bp`, `consulta_paciente_bp`, `agenda_bp`, `agenda_api_bp`.
- Rotas principais:
  - `GET /` → `login.html`
  - `POST /api/login` → autentica usuário na base `medicoraiz.fdb`, obtém `db_path` da empresa, guarda em `session`.
  - `POST /api/change-password` → atualiza senha na tabela `senha` (atenção: armazenamento em texto claro aparenta ocorrer).
  - Rotas para servir templates (`/principal.html`, `/menu.html`, `/consulta_paciente.html`, `/consultas_paciente.html`).
- Observações: gerencia variáveis globais `db_path_global`, `usuario_global`, `empresa_global` e configura caminhos para o cliente Firebird.

## medsoft_core.py
- Função `get_db_connection(db_path=None)` — cria e retorna uma conexão Firebird usando `fdb.connect`.
- Uso: se `db_path` não informado, usa `medicoraiz.fdb`; monta caminho base `C:/JTN/Medsoft/2-Migracao/BD` quando necessário.

## paciente_routes.py
- Blueprint `paciente_bp` com rota `POST /api/consulta-paciente` (há duplicidade de lógica comentada; existe também `consulta_paciente.py`).
- Lê `X-DB-PATH` do header (ou `db_path` no JSON em chamadas anteriores) e busca na tabela `Pacient` pacientes por `termo` e `nome_medico`.
- Calcula idade com base em `datanasc_` e retorna lista `pacientes`.

## consulta_paciente.py
- Blueprint `consulta_paciente_bp` com rota `POST /api/consulta-paciente` (implementação ativa usada pela aplicação).
- Suporta `nome_medico` opcional (usa `LIKE` quando não informado) e monta query adequada.
- Retorna `pacientes` com campos `nomecli`, `codcli`, `idade`, `nomeplano1`, `nomed`.

## consultas_routes.py
- Blueprint `consultas_bp` com rota `POST /api/consultas-paciente`.
- Exige `codpac` no body e `X-DB-PATH` no header; converte `codpac` para `int` e busca consultas na tabela `CONSULTA`.
- Formata `historico` (decodifica bytes/blobs) e datas (`dtvisita`) para `dd/mm/YYYY`.

## agenda.py
- Blueprint `agenda_bp` que serve o template `/agenda` (renderiza `agenda.html`).

## agenda_api.py
- Blueprint `agenda_api_bp` com `POST /api/agenda` que recebe `data` (yyyy-mm-dd), usa `session['nome_medico']` e `X-DB-PATH` para consultar agenda do dia.
- Formata data para Firebird (`dd.mm.YYYY`) antes de executar a query.

## requirements.txt
- Contém `flask` e `fdb`. Confirme versões em um ambiente controlado antes de deploy.

## Notas gerais e riscos conhecidos
- `app.secret_key` está codificada; troque por variável de ambiente em produção.
- Senhas parecem manipuladas em texto; considere hashing e HTTPS.
- O hostname/porta do banco e credenciais estão hard-coded em `get_db_connection` (`24.152.36.178`, `sysdba/masterkey`) — mover para configuração/variáveis de ambiente.
- As queries usam parâmetros `?` (bom), mas revise permissões e exposição do arquivo DB via `X-DB-PATH`.

Se quiser, gero também uma exportação do Postman com os requests prontos e testes básicos de integração.
