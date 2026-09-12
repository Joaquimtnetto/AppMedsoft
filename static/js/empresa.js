(function () {
    var canEdit = false;
    var planosCadastrados = [];

    function headers() {
        return {
            'Content-Type': 'application/json',
            'X-DB-PATH': localStorage.getItem('db_path') || ''
        };
    }

    function api(path, method, body) {
        return CrudUI.request(path, {
            method: method || 'POST',
            headers: headers(),
            body: body ? JSON.stringify(body) : undefined
        });
    }

    function renderEmpresa(item) {
        var status = item.ativo === false ? 'Inativa' : 'Ativa';
        var actions = canEdit
            ? '<div class="crud-card-actions">' +
                '<button class="crud-button crud-button-secondary" data-crud-edit="' + CrudUI.escapeHtml(item.id) + '">' +
                    '<i class="fa fa-pen"></i> Editar</button>' +
            '</div>'
            : '';
        return '<article class="crud-card">' +
            '<div class="crud-card-main">' +
                '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome || '') + '</div>' +
                '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
                '<div class="crud-card-details">' +
                    '<span><i class="fa fa-database"></i> ' + CrudUI.escapeHtml(item.database || '') + '</span>' +
                    '<span><i class="fa fa-circle-check"></i> ' + CrudUI.escapeHtml(status) + '</span>' +
                '</div>' +
            '</div>' +
            actions +
        '</article>';
    }

    function fields(item) {
        item = item || {};
        var planOptions = [{value: '', label: 'Selecione'}].concat(
            planosCadastrados.map(function (plan) {
                return {value: String(plan.id), label: plan.nome || String(plan.id)};
            })
        );
        if (item.plano && !planOptions.some(function (option) { return String(option.value) === String(item.plano); })) {
            planOptions.push({value: String(item.plano), label: 'Plano #' + item.plano});
        }
        return [
            {name: 'nome', label: 'Empresa', value: item.nome || '', maxLength: 120, required: true, wide: true},
            {name: 'database', label: 'Banco de dados', value: item.database || '', maxLength: 120, required: true, wide: true},
            {name: 'email', label: 'E-mail', value: item.email || '', type: 'email', maxLength: 120, wide: true},
            {name: 'telefone', label: 'Telefone', value: item.telefone || '', type: 'tel', maxLength: 20},
            {name: 'whatsapp', label: 'WhatsApp', value: item.whatsapp || '', type: 'tel', maxLength: 20},
            {name: 'plano', label: 'Plano', value: item.plano || '', type: 'select', options: planOptions},
            {name: 'datainico', label: 'Data de Início', value: item.datainico || '', type: 'date'},
            {
                name: 'pago', label: 'Pago', value: item.pago === 'S' ? 'S' : 'N', type: 'select',
                options: [{value: 'S', label: 'Sim'}, {value: 'N', label: 'Não'}]
            },
            {name: 'titulo1', label: 'Título 1', value: item.titulo1 || '', maxLength: 120, wide: true},
            {name: 'titulo2', label: 'Título 2', value: item.titulo2 || '', maxLength: 120, wide: true},
            {
                name: 'ativo',
                label: 'Situação',
                value: item.ativo === false ? 'N' : 'S',
                type: 'select',
                options: [
                    {value: 'S', label: 'Ativa'},
                    {value: 'N', label: 'Inativa'}
                ]
            }
        ];
    }

    function values(payload) {
        return {
            nome: payload.nome,
            database: payload.database,
            ativo: payload.ativo !== 'N',
            email: payload.email,
            telefone: payload.telefone,
            whatsapp: payload.whatsapp,
            plano: payload.plano,
            datainico: payload.datainico,
            pago: payload.pago,
            titulo1: payload.titulo1,
            titulo2: payload.titulo2
        };
    }

    async function applyPermission() {
        var includeButton = document.getElementById('empresa-incluir');
        if (!includeButton) return;
        try {
            var result = await api('/api/empresas/permissao', 'POST');
            canEdit = !!result.pode_editar;
            includeButton.hidden = !canEdit;
            includeButton.disabled = !canEdit;
        } catch (error) {
            canEdit = false;
            includeButton.hidden = true;
            includeButton.disabled = true;
        }
    }

    async function loadCompanyPlans() {
        try {
            var result = await api('/api/empresas/planos', 'POST');
            planosCadastrados = result.planos || [];
        } catch (error) {
            planosCadastrados = [];
            CrudUI.notify('Não foi possível carregar os planos da empresa.', 'error');
        }
    }

    function init() {
        var page = document.getElementById('empresa-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';

        var search = document.getElementById('empresa-busca');
        var controller = new CrudUI.Controller({
            getId: function (item) { return item.id; },
            list: async function () {
                var result = await api('/api/empresas', 'POST', {termo: search.value});
                return result.empresas || [];
            },
            createTitle: 'Incluir empresa',
            editTitle: 'Alterar empresa',
            fields: fields,
            create: function (payload) {
                return api('/api/empresas/itens', 'POST', values(payload));
            },
            update: function (item, payload) {
                return api('/api/empresas/itens/' + encodeURIComponent(item.id), 'PUT', values(payload));
            },
            renderItem: renderEmpresa,
            emptyMessage: 'Nenhuma empresa encontrada.'
        }).mount({
            root: page,
            list: document.getElementById('empresa-result'),
            includeButton: document.getElementById('empresa-incluir')
        });

        document.getElementById('empresa-pesquisar').onclick = function () { controller.reload(); };
        search.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        Promise.all([applyPermission(), loadCompanyPlans()]).then(function () { controller.reload(); });
    }

    window.EmpresaCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
