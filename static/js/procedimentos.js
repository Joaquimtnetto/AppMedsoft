(function () {
    var controller;
    var planoOptions = [{value: '', label: ''}];

    function headers() {
        return {
            'Content-Type': 'application/json',
            'X-DB-PATH': localStorage.getItem('db_path') || ''
        };
    }

    async function api(url, method, body) {
        return CrudUI.request(url, {
            method: method,
            headers: headers(),
            body: body ? JSON.stringify(body) : undefined
        });
    }

    function searchTerm() {
        return document.getElementById('procedimento-busca').value;
    }

    async function loadPlanos() {
        var data = await api('/api/planos', 'POST', {termo: ''});
        planoOptions = [{value: '', label: ''}].concat((data.planos || []).map(function (plano) {
            var nome = plano.nome || plano.id || '';
            return {value: nome, label: nome};
        }));
    }

    function formatCurrency(value) {
        if (value === null || value === undefined || value === '') return '';
        var numeric = Number(String(value).replace(',', '.'));
        if (!Number.isFinite(numeric)) return CrudUI.escapeHtml(value);
        return numeric.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    }

    function formatDecimal(value) {
        if (value === null || value === undefined || value === '') return '';
        var numeric = Number(String(value).replace(',', '.'));
        if (!Number.isFinite(numeric)) return String(value);
        return numeric.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function formatInteger(value) {
        if (value === null || value === undefined || value === '') return '';
        var numeric = Number(String(value).replace(',', '.'));
        if (!Number.isFinite(numeric)) return String(value);
        return String(Math.trunc(numeric));
    }

    function planoOptionsFor(item) {
        var currentValue = (item && item.plano) || '';
        var options = planoOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'descricao', label: 'Descricao', value: item.descricao || '', required: true, maxLength: 120},
            {name: 'plano', label: 'Plano', type: 'select', value: item.plano || '', required: true, options: planoOptionsFor(item)},
            {name: 'valor', label: 'Valor', type: 'text', value: formatDecimal(item.valor), inputMode: 'decimal', placeholder: '0,00'},
            {
                name: 'percrateio',
                label: 'Prof. Saúde (%)',
                type: 'number',
                value: formatInteger(item.percrateio),
                inputMode: 'numeric',
                placeholder: '0',
                min: 0,
                max: 100,
                step: 1
            }
        ];
    }

    function renderItem(item) {
        return '<article class="crud-card procedimento-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.descricao) + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '</div></div><div class="crud-card-details">' +
            '<span><i class="fa fa-id-card"></i> <strong>Plano:</strong> ' +
            CrudUI.escapeHtml(item.plano || '') + '</span>' +
            '<span><i class="fa fa-money-bill"></i> <strong>Valor:</strong> ' +
            formatCurrency(item.valor) + '</span>' +
            '<span><i class="fa fa-user-doctor"></i> <strong>Prof. Saúde:</strong> ' +
            (formatInteger(item.percrateio) || '0') + '%</span>' +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.id +
            '" title="Alterar procedimento"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.id +
            '" title="Excluir procedimento"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.id; },
            createTitle: 'Incluir procedimento',
            editTitle: 'Alterar procedimento',
            formClass: 'procedimento-form',
            emptyMessage: 'Nenhum procedimento encontrado.',
            beforeOpen: loadPlanos,
            fields: fields,
            renderItem: renderItem,
            list: async function () {
                var data = await api('/api/procedimentos', 'POST', {termo: searchTerm()});
                return data.procedimentos || [];
            },
            create: function (values) { return api('/api/procedimentos/itens', 'POST', values); },
            update: function (item, values) {
                return api('/api/procedimentos/itens/' + encodeURIComponent(item.id), 'PUT', values);
            },
            delete: function (item) { return api('/api/procedimentos/itens/' + encodeURIComponent(item.id), 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o procedimento ' + item.descricao + '?';
            }
        });
    }

    function init() {
        var page = document.getElementById('procedimento-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';

        controller = createController().mount({
            root: page,
            list: document.getElementById('procedimento-result'),
            includeButton: document.getElementById('procedimento-include')
        });

        document.getElementById('procedimento-btn-buscar').onclick = function () { controller.reload(); };
        document.getElementById('procedimento-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        controller.reload();
    }

    window.ProcedimentoConsulta = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
