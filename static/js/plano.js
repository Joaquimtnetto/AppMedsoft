(function () {
    var controller;
    var optionsMode = false;

    function headers() {
        return {
            'Content-Type': 'application/json',
            'X-DB-PATH': localStorage.getItem('db_path') || ''
        };
    }

    function api(url, method, body) {
        return CrudUI.request(url, {
            method: method,
            headers: headers(),
            body: body ? JSON.stringify(body) : undefined
        });
    }

    function searchTerm() {
        return document.getElementById('plano-busca').value;
    }

    function setupCepLookup(backdrop) {
        var cep = backdrop.querySelector('[name="cep"]');
        if (!cep) return;
        var lastCep = '';

        async function lookupCep() {
            var digits = cep.value.replace(/\D/g, '');
            if (digits.length !== 8) return;
            if (digits === lastCep) return;
            lastCep = digits;
            try {
                var response = await fetch('https://viacep.com.br/ws/' + digits + '/json/');
                var data = await response.json();
                if (!response.ok || data.erro) throw new Error('CEP não encontrado.');
                var endereco = backdrop.querySelector('[name="endereco"]');
                var bairro = backdrop.querySelector('[name="bairro"]');
                var cidade = backdrop.querySelector('[name="cidade"]');
                if (endereco) endereco.value = data.logradouro || endereco.value;
                if (bairro) bairro.value = data.bairro || bairro.value;
                if (cidade) cidade.value = data.localidade || cidade.value;
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível consultar o CEP.', 'error');
            }
        }

        cep.addEventListener('input', lookupCep);
        cep.addEventListener('blur', lookupCep);
        cep.addEventListener('change', lookupCep);
    }

    function fields(item) {
        item = item || {};
        var tabelaOptions = [
            {value: '', label: ''},
            {value: 'AMB 90', label: 'AMB 90'},
            {value: 'AMB 92', label: 'AMB 92'},
            {value: 'AMB 96', label: 'AMB 96'},
            {value: 'AMB 99', label: 'AMB 99'},
            {value: 'TUSS', label: 'TUSS'},
            {value: 'SIGTAP', label: 'SIGTAP'},
            {value: 'CBHPM', label: 'CBHPM'}
        ];
        if (item.tabela && !tabelaOptions.some(function (option) { return option.value === item.tabela; })) {
            tabelaOptions.push({value: item.tabela, label: item.tabela});
        }
        return [
            {name: 'nome', label: 'Nome', value: item.nome || '', required: true, className: 'plano-field-nome'},
            {
                name: 'tabela',
                label: 'Tabela',
                type: 'select',
                value: item.tabela || '',
                className: 'plano-field-tabela',
                options: tabelaOptions
            },
            {name: 'ans', label: 'ANS', value: item.ans || '', maxLength: 20, className: 'plano-field-ans'},
            {
                name: 'cep',
                label: 'CEP',
                value: item.cep || '',
                mask: 'cep-br',
                placeholder: '99999-99',
                maxLength: 9,
                inputMode: 'numeric',
                className: 'plano-field-cep'
            },
            {name: 'endereco', label: 'Endereço', value: item.endereco || '', maxLength: 40, className: 'plano-field-endereco'},
            {name: 'bairro', label: 'Bairro', value: item.bairro || '', maxLength: 15, className: 'plano-field-bairro'},
            {name: 'cidade', label: 'Cidade', value: item.cidade || '', maxLength: 10, className: 'plano-field-cidade'},
            {name: 'banco', label: 'Banco', value: item.banco || '', maxLength: 15, className: 'plano-field-banco'},
            {
                name: 'prazo',
                label: 'Prazo (Dias)',
                type: 'number',
                value: item.prazo || '',
                inputMode: 'numeric',
                className: 'plano-field-prazo'
            },
            {
                name: 'valorch',
                label: 'Valor CH (R$)',
                type: 'number',
                value: item.valorch || '',
                inputMode: 'decimal',
                className: 'plano-field-valorch'
            },
            {
                name: 'telefone', label: 'Telefone', type: 'tel', value: item.telefone || '',
                mask: 'phone-br-landline', placeholder: '(99)9999-9999', maxLength: 13,
                inputMode: 'numeric', className: 'plano-field-telefone'
            },
            {
                name: 'observacao',
                label: 'Observação',
                type: 'textarea',
                value: item.observacao || '',
                maxLength: 400,
                rows: 4,
                wide: true,
                className: 'plano-field-observacao'
            }
        ];
    }

    function detail(label, value, icon) {
        return '<span><i class="fa ' + icon + '"></i> <strong>' + label + ':</strong> ' +
            CrudUI.escapeHtml(value || '') + '</span>';
    }

    function renderItem(item) {
        return '<article class="crud-card plano-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome) + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '</div></div><div class="crud-card-details">' +
            detail('Tabela', item.tabela, 'fa-table') +
            detail('ANS', item.ans, 'fa-id-card') +
            detail('Telefone', item.telefone, 'fa-phone') +
            detail('Cidade', item.cidade, 'fa-location-dot') +
            detail('Valor CH', item.valorch, 'fa-money-bill') +
            (optionsMode ? detail('Empresa', item.empresa_id, 'fa-building') : '') +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' +
            CrudUI.escapeHtml(optionsMode ? item._option_key : item.id) +
            '" title="Alterar plano"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            (optionsMode ? '' : '<button class="crud-button crud-button-danger" data-crud-delete="' + item.id +
            '" title="Excluir plano"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button>') + '</div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return optionsMode ? item._option_key : item.id; },
            createTitle: 'Incluir plano',
            editTitle: 'Alterar plano',
            formClass: 'plano-form',
            emptyMessage: 'Nenhum plano encontrado.',
            fields: fields,
            renderItem: renderItem,
            onFormReady: setupCepLookup,
            list: async function () {
                var endpoint = optionsMode ? '/api/planos/opcoes' : '/api/planos';
                var data = await api(endpoint, 'POST', {termo: searchTerm()});
                return data.planos || [];
            },
            create: function (values) { return api('/api/planos/itens', 'POST', values); },
            update: function (item, values) {
                if (optionsMode) return api('/api/planos/itens', 'POST', values);
                return api('/api/planos/itens/' + encodeURIComponent(item.id), 'PUT', values);
            },
            delete: function (item) { return api('/api/planos/itens/' + encodeURIComponent(item.id), 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o plano ' + item.nome + '?';
            }
        });
    }

    function init() {
        var page = document.getElementById('plano-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        optionsMode = false;
        page.classList.remove('options-mode');
        document.getElementById('plano-options').innerHTML = '<i class="fa fa-list"></i> Opções';
        document.getElementById('plano-include').hidden = false;

        controller = createController().mount({
            root: page,
            list: document.getElementById('plano-result'),
            includeButton: document.getElementById('plano-include')
        });

        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        var optionsButton = document.getElementById('plano-options');
        var includeButton = document.getElementById('plano-include');
        optionsButton.onclick = function () {
            optionsMode = !optionsMode;
            optionsButton.innerHTML = optionsMode
                ? '<i class="fa fa-arrow-left"></i> Meus planos'
                : '<i class="fa fa-list"></i> Opções';
            includeButton.hidden = optionsMode;
            controller.reload();
        };
        document.getElementById('plano-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        controller.reload();
    }

    window.PlanoCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
