(function () {
    function api(path, method, body) {
        return CrudUI.request(path, {
            method: method || 'POST',
            headers: {'Content-Type': 'application/json'},
            body: body ? JSON.stringify(body) : undefined
        });
    }

    function yesNo(value) {
        return String(value || '').toUpperCase() === 'S' ? 'Sim' : 'Não';
    }

    function yesNoField(name, label, value) {
        return {
            name: name, label: label, type: 'select',
            value: String(value || '').toUpperCase() === 'S' ? 'S' : 'N',
            options: [{value: 'S', label: 'Sim'}, {value: 'N', label: 'Não'}]
        };
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'plano', label: 'Nome do plano', value: item.plano || '', maxLength: 80, required: true, wide: true},
            {name: 'descricao', label: 'Descrição', value: item.descricao || '', type: 'textarea', rows: 3, wide: true},
            {name: 'valor', label: 'Valor (R$)', value: item.valor || '', type: 'number', inputMode: 'decimal', step: '0.01', min: '0'},
            {name: 'qtdusuarios', label: 'Quantidade de Usuários', value: item.qtdusuarios || 0, type: 'number', min: '0', max: '2147483647'},
            yesNoField('confagenda', 'Confirma Agenda', item.confagenda),
            {name: 'qtdpacientes', label: 'Quantidade de Pacientes', value: item.qtdpacientes || 0, type: 'number', min: '0', max: '2147483647'},
            yesNoField('teleconsulta', 'Teleconsulta', item.teleconsulta),
            yesNoField('financeiro', 'Financeiro', item.financeiro),
            yesNoField('ditadovoz', 'Histórico por Voz', item.ditadovoz),
            {name: 'datamax', label: 'Data Máxima', value: item.datamax || '', type: 'date'},
            {name: 'diasmax', label: 'Dias de uso', value: item.diasmax || 0, type: 'number', min: '0', max: '2147483647', step: '1'}
        ];
    }

    function detail(label, value) {
        return '<span><strong>' + label + ':</strong> ' + CrudUI.escapeHtml(value) + '</span>';
    }

    function renderItem(item) {
        return '<article class="crud-card"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.plano || '') + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '<div class="crud-card-details">' +
            detail('Valor', Number(item.valor || 0).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})) +
            detail('Usuários', item.qtdusuarios) + detail('Pacientes', item.qtdpacientes) +
            detail('Confirma agenda', yesNo(item.confagenda)) + detail('Teleconsulta', yesNo(item.teleconsulta)) +
            detail('Financeiro', yesNo(item.financeiro)) + detail('Histórico por Voz', yesNo(item.ditadovoz)) +
            detail('Data Máxima', item.datamax ? item.datamax.split('-').reverse().join('/') : '') +
            detail('Dias de uso', item.diasmax) +
            '</div></div><div class="crud-card-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.id + '">' +
            '<i class="fa fa-pen"></i> Editar</button></div></article>';
    }

    function init() {
        var page = document.getElementById('plano-empresa-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var search = document.getElementById('plano-empresa-busca');
        var controller = new CrudUI.Controller({
            getId: function (item) { return item.id; },
            list: async function () {
                var result = await api('/api/planos-empresa', 'POST', {termo: search.value});
                return result.planos || [];
            },
            createTitle: 'Incluir plano', editTitle: 'Alterar plano', fields: fields,
            create: function (values) { return api('/api/planos-empresa/itens', 'POST', values); },
            update: function (item, values) {
                return api('/api/planos-empresa/itens/' + encodeURIComponent(item.id), 'PUT', values);
            },
            renderItem: renderItem, emptyMessage: 'Nenhum plano encontrado.'
        }).mount({
            root: page, list: document.getElementById('plano-empresa-result'),
            includeButton: document.getElementById('plano-empresa-incluir')
        });
        document.getElementById('plano-empresa-pesquisar').onclick = function () { controller.reload(); };
        search.addEventListener('keydown', function (event) { if (event.key === 'Enter') controller.reload(); });
        controller.reload();
    }

    window.PlanoEmpresaCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
