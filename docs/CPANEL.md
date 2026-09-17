# Publicacao no cPanel

O cPanel executa a aplicacao Python com Passenger em Linux. Os arquivos gerados
pelo PyInstaller (`build`, `dist` e `.exe`) sao exclusivos do Windows e nao devem
ser enviados para a hospedagem.

## Configuracao da aplicacao

Para evitar conflitos ao criar o ambiente virtual, use uma raiz simples, sem
subpastas. Considerando os arquivos enviados para:

```text
/home/SEU_USUARIO/sistema_medsoft_pMobile
```

preencha o painel **Setup Python App** assim:

```text
Versao do Python:                  3.12
Raiz do aplicativo:               sistema_medsoft_pMobile
URL do aplicativo:                sistema.medsoft.com.br /
Arquivo de inicializacao:         passenger_wsgi.py
Ponto de entrada da aplicacao:    application
```

A raiz do aplicativo e relativa ao diretorio da conta. Use `/` e nunca `\`.

## Configuracao do banco

Este pacote ja possui os valores atuais de conexao como padrao em
`backend/config.py`. Portanto, o cadastro das variaveis abaixo no painel nao e
obrigatorio para iniciar a aplicacao.

Em producao, recomenda-se cadastra-las no painel para substituir os valores do
arquivo sem precisar alterar o codigo:

```text
MEDSOFT_PG_HOST
MEDSOFT_PG_PORT
MEDSOFT_PG_DB
MEDSOFT_PG_USER
MEDSOFT_PG_PASS
MEDSOFT_SECRET_KEY
```

As configuracoes de e-mail sao opcionais:

```text
MEDSOFT_SMTP_HOST
MEDSOFT_SMTP_PORT
MEDSOFT_SMTP_USER
MEDSOFT_SMTP_PASS
MEDSOFT_SMTP_USE_TLS
MEDSOFT_SMTP_USE_SSL
MEDSOFT_SMTP_FROM
```

## Instalacao

Depois de criar a aplicacao, abra o terminal do cPanel e execute o comando de
ativacao exibido pelo painel. Em seguida, dentro da raiz da aplicacao:

```bash
python -m pip install -r requirements.txt
```

Por fim, clique em **Restart** no painel. A aplicacao nao deve chamar
`medsoft_app.exe`; o Passenger importa o objeto `application` diretamente de
`passenger_wsgi.py`.
