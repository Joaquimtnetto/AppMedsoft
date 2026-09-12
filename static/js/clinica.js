(function () {
    var controller;
    var empresasCadastradas = [];

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
        return document.getElementById('clinica-busca').value;
    }

    function ufOptions() {
        return ['', 'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT',
            'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR',
            'SC', 'SP', 'SE', 'TO'].map(function (uf) {
            return {value: uf, label: uf};
        });
    }

    function optionLabel(id, name) {
        if (!id && !name) return '';
        return (name || '') + (id ? ' - ' + id : '');
    }

    function empresaOptions(item) {
        item = item || {};
        var options = [{value: '', label: ''}];
        empresasCadastradas.forEach(function (empresa) {
            var value = String(empresa.id || '');
            if (!value) return;
            if (!options.some(function (option) { return String(option.value) === value; })) {
                options.push({value: value, label: optionLabel(empresa.id, empresa.nome)});
            }
        });
        if (item.idempresa && !options.some(function (option) { return String(option.value) === String(item.idempresa); })) {
            options.push({value: item.idempresa, label: item.idempresa_nome || item.idempresa});
        }
        return options;
    }

    function empresaNome(id) {
        var empresa = empresasCadastradas.find(function (item) {
            return String(item.id || '') === String(id || '');
        });
        return empresa ? empresa.nome : '';
    }

    async function carregarEmpresas() {
        try {
            var data = await api('/api/empresas', 'POST', {termo: ''});
            empresasCadastradas = data.empresas || [];
        } catch (error) {
            empresasCadastradas = [];
            CrudUI.notify('Nao foi possivel carregar as empresas cadastradas.', 'error');
        }
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
                var municipio = backdrop.querySelector('[name="municipio"]');
                var uf = backdrop.querySelector('[name="uf"]');
                if (endereco) endereco.value = data.logradouro || endereco.value;
                if (bairro) bairro.value = data.bairro || bairro.value;
                if (municipio) municipio.value = data.localidade || municipio.value;
                if (uf) uf.value = data.uf || uf.value;
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
        return [
            {name: 'idempresa', label: 'Empresa', value: item.idempresa || '', type: 'select', options: empresaOptions(item), required: true, wide: true},
            {name: 'nome', label: 'Nome', value: item.nome || '', required: true, maxLength: 60, className: 'clinica-field-nome'},
            {name: 'uf', label: 'UF', type: 'select', value: item.uf || '', options: ufOptions(), className: 'clinica-field-uf'},
            {name: 'cep', label: 'Cep', value: item.cep || '', mask: 'cep-br', placeholder: '99999-99', maxLength: 9, inputMode: 'numeric'},
            {name: 'municipio', label: 'Município', value: item.municipio || '', maxLength: 30},
            {name: 'endereco', label: 'Endereço', value: item.endereco || '', maxLength: 60, className: 'clinica-field-endereco'},
            {name: 'bairro', label: 'Bairro', value: item.bairro || '', maxLength: 30},
            {name: 'especialidade', label: 'Especialidade', value: item.especialidade || '', maxLength: 40},
            {name: 'nrconselho', label: 'Nr. Conselho', value: item.nrconselho || '', maxLength: 20},
            {name: 'conselho', label: 'Conselho', value: item.conselho || '', maxLength: 20},
            {name: 'cnpj', label: 'Cnpj', value: item.cnpj || '', mask: 'cnpj-br', placeholder: '99.999.999/9999-99', maxLength: 18, inputMode: 'numeric'},
            {name: 'telefone', label: 'Telefone', value: item.telefone || '', mask: 'phone-br-landline', placeholder: '(99)9999-9999', maxLength: 13, inputMode: 'numeric'},
            {name: 'celular', label: 'Celular', value: item.celular || '', mask: 'phone-br', placeholder: '(99)99999-9999', maxLength: 14, inputMode: 'numeric'},
            {name: 'email', label: 'Email', value: item.email || '', type: 'email', maxLength: 60, className: 'clinica-field-email'},
            {name: 'observacao', label: 'Observação', value: item.observacao || '', type: 'textarea', rows: 3, maxLength: 400, className: 'clinica-field-observacao'}
        ];
    }

    function payload(values) {
        return {
            idempresa: values.idempresa,
            nome: values.nome,
            uf: values.uf,
            municipio: values.municipio,
            endereco: values.endereco,
            bairro: values.bairro,
            cep: values.cep,
            especialidade: values.especialidade,
            nrconselho: values.nrconselho,
            conselho: values.conselho,
            cnpj: values.cnpj,
            telefone: values.telefone,
            celular: values.celular,
            email: values.email,
            observacao: values.observacao
        };
    }

    function detail(label, value, icon) {
        return '<span><i class="fa ' + icon + '"></i> <strong>' + label + ':</strong> ' +
            CrudUI.escapeHtml(value || '') + '</span>';
    }

    function renderItem(item) {
        return '<article class="crud-card clinica-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome) + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '</div></div><div class="crud-card-details">' +
            detail('Empresa', item.idempresa_nome || empresaNome(item.idempresa) || item.idempresa, 'fa-building') +
            detail('Município', item.municipio, 'fa-location-dot') +
            detail('Telefone', item.telefone || item.celular, 'fa-phone') +
            detail('Especialidade', item.especialidade, 'fa-stethoscope') +
            detail('CNPJ', item.cnpj, 'fa-building') +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.id +
            '" title="Alterar clínica"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.id +
            '" title="Excluir clínica"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.id; },
            createTitle: 'Incluir Clínica',
            editTitle: 'Alterar Clínica',
            formClass: 'clinica-form',
            emptyMessage: 'Nenhuma clínica encontrada.',
            fields: fields,
            renderItem: renderItem,
            onFormReady: setupCepLookup,
            list: async function () {
                var data = await api('/api/clinicas', 'POST', {termo: searchTerm()});
                return data.clinicas || [];
            },
            create: function (values) { return api('/api/clinicas/itens', 'POST', payload(values)); },
            update: function (item, values) {
                return api('/api/clinicas/itens/' + encodeURIComponent(item.id), 'PUT', payload(values));
            },
            delete: function (item) { return api('/api/clinicas/itens/' + encodeURIComponent(item.id), 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir a clínica ' + item.nome + '?';
            }
        });
    }

    async function applyIncludePermission() {
        var includeButton = document.getElementById('clinica-include');
        if (!includeButton) return;

        try {
            var data = await api('/api/clinicas/permissao', 'POST');
            if (data.pode_incluir) {
                includeButton.hidden = false;
                includeButton.disabled = false;
                return;
            }
        } catch (error) {
            CrudUI.notify(error.message || 'Nao foi possivel validar a permissao para incluir clinica.', 'error');
        }

        includeButton.hidden = true;
        includeButton.disabled = true;
    }

    function init() {
        var page = document.getElementById('clinica-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';

        controller = createController().mount({
            root: page,
            list: document.getElementById('clinica-result'),
            includeButton: document.getElementById('clinica-include')
        });

        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        document.getElementById('clinica-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        applyIncludePermission();
        carregarEmpresas().then(function () { controller.reload(); });
    }

    window.ClinicaCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
