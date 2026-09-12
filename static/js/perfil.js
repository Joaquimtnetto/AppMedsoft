(function () {
    var usuarioMaster = false;
    var menuOptions = [
        {value: '1', label: 'Paciente'}, {value: '2', label: 'Agenda'},
        {value: '3', label: 'Plano'}, {value: '4', label: 'Padrões'},
        {value: '5', label: 'Financeiro'}, {value: '6', label: 'Configuração'},
        {value: '7', label: 'Clínica'}, {value: '8', label: 'Prof. de Saúde'},
        {value: '9', label: 'Usuário'}, {value: '10', label: 'Procedimentos'},
        {value: '11', label: 'Config. e-mail'}, {value: '12', label: 'Config. Watzap'},
        {value: '13', label: 'Msg Enviadas'}, {value: '14', label: 'Perfil'},
        {value: '15', label: 'Empresa'}
    ];

    function permissionRows(item) {
        var rows = [];
        for (var number = 1; number <= 15; number++) {
            var value = String((item && item['menu' + number]) || (number + '-AM-ET')).toUpperCase();
            var match = value.match(/^(\d+)-(AM|NAM)-(ET|NET)$/);
            rows.push({
                name: 'menu' + number,
                menu: match ? match[1] : String(number),
                open: match ? match[2] : 'AM',
                edit: match ? match[3] : 'ET'
            });
        }
        return rows;
    }

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

    function renderPerfil(item) {
        var status = item.ativo === false ? 'Inativo' : 'Ativo';
        var perfilMasterProtegido = String(item.nome || '').trim().toUpperCase() === 'MASTER' && !usuarioMaster;
        var actions = perfilMasterProtegido ?
            '<span class="crud-badge" title="Somente usuários Master podem alterar este perfil">Protegido</span>' :
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + CrudUI.escapeHtml(item.id) + '">' +
                '<i class="fa fa-pen"></i> Editar</button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + CrudUI.escapeHtml(item.id) + '">' +
                '<i class="fa fa-trash"></i> Excluir</button>';
        return '<article class="crud-card">' +
            '<div class="crud-card-main">' +
                '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome || '') + '</div>' +
                '<div class="crud-card-details">' +
                    '<span><i class="fa fa-id-badge"></i> ' + CrudUI.escapeHtml(status) + '</span>' +
                    '<span><i class="fa fa-align-left"></i> ' + CrudUI.escapeHtml(item.descricao || 'Sem descrição') + '</span>' +
                '</div>' +
            '</div>' +
            '<div class="crud-card-actions">' +
                actions +
            '</div>' +
        '</article>';
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'nome', label: 'Perfil', value: item.nome || '', maxLength: 60, required: true, wide: true},
            {name: 'descricao', label: 'Descrição', value: item.descricao || '', maxLength: 200, wide: true},
            {
                name: 'ativo',
                label: 'Situação',
                value: item.ativo === false ? 'N' : 'S',
                type: 'select',
                options: [
                    {value: 'S', label: 'Ativo'},
                    {value: 'N', label: 'Inativo'}
                ]
            },
            {
                name: 'verhist',
                label: 'Visualiza Histórico Clínico',
                value: String(item.verhist || 'SIM').toUpperCase() === 'NÃO' ? 'NÃO' : 'SIM',
                type: 'select',
                options: [
                    {value: 'SIM', label: 'SIM'},
                    {value: 'NÃO', label: 'NÃO'}
                ]
            },
            {
                name: 'verexame',
                label: 'Visualiza Histórico Exame',
                value: String(item.verexame || 'SIM').toUpperCase() === 'NÃO' ? 'NÃO' : 'SIM',
                type: 'select',
                options: [
                    {value: 'SIM', label: 'SIM'},
                    {value: 'NÃO', label: 'NÃO'}
                ]
            },
            {
                name: 'permissoes', label: 'Permissões dos menus', type: 'permission-grid',
                rows: permissionRows(item), menuOptions: menuOptions, wide: true,
                className: 'perfil-permission-field'
            }
        ];
    }

    function values(payload) {
        var result = {
            nome: payload.nome,
            descricao: payload.descricao,
            ativo: payload.ativo !== 'N',
            verhist: payload.verhist,
            verexame: payload.verexame
        };
        var selected = {};
        for (var number = 1; number <= 15; number++) {
            var menu = payload['menu' + number + '_menu'];
            if (selected[menu]) throw new Error('Cada menu deve ser selecionado apenas uma vez.');
            selected[menu] = true;
            result['menu' + number] = menu + '-' + payload['menu' + number + '_open'] + '-' + payload['menu' + number + '_edit'];
        }
        return result;
    }

    function init() {
        var page = document.getElementById('perfil-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';

        var search = document.getElementById('perfil-busca');
        var controller = new CrudUI.Controller({
            getId: function (item) { return item.id; },
            list: async function () {
                var result = await api('/api/perfis', 'POST', {termo: search.value});
                usuarioMaster = !!result.usuario_master;
                return result.perfis || [];
            },
            createTitle: 'Incluir perfil',
            editTitle: 'Editar perfil',
            formClass: 'perfil-form',
            fields: fields,
            create: function (payload) {
                return api('/api/perfis/itens', 'POST', values(payload));
            },
            update: function (item, payload) {
                return api('/api/perfis/itens/' + encodeURIComponent(item.id), 'PUT', values(payload));
            },
            delete: function (item) {
                return api('/api/perfis/itens/' + encodeURIComponent(item.id), 'DELETE');
            },
            confirmDelete: function (item) {
                return 'Excluir o perfil ' + item.nome + '?';
            },
            renderItem: renderPerfil,
            emptyMessage: 'Nenhum perfil encontrado.'
        }).mount({
            root: page,
            list: document.getElementById('perfil-result'),
            includeButton: document.getElementById('perfil-incluir')
        });

        document.getElementById('perfil-pesquisar').onclick = function () { controller.reload(); };
        search.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        controller.reload();
    }

    window.PerfilCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
