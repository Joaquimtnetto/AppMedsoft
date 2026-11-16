# Fontes do Medsoft no Alpha

Servidor: 208.115.208.180. Usuário SSH: alpha.

O programa executa no servidor Linux e usa Python 3.12 e Git, já disponíveis.
Não contém senhas. O código é obtido de https://github.com/Joaquimtnetto/AppMedsoft.git, branch main.

Depois de entrar no Alpha por SSH:

```sh
python3 /home/alpha/atualizar_medsoft.py atualizar
```

Para consultar as versões copiadas:

```sh
python3 /home/alpha/atualizar_medsoft.py status
```

Para apontar novamente para a versão anterior:

```sh
python3 /home/alpha/atualizar_medsoft.py voltar
```

## Pastas

- `/home/alpha/medsoft_backup/atual`: acesso aos fontes mais recentes copiados.
- `/home/alpha/medsoft_backup/anterior`: versão que estava ativa antes da última atualização.
- `/home/alpha/medsoft_backup/versoes`: mantém somente a versão atual e a imediatamente anterior.
- `/home/alpha/medsoft_backup/historico.jsonl`: registro das atualizações e retornos.

A palavra “atual” se refere somente ao atalho dos arquivos; não significa aplicação publicada ou em execução.

## Uso

1. Publique no GitHub as alterações de código que deseja levar ao Alpha.
2. Execute o comando de atualização no Alpha.
3. O programa busca o commit mais recente da branch main, extrai uma nova versão e confere a sintaxe do backend Python.
4. Somente depois da conferência o atalho `atual` é trocado. A pasta anterior continua guardada.

Se a versão já estiver copiada, não há nova cópia. Se detectar arquivos alterados/adicionados localmente na pasta atual, o programa interrompe a atualização para preservá-los. Modifique o código no GitHub, não diretamente nas pastas de versões. Configurações, senhas e arquivos de usuários devem ser mantidos fora dessas pastas.

Nesta etapa o programa apenas copia fontes. Não instala dependências, não executa migrações SQL, não acessa o banco de dados, não reinicia serviços e não configura domínio, HTTPS ou WhatsApp.

Após uma atualização bem-sucedida, versões mais antigas são apagadas automaticamente. A limpeza também ocorre quando os fontes já estão atualizados. Pastas desconhecidas ou com alterações locais não são apagadas; alterações locais interrompem a limpeza e são informadas. O recurso `voltar` troca somente os atalhos dos arquivos e não reverte dados de banco ou serviços.
