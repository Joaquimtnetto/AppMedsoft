(function () {
    var controller;

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

    function selectedDate() {
        return document.getElementById('agenda-date').value;
    }

    function today() {
        var date = new Date();
        return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' +
            String(date.getDate()).padStart(2, '0');
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'data', label: 'Data', type: 'date', value: item.DATACONS || selectedDate(), required: true},
            {name: 'hora', label: 'Horário', type: 'time', value: item.HORACONS || '', required: true},
            {name: 'paciente', label: 'Paciente', value: item.NOMEPACI || '', required: true, wide: true},
            {
                name: 'telefone', label: 'Telefone', type: 'tel', value: item.TELEFONE || '',
                mask: 'phone-br-landline', placeholder: '(99)9999-9999', maxLength: 13,
                inputMode: 'numeric'
            },
            {name: 'plano', label: 'Plano', value: item.NOMEPLANO || ''},
            {name: 'procedimento', label: 'Procedimento', value: item.PROCED || '', wide: true}
        ];
    }

    function renderItem(item) {
        return '<article class="crud-card">' +
            '<div class="crud-card-header"><span class="crud-time"><i class="fa fa-clock"></i> ' +
            CrudUI.escapeHtml(item.HORACONS) + '</span>' +
            '<div class="crud-card-main"><div class="crud-card-title">' + CrudUI.escapeHtml(item.NOMEPACI) +
            '</div></div></div><div class="crud-card-details">' +
            '<span><i class="fa fa-phone"></i> ' + CrudUI.escapeHtml(item.TELEFONE || 'Sem telefone') + '</span>' +
            '<span><i class="fa fa-id-card"></i> ' + CrudUI.escapeHtml(item.NOMEPLANO || 'Sem plano') + '</span>' +
            '<span><i class="fa fa-stethoscope"></i> ' + CrudUI.escapeHtml(item.PROCED || 'Sem procedimento') + '</span>' +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-action="patient" data-crud-id="' +
            item.CODAGEND + '" title="Consultar paciente"><i class="fa fa-user"></i>' +
            '<span class="crud-button-label"> Paciente</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.CODAGEND +
            '" title="Alterar compromisso"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.CODAGEND +
            '" title="Excluir compromisso"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.CODAGEND; },
            createTitle: 'Incluir compromisso',
            editTitle: 'Alterar compromisso',
            emptyMessage: 'Nenhum compromisso encontrado para esta data.',
            fields: fields,
            renderItem: renderItem,
            list: async function () {
                if (!selectedDate()) throw new Error('Selecione uma data.');
                var data = await api('/api/agenda', 'POST', {data: selectedDate()});
                return data.resultados || [];
            },
            create: function (values) { return api('/api/agenda/itens', 'POST', values); },
            update: function (item, values) {
                return api('/api/agenda/itens/' + item.CODAGEND, 'PUT', values);
            },
            delete: function (item) { return api('/api/agenda/itens/' + item.CODAGEND, 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o compromisso de ' + item.NOMEPACI + ' às ' + item.HORACONS + '?';
            },
            afterSave: function (values) { document.getElementById('agenda-date').value = values.data; },
            onAction: function (action, item) {
                if (action === 'patient' && item && window.carregarTela) {
                    window.pacienteAgendaPendente = item.NOMEPACI.trim();
                    window.carregarTela('consulta_paciente.html');
                }
            }
        });
    }

    function init() {
        var page = document.getElementById('agenda-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var dateInput = document.getElementById('agenda-date');
        if (!dateInput.value) dateInput.value = today();
        controller = createController().mount({
            root: page,
            list: document.getElementById('agenda-result'),
            includeButton: document.getElementById('agenda-include')
        });
        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        controller.reload();
    }

    window.AgendaCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
