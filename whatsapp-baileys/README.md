# Serviço WhatsApp do MedSoft (Baileys)

Este serviço é um módulo separado do MedSoft. Ele mantém uma sessão independente do WhatsApp para cada empresa, fornece o QR Code ao backend Flask e realiza os envios sem abrir `wa.me` no navegador.

## Estrutura

```text
whatsapp-baileys/
├── server.js                       inicialização e encerramento seguro
├── src/config.js                   ambiente, logs e diretórios
├── src/http/api-server.js          API interna protegida
├── src/whatsapp/phone.js           normalização de telefone e JID
├── src/whatsapp/session-manager.js sessões, QR, reconexão e envio
├── test/                            testes independentes do Flask
└── sessions/                        credenciais locais (não publicar)
```

## API interna

Todas as rotas exigem `Authorization: Bearer <MEDSOFT_BAILEYS_TOKEN>`.

- `GET /health` — saúde do serviço.
- `GET /sessions/:empresa/status` — inicia/restaura a sessão e retorna estado ou QR.
- `POST /sessions/:empresa/messages/text` — envia `{ "phone": "...", "text": "..." }`.
- `POST /sessions/:empresa/disconnect` — encerra a sessão e remove as credenciais daquela empresa.

O navegador nunca acessa essa API diretamente. O Flask identifica a empresa autenticada e atua como ponte segura.

## Requisitos

- Node.js 20 ou superior.
- Diretório persistente e gravável para `sessions`.
- Uma chave interna forte e igual no serviço Node e no MedSoft Python.

## Instalação

1. Publique toda a pasta `whatsapp-baileys` no servidor.
2. Execute `npm install --omit=dev` dentro dela.
3. Configure as variáveis:

   - `MEDSOFT_BAILEYS_TOKEN`: chave interna forte.
   - `MEDSOFT_BAILEYS_HOST`: `127.0.0.1` quando Flask e Node compartilham o servidor; no gerenciador Node do cPanel, use o endereço exigido pela hospedagem.
   - `MEDSOFT_BAILEYS_PORT`: porta interna, por exemplo `3001`. Quando ausente, o serviço também aceita a variável `PORT` fornecida pelo cPanel.
   - `MEDSOFT_BAILEYS_SESSIONS`: diretório persistente para as credenciais, por exemplo `/home/USUARIO/medsoft-baileys-sessions`.

4. Inicie com `npm start` ou configure `server.js` como arquivo de inicialização no cPanel.
5. Na aplicação Python, configure:

   - `MEDSOFT_BAILEYS_URL`: endereço alcançável pelo Flask, por exemplo `http://127.0.0.1:3001`.
   - `MEDSOFT_BAILEYS_TOKEN`: exatamente a mesma chave do serviço Node.

6. Reinicie os dois serviços.

## Fluxos já migrados

- Solicitação de confirmação pela Agenda.
- Mensagem enviada depois da confirmação pública do paciente.
- Envio individual ou em lote pelo relatório de pacientes.

Esses fluxos não abrem mais abas do WhatsApp Web.

## Próximas extensões previstas

A separação atual permite acrescentar sem alterar o núcleo do MedSoft:

- imagens, PDFs, áudio e documentos;
- fila persistente com tentativas e controle de velocidade;
- webhooks de entrega, leitura e resposta;
- caixa de entrada e atendimento por conversa;
- modelos de mensagens e variáveis;
- armazenamento das credenciais em PostgreSQL ou cofre criptografado;
- painel de saúde por empresa.

O diretório de sessões contém credenciais sensíveis do WhatsApp. Não publique, não compartilhe e mantenha uma cópia de segurança protegida.
