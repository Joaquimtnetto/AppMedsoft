(function () {
    const moeda = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'});
    const endpoint = '/api/empresas/pagamentos';

    function formatarData(valor) {
        return valor == null ? '—' : valor.split('-').reverse().join('/');
    }

    function formatarValor(valor) {
        return valor == null ? '—' : moeda.format(valor);
    }

    function criarCartao(pagamento, editar, duplicar, excluir) {
        const cartao = document.createElement('article');
        cartao.className = 'crud-card';
        const campos = document.createElement('div');
        campos.className = 'crud-card-details';
        const detalhes = [
            ['Data prevista', formatarData(pagamento.dataprevpag)],
            ['Data do pagamento', formatarData(pagamento.datapagrealiz)],
            ['Valor previsto', formatarValor(pagamento.valorprev)],
            ['Valor pago', formatarValor(pagamento.valorpag)],
            ['Tipo de pagamento', pagamento.tipopag || '—']
        ];
        for (const [rotulo, valor] of detalhes) {
            const campo = document.createElement('span');
            const titulo = document.createElement('strong');
            titulo.textContent = rotulo + ': ';
            campo.append(titulo, valor);
            campos.append(campo);
        }
        cartao.append(campos);
        if (!editar) return cartao;

        const acoes = document.createElement('div');
        acoes.className = 'crud-card-actions';
        const botaoEditar = document.createElement('button');
        botaoEditar.type = 'button';
        botaoEditar.className = 'crud-button crud-button-secondary';
        botaoEditar.textContent = 'Editar';
        botaoEditar.addEventListener('click', editar);
        const botaoDuplicar = document.createElement('button');
        botaoDuplicar.type = 'button';
        botaoDuplicar.className = 'crud-button crud-button-secondary';
        botaoDuplicar.textContent = 'Duplicar';
        botaoDuplicar.addEventListener('click', () => duplicar(botaoDuplicar));
        const botaoExcluir = document.createElement('button');
        botaoExcluir.type = 'button';
        botaoExcluir.className = 'crud-button crud-button-danger';
        botaoExcluir.textContent = 'Excluir';
        botaoExcluir.addEventListener('click', () => excluir(botaoExcluir));
        acoes.append(botaoEditar, botaoDuplicar, botaoExcluir);
        cartao.append(acoes);
        return cartao;
    }

    async function init() {
        const status = document.getElementById('pagamentos-empresa-status');
        if (!status || status.dataset.iniciado) return;
        status.dataset.iniciado = '1';
        const resultado = document.getElementById('pagamentos-empresa-result');
        const empresa = document.getElementById('pagamentos-empresa-selecao');
        const incluir = document.getElementById('pagamentos-empresa-incluir');
        if (!empresa) {
            status.textContent = 'Carregando pagamentos da sua empresa.';
            try {
                const dados = await CrudUI.request(endpoint, {cache: 'no-store'});
                const links = document.getElementById('pagamentos-empresa-links');
                for (const [tipo, rotulo] of [['pix', 'Pagar via Pix'], ['cartao', 'Assinar no cartão']]) {
                    const endereco = dados.links && dados.links[tipo];
                    if (!endereco) continue;
                    const botao = document.createElement('a');
                    botao.className = 'crud-button';
                    botao.href = endereco;
                    botao.target = '_blank';
                    botao.rel = 'noopener noreferrer';
                    botao.textContent = rotulo;
                    links.append(botao);
                }
                if (!links.childElementCount) links.textContent = 'O pagamento online ainda não está configurado para sua empresa.';
                links.hidden = false;
                resultado.replaceChildren(...dados.pagamentos.map(pagamento => criarCartao(pagamento)));
                status.textContent = dados.pagamentos.length ? '' : 'Nenhum pagamento cadastrado para sua empresa.';
            } catch (erro) {
                status.textContent = erro.message || 'Erro ao consultar os pagamentos.';
            }
            return;
        }
        let consulta = 0;

        function url(codigo, id, acao = '') {
            return endpoint + (id ? '/' + encodeURIComponent(id) : '') + acao + '?empresa=' + encodeURIComponent(codigo);
        }

        async function carregar() {
            const versao = ++consulta;
            const codigo = empresa.value;
            incluir.disabled = !codigo;
            resultado.replaceChildren();
            status.textContent = codigo ? 'Carregando pagamentos…' : 'Selecione a empresa para consultar os pagamentos.';
            if (!codigo) return;
            try {
                const dados = await CrudUI.request(url(codigo));
                if (versao !== consulta) return;
                for (const pagamento of dados.pagamentos) {
                    resultado.append(criarCartao(pagamento,
                        () => abrirFormulario(codigo, pagamento),
                        botao => duplicarPagamento(codigo, pagamento, botao),
                        botao => excluirPagamento(codigo, pagamento, botao)));
                }
                status.textContent = dados.pagamentos.length ? '' : 'Nenhum pagamento cadastrado para esta empresa.';
            } catch (erro) {
                if (versao === consulta) status.textContent = erro.message;
            }
        }

        function abrirFormulario(codigo, pagamento = {}) {
            CrudUI.openForm({
                title: pagamento.id ? 'Editar pagamento' : 'Incluir pagamento',
                fields: [
                    {name: 'empresa', label: 'Empresa', type: 'static', value: empresa.selectedOptions[0].text, wide: true},
                    {name: 'dataprevpag', label: 'Data prevista', type: 'date', value: pagamento.dataprevpag},
                    {name: 'datapagrealiz', label: 'Data do pagamento', type: 'date', value: pagamento.datapagrealiz},
                    {name: 'valorprev', label: 'Valor previsto (R$)', inputMode: 'decimal', value: pagamento.valorprev},
                    {name: 'valorpag', label: 'Valor pago (R$)', inputMode: 'decimal', value: pagamento.valorpag},
                    {name: 'tipopag', label: 'Tipo de pagamento', type: 'textarea', rows: 1, value: pagamento.tipopag, wide: true}
                ],
                onSubmit: async function (dados) {
                    await CrudUI.request(url(codigo, pagamento.id), {
                        method: pagamento.id ? 'PUT' : 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(dados)
                    });
                    if (empresa.value === codigo) await carregar();
                    CrudUI.notify('Pagamento salvo.');
                }
            });
        }

        async function duplicarPagamento(codigo, pagamento, botao) {
            botao.disabled = true;
            try {
                const dados = await CrudUI.request(url(codigo, pagamento.id, '/duplicar'), {method: 'POST'});
                CrudUI.notify('Cobrança incluída para ' + formatarData(dados.dataprevpag) + '.');
                if (empresa.value === codigo) await carregar();
            } catch (erro) {
                CrudUI.notify(erro.message, 'error');
            } finally {
                botao.disabled = false;
            }
        }

        async function excluirPagamento(codigo, pagamento, botao) {
            if (!window.confirm('Excluir este pagamento de ' + empresa.selectedOptions[0].text + '?')) return;
            botao.disabled = true;
            try {
                await CrudUI.request(url(codigo, pagamento.id), {method: 'DELETE'});
                CrudUI.notify('Pagamento excluído.');
                if (empresa.value === codigo) await carregar();
            } catch (erro) {
                CrudUI.notify(erro.message, 'error');
            } finally {
                botao.disabled = false;
            }
        }

        empresa.addEventListener('change', carregar);
        incluir.addEventListener('click', () => abrirFormulario(empresa.value));
        status.textContent = 'Carregando empresas…';
        try {
            const dados = await CrudUI.request(endpoint);
            if (!Array.isArray(dados.empresas)) {
                throw new Error('O servidor está usando uma versão antiga de Pagamentos. Reinicie o Medsoft e abra a tela novamente.');
            }
            for (const item of dados.empresas) {
                empresa.add(new Option(item.id + ' - ' + item.nome, item.id));
            }
            empresa.disabled = !dados.empresas.length;
            status.textContent = dados.empresas.length ? 'Selecione a empresa para consultar os pagamentos.' : 'Nenhuma empresa cadastrada.';
        } catch (erro) {
            status.textContent = erro.message || 'Erro ao consultar os pagamentos.';
        }
    }

    window.PagamentosEmpresa = {init};
    init();
})();
