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
        return document.getElementById('anamnese-busca').value;
    }

    function fields(item) {
        var isNew = !item;
        item = item || {};
        var result = [
            {name: 'atalho', label: 'Tipo', value: item.atalho || 'A', required: true, type: 'select', options: [
                {value: 'R', label: 'Rec - Receita'},
                {value: 'X', label: 'Ex - Exame'},
                {value: 'P', label: 'Pr - Procedimento'},
                {value: 'E', label: 'Me - Mensagem E-mail'},
                {value: 'Z', label: 'Mz - Mensagem WhatsApp'},
                {value: 'A', label: 'An - Anamnese'}
            ], className: 'anamnese-field-tipo'},
            {name: 'nome', label: 'Nome', value: item.nome || '', required: true, maxLength: 30, className: 'anamnese-field-nome'},
            {name: 'msghtml', label: 'Msg HTML', checkboxLabel: 'Msg HTML', value: !!item.msghtml, type: 'checkbox', className: 'anamnese-field-html-check'},
            {name: 'texto', label: item.atalho === 'E' ? 'HTML do e-mail' : 'Texto', value: item.texto || '', type: 'textarea', rows: item.atalho === 'E' ? 18 : 7, className: 'anamnese-field-texto'}
        ];
        if (isNew) {
            result.push({
                name: 'copiar_padrao',
                label: 'Copiar padrão existente',
                type: 'select',
                value: '',
                wide: true,
                className: 'anamnese-field-copy',
                options: [{value: '', label: 'Selecione um padrão'}].concat(
                    ((controller && controller.items) || []).map(function (source) {
                        return {
                            value: source.id,
                            label: typeLabel(source.atalho) + ' - ' + source.nome
                        };
                    })
                )
            });
        }
        return result;
    }

    function setupEmailHtmlEditor(backdrop) {
        var type = backdrop.querySelector('[name="atalho"]');
        var textarea = backdrop.querySelector('[name="texto"]');
        var field = textarea && textarea.closest('.anamnese-field-texto');
        var htmlCheck = backdrop.querySelector('[name="msghtml"]');
        var htmlCheckField = htmlCheck && htmlCheck.closest('.anamnese-field-html-check');
        var modal = backdrop.querySelector('.crud-modal');
        if (!type || !textarea || !field || !htmlCheck || !htmlCheckField || !modal) return;

        var tools = document.createElement('div');
        tools.className = 'email-html-tools';
        tools.innerHTML =
            '<p>Use HTML para cores, imagens, tabelas e botões. Variáveis disponíveis:</p>' +
            '<div class="email-html-variables">' +
            ['paciente', 'procedimento', 'data', 'hora', 'profissional', 'nomeclinica', 'link_confirmacao'].map(function (name) {
                return '<button type="button" data-email-variable="' + name + '">{' + name + '}</button>';
            }).join('') + '</div>' +
            '<label>Pré-visualização</label>' +
            '<iframe class="email-html-preview" sandbox title="Pré-visualização do e-mail"></iframe>';
        field.appendChild(tools);
        var preview = tools.querySelector('iframe');

        function refreshPreview() {
            preview.srcdoc = textarea.value || '<p style="font-family:Arial;padding:20px">Digite o HTML do e-mail.</p>';
        }

        function toggleMode() {
            var isEmail = type.value === 'E';
            var useHtml = isEmail && htmlCheck.checked;
            htmlCheckField.hidden = !isEmail;
            tools.hidden = !useHtml;
            modal.classList.toggle('email-html-modal', useHtml);
            field.querySelector('label').textContent = useHtml ? 'HTML do e-mail' : 'Texto';
            textarea.rows = useHtml ? 18 : 7;
            if (useHtml) refreshPreview();
        }

        tools.addEventListener('click', function (event) {
            var button = event.target.closest('[data-email-variable]');
            if (!button) return;
            var token = '{' + button.dataset.emailVariable + '}';
            var start = textarea.selectionStart;
            var end = textarea.selectionEnd;
            textarea.value = textarea.value.slice(0, start) + token + textarea.value.slice(end);
            textarea.focus();
            textarea.selectionStart = textarea.selectionEnd = start + token.length;
            refreshPreview();
        });
        type.addEventListener('change', toggleMode);
        htmlCheck.addEventListener('change', toggleMode);
        textarea.addEventListener('input', function () {
            if (type.value === 'E' && htmlCheck.checked) refreshPreview();
        });

        var copySelect = backdrop.querySelector('[name="copiar_padrao"]');
        if (copySelect) {
            var copyField = copySelect.closest('.anamnese-field-copy');
            var copyRow = document.createElement('div');
            copyRow.className = 'anamnese-copy-row';
            copySelect.parentNode.insertBefore(copyRow, copySelect);
            copyRow.appendChild(copySelect);
            var copyButton = document.createElement('button');
            copyButton.type = 'button';
            copyButton.className = 'crud-button crud-button-secondary';
            copyButton.innerHTML = '<i class="fa fa-copy"></i> Copiar';
            copyRow.appendChild(copyButton);
            copyButton.addEventListener('click', function () {
                var source = controller && controller.find(copySelect.value);
                if (!source) {
                    CrudUI.notify('Selecione um padrão para copiar.', 'error');
                    return;
                }
                type.value = source.atalho || 'A';
                htmlCheck.checked = !!source.msghtml;
                textarea.value = source.texto || '';
                type.dispatchEvent(new Event('change'));
                textarea.dispatchEvent(new Event('input'));
                CrudUI.notify('Padrão copiado. Informe um novo nome e salve.');
            });
            copyField.classList.add('crud-field-wide');
        }
        toggleMode();
    }

    function payload(values) {
        return {
            atalho: values.atalho,
            nome: values.nome,
            texto: values.texto,
            msghtml: values.atalho === 'E' && values.msghtml === 'true'
        };
    }

    function typeLabel(value) {
        return {
            R: 'Rec - Receita',
            X: 'Ex - Exame',
            P: 'Pr - Procedimento',
            E: 'Me - Mensagem E-mail',
            Z: 'Mz - Mensagem WhatsApp',
            A: 'An - Anamnese'
        }[value] || 'An - Anamnese';
    }

    function renderItem(item) {
        var resumo = item.atalho === 'E' && item.msghtml ? 'Modelo HTML editável' : (item.texto || '');
        if (resumo.length > 160) resumo = resumo.slice(0, 160) + '...';
        return '<article class="crud-card anamnese-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome) + '</div>' +
            '<div class="plano-code">' + CrudUI.escapeHtml(typeLabel(item.atalho)) + '</div>' +
            '</div></div>' +
            '<div class="crud-card-details">' +
            '<span><i class="fa fa-notes-medical"></i> ' + CrudUI.escapeHtml(resumo) + '</span>' +
            (optionsMode ? '<span><i class="fa fa-building"></i> <strong>Empresa:</strong> ' +
                CrudUI.escapeHtml(item.empresa_id || '') + '</span>' : '') +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' +
            CrudUI.escapeHtml(optionsMode ? item._option_key : item.id) +
            '" title="Alterar padrão"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + CrudUI.escapeHtml(item.id) +
            '" title="Excluir padrão"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return optionsMode ? item._option_key : item.id; },
            createTitle: 'Incluir Padrão',
            editTitle: 'Alterar Padrão',
            formClass: 'anamnese-form',
            emptyMessage: 'Nenhum padrão encontrado.',
            fields: fields,
            onFormReady: setupEmailHtmlEditor,
            renderItem: renderItem,
            list: async function () {
                var endpoint = optionsMode ? '/api/anamnese/opcoes' : '/api/anamnese';
                var data = await api(endpoint, 'POST', {termo: searchTerm()});
                return data.anamneses || [];
            },
            create: function (values) { return api('/api/anamnese/itens', 'POST', payload(values)); },
            update: function (item, values) {
                if (optionsMode) return api('/api/anamnese/itens', 'POST', payload(values));
                return api('/api/anamnese/itens/' + encodeURIComponent(item.id), 'PUT', payload(values));
            },
            delete: function (item) { return api('/api/anamnese/itens/' + encodeURIComponent(item.id), 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o padrão ' + item.nome + '?';
            }
        });
    }

    function init() {
        var page = document.getElementById('anamnese-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        optionsMode = false;
        page.classList.remove('options-mode');
        document.getElementById('anamnese-options').innerHTML = '<i class="fa fa-list"></i> Opções';
        document.getElementById('anamnese-include').hidden = false;

        controller = createController().mount({
            root: page,
            list: document.getElementById('anamnese-result'),
            includeButton: document.getElementById('anamnese-include')
        });

        document.getElementById('btn-anamnese-ok').onclick = function () { controller.reload(); };
        var optionsButton = document.getElementById('anamnese-options');
        var includeButton = document.getElementById('anamnese-include');
        optionsButton.onclick = function () {
            optionsMode = !optionsMode;
            page.classList.toggle('options-mode', optionsMode);
            optionsButton.innerHTML = optionsMode
                ? '<i class="fa fa-arrow-left"></i> Meus padrões'
                : '<i class="fa fa-list"></i> Opções';
            includeButton.hidden = optionsMode;
            controller.reload();
        };
        document.getElementById('anamnese-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        controller.reload();
    }

    window.AnamneseCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
