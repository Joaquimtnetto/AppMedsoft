# Padrão do botão Voltar

O componente compartilhado está em `static/js/navigation.js`, com estilos em
`static/css/navigation.css`.

## Página completa

Inclua apenas o script no final da página. A seta será criada automaticamente:

```html
<script src="/static/js/navigation.js"></script>
```

O componente usa o histórico quando a página anterior pertence ao sistema e usa `/` como
destino seguro quando não existe uma página anterior.

## Tela carregada no painel

O painel carrega o script uma única vez e chama:

```javascript
NavigationUI.attach({
    container: mainContent,
    inline: true,
    onBack: voltarTelaPainel
});
```

A função `carregarTela` mantém a pilha de telas. Novos módulos carregados por ela recebem
automaticamente a seta e não precisam declarar botão ou evento próprio.
