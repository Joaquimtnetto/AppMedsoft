# Diagramas — resumo visual do backend

Este arquivo contém diagramas Mermaid que resumem a arquitetura, os fluxos principais (login, busca de pacientes e consultas) e o fluxo de dados.

**1) Arquitetura geral**

```mermaid
graph LR
  Client[Usuário (Frontend)] -->|HTTP| App[medsoft_app (Flask)]
  App -->|register_blueprint| ConsultaBP[consultas_bp]
  App -->|register_blueprint| PacienteBP[consulta_paciente_bp]
  App -->|register_blueprint| AgendaBP[agenda_bp / agenda_api_bp]
  ConsultaBP -->|usa|get_db_connection[medsoft_core.get_db_connection]
  PacienteBP -->|usa|get_db_connection
  AgendaBP -->|usa|get_db_connection
  get_db_connection -->|connect| PostgreSQL[PostgreSQL (Banco principal / Empresa)]
  App -->|serve| Templates[templates/ static/]
```

**Legenda:** o `App` registra Blueprints que executam queries via `medsoft_core.get_db_connection` para conectar ao PostgreSQL.

**2) Sequência: Login**

```mermaid
sequenceDiagram
  participant C as Client
  participant A as medsoft_app
  participant DBroot as PostgreSQL principal
  participant DBuser as EmpresaDB

  C->>A: POST /api/login {nome, senha}
  A->>DBroot: get_db_connection() -> valida credenciais
  DBroot-->>A: usuario + db_path (empresa)
  A->>DBuser: get_db_connection(db_path) (test connection)
  DBuser-->>A: OK
  A-->>C: {success: true, db_path, nome_medico, ...}
```

**3) Sequência: Consulta de paciente**

```mermaid
sequenceDiagram
  participant C as Client
  participant A as medsoft_app
  participant BP as consulta_paciente_bp
  participant DB as EmpresaDB

  C->>A: POST /api/consulta-paciente (JSON) + header X-DB-PATH
  A->>BP: encaminha para rota /api/consulta-paciente
  BP->>DB: get_db_connection(X-DB-PATH) e executa SELECT em Pacient
  DB-->>BP: rows
  BP-->>A: JSON {pacientes: [...]}
  A-->>C: responde JSON
```

**4) Sequência: Histórico de consultas**

```mermaid
sequenceDiagram
  participant C as Client
  participant A as medsoft_app
  participant BP as consultas_bp
  participant DB as EmpresaDB

  C->>A: POST /api/consultas-paciente {codpac} + X-DB-PATH
  A->>BP: rota consultas_paciente
  BP->>DB: SELECT em CONSULTA, JOIN PACIENT, CLINICA
  DB-->>BP: rows
  BP->>A: JSON com consultas formatadas
  A-->>C: JSON
```

**5) Fluxo de dados (simplificado)**

```mermaid
graph TD
  request[Request HTTP] --> app[medsoft_app]
  app --> route[Blueprint route]
  route --> core[get_db_connection]
  core --> db[Banco PostgreSQL]
  db --> result[Rows]
  result --> route
  route --> response[JSON]
  response --> client
```

**Observações rápidas**
- Os diagramas são ideais para documentação em Markdown/HTML (renderizadores que suportam Mermaid).
- Se preferir um `.docx` com imagens das figuras, posso renderizar cada diagrama como imagem e embutir em um `DOCUMENTATION.docx` para download.
