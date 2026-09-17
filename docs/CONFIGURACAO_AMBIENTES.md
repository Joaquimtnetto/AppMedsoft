# MedSoft pMobile — Configuração dos ambientes

## 1. Arquitetura

O MedSoft utiliza dois serviços separados:

### Aplicação principal

- Tecnologia: Python/Flask
- Serviço: sistema MedSoft
- Domínio principal: `medsoft.com.br`
- Banco: PostgreSQL
- Hospedagem: cPanel principal

### Serviço de WhatsApp

- Tecnologia: Node.js com Baileys
- Serviço: conexão do WhatsApp por QR Code
- Domínio: `agenda.medsoft.com.br`
- Hospedagem: segundo cPanel
- Requisito: Node.js 20 ou superior

Embora os dois domínios apontem para o IP `177.85.99.66`, eles pertencem a contas diferentes do cPanel. Por isso, a comunicação em produção deve utilizar HTTPS, e não `127.0.0.1`.

## 2. Regra geral de configuração

A ordem de prioridade é:

1. Variável de ambiente, quando existir.
2. Valor padrão definido no arquivo de configuração.

Isso permite usar o mesmo código no computador local, notebook e servidor.

### Ambiente local

O MedSoft funciona sem depender de `.env`.

Os valores principais ficam em:

- Python: `backend/config.py`
- Node/Baileys: `whatsapp-baileys/src/config.js`

### Servidor

As variáveis de ambiente do cPanel podem sobrescrever os valores locais, principalmente endereços, portas e tokens.

Os arquivos `.env` não são obrigatórios para executar o MedSoft localmente.

## 3. Configuração do PostgreSQL

Arquivo principal: `backend/config.py`.

Variáveis reconhecidas:

```text
MEDSOFT_PG_HOST
MEDSOFT_PG_PORT
MEDSOFT_PG_DB
MEDSOFT_PG_USER
MEDSOFT_PG_PASS
MEDSOFT_PG_CLIENT_ENCODING
```

Configuração lógica:

```python
PG_HOST = os.environ.get("MEDSOFT_PG_HOST", "ENDERECO_DO_POSTGRES")
PG_PORT = int(os.environ.get("MEDSOFT_PG_PORT", "5432"))
PG_DB = os.environ.get("MEDSOFT_PG_DB", "NOME_DO_BANCO")
PG_USER = os.environ.get("MEDSOFT_PG_USER", "USUARIO_DO_BANCO")
PG_PASS = os.environ.get("MEDSOFT_PG_PASS", "SENHA_DO_BANCO")
```

O módulo `medsoft_core.py` utiliza os valores já carregados pelo `config.py`.

Para substituir uma configuração no servidor, cadastre a variável correspondente no cPanel. Se ela não existir, o valor padrão do `config.py` será utilizado.

## 4. Configuração do Baileys no Python

O Python se comunica com o serviço Node por HTTP ou HTTPS.

Variáveis reconhecidas:

```text
MEDSOFT_BAILEYS_URL
MEDSOFT_BAILEYS_TOKEN
```

### Configuração local

```text
MEDSOFT_BAILEYS_URL=http://127.0.0.1:3001
```

O serviço Python e o Node funcionam no mesmo computador, portanto o endereço local pode ser usado.

### Configuração no servidor

```text
MEDSOFT_BAILEYS_URL=https://agenda.medsoft.com.br
MEDSOFT_BAILEYS_TOKEN=TOKEN_INTERNO_COMPARTILHADO
```

O token precisa ser exatamente igual ao configurado na aplicação Node.

Nunca coloque `/health` ou outra rota no final da URL. Use apenas:

```text
https://agenda.medsoft.com.br
```

## 5. Configuração da aplicação Node/Baileys

Diretório da aplicação: `whatsapp-baileys/`.

Arquivo inicial: `server.js`.

Arquivo de configuração: `src/config.js`.

Variáveis reconhecidas:

```text
MEDSOFT_BAILEYS_HOST
MEDSOFT_BAILEYS_PORT
MEDSOFT_BAILEYS_TOKEN
MEDSOFT_BAILEYS_SESSIONS
MEDSOFT_BAILEYS_LOG_LEVEL
PORT
```

### Configuração local

```text
MEDSOFT_BAILEYS_HOST=127.0.0.1
MEDSOFT_BAILEYS_PORT=3001
MEDSOFT_BAILEYS_TOKEN=TOKEN_INTERNO_COMPARTILHADO
MEDSOFT_BAILEYS_SESSIONS=./sessions
```

### Configuração no cPanel

```text
MEDSOFT_BAILEYS_HOST=0.0.0.0
MEDSOFT_BAILEYS_TOKEN=TOKEN_INTERNO_COMPARTILHADO
MEDSOFT_BAILEYS_SESSIONS=/CAMINHO/PERSISTENTE/sessions
```

No cPanel, normalmente não se deve cadastrar `MEDSOFT_BAILEYS_PORT`. A aplicação deve utilizar a variável `PORT` fornecida automaticamente pelo cPanel.

### Requisitos do Node

```text
Node.js 20 ou superior
Arquivo inicial: server.js
Comando de instalação: npm install
Comando local: npm start
```

## 6. Token compartilhado

O token protege a comunicação entre o Python e o Node.

Ele deve ser igual nos dois lados:

### Python

```text
MEDSOFT_BAILEYS_TOKEN=TOKEN_INTERNO_COMPARTILHADO
```

### Node

```text
MEDSOFT_BAILEYS_TOKEN=TOKEN_INTERNO_COMPARTILHADO
```

Se os tokens forem diferentes, a aplicação retornará erro de autorização.

O token não deve ser publicado no GitHub, enviado por mensagem ou colocado em documentação pública.

## 7. Sessões do WhatsApp

As credenciais do WhatsApp ficam em `whatsapp-baileys/sessions/`.

Cada empresa possui uma pasta própria, por exemplo:

```text
sessions/empresa-6/
```

O principal arquivo de autenticação é:

```text
sessions/empresa-6/creds.json
```

Regras importantes:

- Não publicar `sessions` no GitHub.
- Não substituir a sessão do servidor pela sessão do Windows.
- Não copiar a mesma sessão para dois servidores ativos.
- Não apagar `creds.json` sem necessidade.
- Sempre fazer backup das sessões antes de atualizar o Node.
- A pasta precisa permitir gravação pelo usuário da aplicação Node.

Se a pasta não tiver permissão de gravação, o QR poderá ser aceito pelo celular, mas o serviço encerrará ao tentar salvar `creds.json`.

## 8. Execução local pelo VS Code

Abrir a pasta:

```text
C:\Medsoft\MedsoftPhytonFull\pMobile
```

No VS Code:

1. Abrir **Executar e Depurar**.
2. Selecionar **MedSoft completo (Flask + Whatzap)**.
3. Pressionar `F5`.

Esse perfil inicia:

- Flask/Python na porta 8072.
- Node/Baileys na porta 3001.

Executar apenas `python medsoft_app.py` inicia somente o Python. Nesse caso, o QR Code não funcionará porque o Node não estará ativo.

## 9. Verificação do serviço

### Aplicação local

```text
http://localhost:8072
```

### Baileys local

```text
http://127.0.0.1:3001/health
```

### Baileys no servidor

```text
https://agenda.medsoft.com.br/health
```

A rota do Baileys exige o token de autorização. Um retorno de “não autorizado” confirma que o domínio chegou ao serviço, mas o token não foi enviado ou não corresponde.

## 10. Atualização do servidor

Antes de atualizar:

1. Fazer backup da aplicação Python.
2. Fazer backup da aplicação Node.
3. Fazer backup separado da pasta `sessions`.
4. Guardar uma cópia do `config.py` do servidor.
5. Registrar as variáveis do cPanel.
6. Confirmar a versão do Node.
7. Confirmar o arquivo inicial da aplicação.
8. Confirmar o domínio e o certificado HTTPS.

Durante a atualização:

1. Atualizar primeiro os arquivos Python.
2. Preservar as configurações específicas do servidor.
3. Atualizar os arquivos Node.
4. Não substituir a pasta `sessions`.
5. Executar `npm install` caso o `package.json` tenha mudado.
6. Reiniciar a aplicação Node.
7. Reiniciar a aplicação Python.

Depois da atualização:

1. Testar o login.
2. Testar a conexão PostgreSQL.
3. Verificar o estado do WhatsApp.
4. Confirmar que o número aparece conectado.
5. Fazer um envio de teste.
6. Examinar os registros das duas aplicações.

## 11. Restauração de emergência

Se a atualização falhar:

1. Parar a aplicação Python.
2. Restaurar o ZIP do Python.
3. Parar a aplicação Node.
4. Restaurar o ZIP do Node.
5. Restaurar a pasta de sessões somente se ela tiver sido alterada.
6. Conferir as variáveis do cPanel.
7. Executar novamente `npm install`, se necessário.
8. Reiniciar Node e Python.
9. Testar banco e WhatsApp.

Não apague a versão problemática antes de confirmar que o backup pode ser extraído corretamente.

## 12. Resumo dos endereços

| Ambiente | Python/Flask | Node/Baileys |
|---|---|---|
| Computador local | `http://localhost:8072` | `http://127.0.0.1:3001` |
| Servidor | Domínio principal do MedSoft | `https://agenda.medsoft.com.br` |

## 13. Arquivos que nunca devem ir para o GitHub

```text
.env
.env.txt
sessions/
creds.json
.medsoft_secret_key
arquivos de backup
logs com dados sensíveis
```

Os arquivos `.env.example` podem ser publicados somente com valores fictícios e sem senhas ou tokens reais.
