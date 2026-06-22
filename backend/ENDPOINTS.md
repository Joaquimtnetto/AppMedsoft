# Exemplos de uso dos endpoints

Este arquivo contém exemplos `curl` e instruções para importar no Postman dos endpoints principais do backend.

## POST /api/login
- URL: `http://localhost:8072/api/login`
- Body (JSON):

```json
{ "nome": "seu_usuario", "senha": "sua_senha" }
```

Exemplo curl:

```bash
curl -X POST http://localhost:8072/api/login \
  -H "Content-Type: application/json" \
  -d '{"nome":"seu_usuario","senha":"sua_senha"}'
```

Resposta (sucesso): JSON com campos: `success`, `nome`, `idusuario`, `idempresa`, `db_path`, `empresa_nome`, `nome_medico`.

## POST /api/change-password
- URL: `http://localhost:8072/api/change-password`
- Body (JSON):

```json
{ "nome": "seu_usuario", "senhaAtual": "senha_atual", "novaSenha": "nova_senha" }
```

Exemplo curl:

```bash
curl -X POST http://localhost:8072/api/change-password \
  -H "Content-Type: application/json" \
  -d '{"nome":"seu_usuario","senhaAtual":"senha_atual","novaSenha":"nova_senha"}'
```

Resposta: `{ "success": true/false, "message": "..." }`.


## POST /api/consulta-paciente
- URL: `http://localhost:8072/api/consulta-paciente`
- Cabeçalho: não é obrigatório quando a aplicação está configurada para usar Postgres (padrão).
- Body (JSON):

```json
{ "termo": "nome ou parte do nome", "nome_medico": "Nome do médico" }
```

Exemplo curl (Postgres):

```bash
curl -X POST http://localhost:8072/api/consulta-paciente \
  -H "Content-Type: application/json" \
  -d '{"termo":"JOÃO","nome_medico":"DR. SILVA"}'
```

Resposta (sucesso):

```json
{
  "success": true,
  "pacientes": [
    {"nomecli":"JOÃO DA SILVA","codcli":123,"idade":45,"nomeplano1":"Plano X","nomed":"DR. SILVA"},
    ...
  ]
}
```

Erros comuns:
- 400 quando `termo` ou `nome_medico` ausentes.
- 400 quando `X-DB-PATH` não informado.

## POST /api/consultas-paciente
- URL: `http://localhost:8072/api/consultas-paciente`
- Cabeçalho obrigatório: `X-DB-PATH: caminho_para_o_arquivo_fdb_da_empresa`
- Body (JSON):

```json
{ "codpac": 123 }
```

Exemplo curl:

```bash
curl -X POST http://localhost:8072/api/consultas-paciente \
  -H "Content-Type: application/json" \
  -H "X-DB-PATH: medsoft_medmigra" \
  -d '{"codpac":123}'
```

Resposta (sucesso):

```json
{
  "success": true,
  "consultas": [
    {"dtvisita":"01/01/2026","diag":"Diagnóstico","historico":"<br>texto...","clinica":"Clinica X","nomepac":"João","separador":""},
    ...
  ]
}
```

## GET rotas de templates
- `GET /` — tela de login
- `GET /principal.html`, `GET /menu.html`, `GET /consulta_paciente.html`, `GET /consultas_paciente.html` — servem templates do frontend.

## Postman
- Para importar: crie uma collection e adicione requests com `Content-Type: application/json`.
- Adicione o header `X-DB-PATH` nos requests que acessam dados da empresa.

Se quiser, eu gero um arquivo de exportação do Postman (JSON) com os requests prontos.
