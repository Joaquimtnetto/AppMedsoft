(function () {
    var controller;
    var perfisCadastrados = null;
    var profissionaisCadastrados = null;
    var empresasCadastradas = null;
    var usuarioMaster = false;

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
        return document.getElementById('usuario-busca').value;
    }

    function valueOrEmpty(value) {
        return value === null || value === undefined ? '' : value;
    }

    function dateTimeLocalValue(value) {
        if (!value) return '';
        var text = String(value);
        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text)) return text.slice(0, 16);
        var date = new Date(text);
        if (Number.isNaN(date.getTime())) return '';
        var pad = function (number) { return String(number).padStart(2, '0'); };
        return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) +
            'T' + pad(date.getHours()) + ':' + pad(date.getMinutes());
    }

    function perfilOptions(item) {
        var options = [{value: '', label: ''}];
        (perfisCadastrados || []).forEach(function (perfil) {
            var value = perfil.nome || perfil.descricao || String(perfil.id || '');
            if (!value) return;
            if (!usuarioMaster && String(value).trim().toUpperCase() === 'MASTER') return;
            if (!options.some(function (option) { return option.value === value; })) {
                options.push({value: value, label: value});
            }
        });
        if (item && item.perfil && (usuarioMaster || String(item.perfil).trim().toUpperCase() !== 'MASTER') &&
                !options.some(function (option) { return option.value === item.perfil; })) {
            options.push({value: item.perfil, label: item.perfil});
        }
        return options;
    }

    function optionLabel(id, name) {
        if (!id && !name) return '';
        return (name || '') + (id ? ' - ' + id : '');
    }

    function cadastroOptions(items, itemValue, itemLabel, currentValue, currentLabel) {
        var options = [{value: '', label: ''}];
        (items || []).forEach(function (item) {
            var value = String(itemValue(item) || '');
            if (!value) return;
            var label = itemLabel(item) || value;
            if (!options.some(function (option) { return String(option.value) === value; })) {
                options.push({value: value, label: label});
            }
        });
        currentValue = valueOrEmpty(currentValue);
        if (currentValue && !options.some(function (option) { return String(option.value) === String(currentValue); })) {
            options.push({value: currentValue, label: currentLabel || currentValue});
        }
        return options;
    }

    function profissionalOptions(item) {
        item = item || {};
        return cadastroOptions(
            profissionaisCadastrados,
            function (profissional) { return profissional.id; },
            function (profissional) { return optionLabel(profissional.id, profissional.nome); },
            item.idcodmed || item.idprefere || item.codmed,
            item.codmed_nome || item.idcodmed || item.idprefere || item.codmed
        );
    }

    function empresaOptions(item) {
        item = item || {};
        return cadastroOptions(
            empresasCadastradas,
            function (empresa) { return empresa.id; },
            function (empresa) { return optionLabel(empresa.id, empresa.nome); },
            item.idempresa || item.codclin,
            item.empresa_nome || item.codclin_nome || item.idempresa || item.codclin
        );
    }

    async function carregarPerfis() {
        try {
            var data = await api('/api/perfis/opcoes', 'POST', {});
            perfisCadastrados = data.perfis || [];
        } catch (error) {
            perfisCadastrados = [];
            CrudUI.notify('Não foi possível carregar os perfis cadastrados.', 'error');
        }
    }

    async function carregarPermissaoUsuario() {
        try {
            var data = await api('/api/usuarios/permissao', 'POST', {});
            usuarioMaster = !!data.usuario_master;
        } catch (error) {
            usuarioMaster = false;
        }
    }

    async function carregarCadastros() {
        await carregarPermissaoUsuario();
        await Promise.all([
            carregarPerfis(),
            api('/api/prof-saude', 'POST', {termo: ''})
                .then(function (data) { profissionaisCadastrados = data.profissionais || []; })
                .catch(function () { profissionaisCadastrados = []; }),
            api('/api/empresas', 'POST', {termo: ''})
                .then(function (data) { empresasCadastradas = data.empresas || []; })
                .catch(function () { empresasCadastradas = []; })
        ]);
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'nome', label: 'Login', value: item.nome || '', required: true, maxLength: 40, className: 'usuario-field-nome'},
            {name: 'senha', label: 'Senha', value: item.senha || '', required: true, type: 'password', maxLength: 40},
            {name: 'perfil', label: 'Perfil', value: item.perfil || '', type: 'select', options: perfilOptions(item)},
            {name: 'idcodmed', label: 'Prof. Saúde', value: valueOrEmpty(item.idcodmed || item.idprefere || item.codmed), type: 'select', options: profissionalOptions(item)},
            {name: 'idempresa', label: 'Empresa', value: valueOrEmpty(item.idempresa || item.codclin), type: 'select', options: empresaOptions(item)}
        ];
    }

    function payload(values, item) {
        return {
            nome: values.nome,
            senha: values.senha,
            direitos: item ? (item.direitos || '') : '',
            idcodmed: values.idcodmed,
            codclin: values.idempresa,
            idempresa: values.idempresa,
            perfil: values.perfil
        };
    }

    function detail(label, value, icon) {
        return '<span><i class="fa ' + icon + '"></i> <strong>' + label + ':</strong> ' +
            CrudUI.escapeHtml(value || '') + '</span>';
    }

    function renderItem(item) {
        var masterProtegido = String(item.perfil || '').trim().toUpperCase() === 'MASTER' && !usuarioMaster;
        var actions = masterProtegido ?
            '<span class="crud-badge" title="Somente usuários Master podem alterar este usuário">Protegido</span>' :
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.id +
            '" title="Alterar usuario"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.id +
            '" title="Excluir usuario"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button>';
        return '<article class="crud-card usuario-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome) + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '</div></div><div class="crud-card-details">' +
            detail('Perfil', item.perfil, 'fa-id-badge') +
            detail('Prof. Saúde', item.codmed_nome || item.idcodmed || item.idprefere || item.codmed, 'fa-user-doctor') +
            detail('Empresa', item.empresa_nome || item.codclin_nome || item.idempresa || item.codclin, 'fa-building') +
            '</div><div class="crud-actions">' +
            actions + '</div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.id; },
            createTitle: 'Incluir Usuario',
            editTitle: 'Alterar Usuario',
            formClass: 'usuario-form',
            emptyMessage: 'Nenhum usuario encontrado.',
            beforeOpen: carregarCadastros,
            fields: fields,
            renderItem: renderItem,
            list: async function () {
                var data = await api('/api/usuarios', 'POST', {termo: searchTerm()});
                usuarioMaster = !!data.usuario_master;
                return data.usuarios || [];
            },
            create: function (values) { return api('/api/usuarios/itens', 'POST', payload(values)); },
            update: function (item, values) {
                return api('/api/usuarios/itens/' + encodeURIComponent(item.id), 'PUT', payload(values, item));
            },
            delete: function (item) { return api('/api/usuarios/itens/' + encodeURIComponent(item.id), 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o usuario ' + item.nome + '?';
            }
        });
    }

    function init() {
        var page = document.getElementById('usuario-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';

        controller = createController().mount({
            root: page,
            list: document.getElementById('usuario-result'),
            includeButton: document.getElementById('usuario-include')
        });

        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        document.getElementById('usuario-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        carregarCadastros();
        controller.reload();
    }

    window.UsuarioCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
