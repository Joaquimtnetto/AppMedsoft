# Padrão de inclusão, edição e exclusão

O projeto concentra o comportamento comum de manutenção nestes arquivos:

- `static/js/crud.js`: controlador, formulário modal, chamadas HTTP, confirmação, mensagens e recarga.
- `static/css/crud.css`: botões, formulários, listas, cartões e responsividade.
- `backend/crud_repository.py`: inclusão, alteração e exclusão transacionais com colunas permitidas.

## Nova tela

No JavaScript da tela, crie um `CrudUI.Controller` e informe somente:

- `getId`: retorna a chave do registro.
- `fields`: descreve os campos do formulário.
- `renderItem`: apresenta um registro e usa `data-crud-edit` e `data-crud-delete` nos botões.
- `list`, `create`, `update` e `delete`: ligam o controlador aos endpoints da tela.
- Títulos, mensagem vazia e texto da confirmação.

Depois, monte o controlador passando o elemento raiz, a lista e o botão Incluir. Consulte
`static/js/agenda.js` como exemplo completo e curto.

## Novo backend

Crie um repositório declarando tabela, chave e colunas que podem ser gravadas:

```python
repository = CrudRepository(
    connection_factory=connection,
    table='nome_tabela',
    id_column='id',
    writable_columns=('campo_a', 'campo_b'),
)
```

As rotas chamam `repository.create(dados)`, `repository.update(id, dados)` e
`repository.delete(id)`. A lista de colunas permitidas impede que nomes recebidos do navegador
sejam usados diretamente na consulta SQL.
