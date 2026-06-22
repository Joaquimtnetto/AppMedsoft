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

    function searchTerm() {
        return document.getElementById('paciente-busca').value;
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'nome', label: 'Nome', value: item.nomecli || '', required: true, wide: true},
        ];
    }

    function renderItem(item) {
        return '<article class="crud-card">' +
            '<div class="crud-card-header"><span class="crud-title">' +
            CrudUI.escapeHtml(item.nomecli) +
            '</span></div><div class="crud-card-details">' +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-action="history" data-crud-id="' +
            item.codcli + '" title="Histórico do paciente"><i class="fa fa-notes-medical"></i>' +
            '<span class="crud-button-label"> Histórico</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.codcli +
            '" title="Alterar paciente"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.codcli +
            '" title="Excluir paciente"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.codcli; },
            createTitle: 'Incluir paciente',
            editTitle: 'Alterar paciente',
            emptyMessage: 'Nenhum paciente encontrado.',
            fields: fields,
            renderItem: renderItem,
            list: async function () {
                var term = searchTerm();
                if (!term) throw new Error('Digite um nome ou código para buscar.');
                var data = await api('/api/consulta-paciente', 'POST', {termo: term});
                return data.pacientes || [];
            },
            create: function (values) {
                return api('/api/pacientes/itens', 'POST', {
                    nome: values.nome
                });
            },
            update: function (item, values) {
                return api('/api/pacientes/itens/' + item.codcli, 'PUT', {
                    nome: values.nome
                });
            },
            delete: function (item) { return api('/api/pacientes/itens/' + item.codcli, 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o paciente ' + item.nomecli + '?';
            },
            onAction: function (action, item) {
                if (action === 'history' && item && window.abrirHistoricoPaciente) {
                    window.abrirHistoricoPaciente(item.codcli, item.nomecli);
                }
            }
        });
    }

    function init() {
        var page = document.getElementById('paciente-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        
        controller = createController().mount({
            root: page,
            list: document.getElementById('paciente-result'),
            includeButton: document.getElementById('paciente-include')
        });
        
        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        
        // Permitir buscar pressionando Enter
        document.getElementById('paciente-busca').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') controller.reload();
        });
    }

    window.PacienteCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

    // Função para abrir histórico do paciente
    window.abrirHistoricoPaciente = function(codcli, nomecli) {
        const db_path = localStorage.getItem('db_path');
        fetch('/api/consultas-paciente', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-DB-PATH': db_path || ''
            },
            body: JSON.stringify({ codpac: codcli })
        })
        .then(resp => resp.json())
        .then(data => {
            let conteudo = `<h3>Histórico de ${nomecli}</h3>`;
            if (data.success && data.consultas && data.consultas.length > 0) {
                conteudo += '<ul style="max-height:300px;overflow:auto;text-align:left;">';
                data.consultas.forEach(c => {
                    conteudo += `<li><b>Data:</b> ${c.dtvisita} <br><b>Diagnóstico:</b> ${c.diag || ''} <br><b>Histórico:</b> ${c.historico || ''}</li><hr>`;
                });
                conteudo += '</ul>';
            } else {
                conteudo += '<p>Nenhuma consulta registrada.</p>';
            }
            alert(conteudo);
        })
        .catch(err => CrudUI.notify('Erro ao buscar histórico: ' + err.message, 'error'));
    };
}());
