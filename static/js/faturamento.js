(function () {
    var controller;
    var buildDateTime = '10/07/2026 13:27';

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
        return document.getElementById('faturamento-busca').value;
    }

    function refreshDisplayedBuildVersion() {
        var labels = document.querySelectorAll('.sidebar-system-label');
        labels.forEach(function (label) {
            if ((label.textContent || '').trim().toUpperCase() === 'VERSÃO') {
                var value = label.nextElementSibling;
                if (value && value.classList.contains('sidebar-system-value')) {
                    value.textContent = buildDateTime;
                }
            }
        });
    }

    function ensureToolbarFilters() {
        if (document.getElementById('faturamento-mes') && document.getElementById('faturamento-tipo')) return;
        var button = document.getElementById('faturamento-buscar');
        if (!button || !button.parentNode) return;
        var monthField = document.createElement('div');
        monthField.className = 'crud-field';
        monthField.innerHTML = '<label for="faturamento-mes">Mês</label>' +
            '<select class="crud-input" id="faturamento-mes">' +
            '<option value="">Todos</option>' +
            '<option value="1">1</option><option value="2">2</option><option value="3">3</option>' +
            '<option value="4">4</option><option value="5">5</option><option value="6">6</option>' +
            '<option value="7">7</option><option value="8">8</option><option value="9">9</option>' +
            '<option value="10">10</option><option value="11">11</option><option value="12">12</option>' +
            '</select>';
        var typeField = document.createElement('div');
        typeField.className = 'crud-field';
        typeField.innerHTML = '<label for="faturamento-tipo">Tipo</label>' +
            '<select class="crud-input" id="faturamento-tipo">' +
            '<option value="">Todos</option>' +
            '<option value="Receita">Receita</option>' +
            '<option value="Despesa">Despesa</option>' +
            '</select>';
        button.parentNode.insertBefore(monthField, button);
        button.parentNode.insertBefore(typeField, button);
    }

    function ensureImportButton() {
        if (document.getElementById('faturamento-import-agenda')) return;
        var includeButton = document.getElementById('faturamento-include');
        if (!includeButton || !includeButton.parentNode) return;
        var wrapper = includeButton.parentNode;
        if (!wrapper.classList.contains('faturamento-header-actions')) {
            var actions = document.createElement('div');
            actions.className = 'faturamento-header-actions';
            wrapper.insertBefore(actions, includeButton);
            actions.appendChild(includeButton);
            wrapper = actions;
        }
        var button = document.createElement('button');
        button.className = 'crud-button crud-button-secondary';
        button.id = 'faturamento-import-agenda';
        button.type = 'button';
        button.title = 'Incluir financeiros da agenda atendida';
        button.innerHTML = '<i class="fa fa-calendar-check"></i> Incluir da Agenda';
        wrapper.insertBefore(button, includeButton);
    }

    function ensureTotalizationButton() {
        if (document.getElementById('faturamento-totalizacao')) return;
        var importButton = document.getElementById('faturamento-import-agenda');
        var includeButton = document.getElementById('faturamento-include');
        var wrapper = (importButton || includeButton || {}).parentNode;
        if (!wrapper) return;
        var button = document.createElement('button');
        button.className = 'crud-button crud-button-secondary';
        button.id = 'faturamento-totalizacao';
        button.type = 'button';
        button.title = 'Totalizar financeiro';
        button.innerHTML = '<i class="fa fa-calculator"></i> Totalização';
        wrapper.insertBefore(button, importButton || includeButton);
    }

    function selectedMonth() {
        var field = document.getElementById('faturamento-mes');
        return field ? field.value : '';
    }

    function selectedType() {
        var field = document.getElementById('faturamento-tipo');
        return field ? field.value : '';
    }

    async function importFromAgenda(button) {
        var month = selectedMonth();
        if (!month) {
            CrudUI.notify('Selecione o mês para incluir da agenda.', 'error');
            return;
        }
        button.disabled = true;
        try {
            var result = await api('/api/faturamento/importar-agenda', 'POST', {mes: month});
            CrudUI.notify(result.message || 'Financeiros incluidos da agenda.');
            await controller.reload();
        } catch (error) {
            CrudUI.notify(error.message || 'Não foi possível incluir da agenda.', 'error');
        } finally {
            button.disabled = false;
        }
    }

    function filterItems(items) {
        var month = selectedMonth();
        var type = selectedType();
        return (items || []).filter(function (item) {
            if (month) {
                var date = item.dataRealizada || '';
                var itemMonth = date.length >= 7 ? String(Number(date.slice(5, 7))) : '';
                if (itemMonth !== month) return false;
            }
            if (type && item.tipo !== type) return false;
            return true;
        });
    }

    function formatCurrencyValue(value) {
        value = String(value || '').trim();
        if (!value) return '';
        var normalized = value.replace(/\./g, '').replace(',', '.');
        var number = Number(normalized);
        if (!Number.isFinite(number)) return '';
        return number.toFixed(2).replace('.', ',');
    }

    function applyCurrencyMask(input) {
        function formatFromDigits() {
            var digits = input.value.replace(/\D/g, '');
            if (!digits) {
                input.value = '';
                return;
            }
            var number = Number(digits) / 100;
            input.value = number.toFixed(2).replace('.', ',');
        }

        input.value = formatCurrencyValue(input.value);
        input.addEventListener('input', formatFromDigits);
        input.addEventListener('blur', function () {
            input.value = formatCurrencyValue(input.value);
        });
    }

    function setupCurrencyFields(backdrop) {
        ['valorPrevisto', 'valorRealizado'].forEach(function (name) {
            var input = backdrop.querySelector('[name="' + name + '"]');
            if (input) applyCurrencyMask(input);
        });
    }

    function pad2(value) {
        return String(value).padStart(2, '0');
    }

    function formatDateBr(date) {
        return pad2(date.getDate()) + '/' + pad2(date.getMonth() + 1) + '/' + date.getFullYear();
    }

    function currentMonthRange() {
        var today = new Date();
        var start = new Date(today.getFullYear(), today.getMonth(), 1);
        var end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        return {
            start: formatDateBr(start),
            end: formatDateBr(end)
        };
    }

    function currencyLabel(value) {
        return 'R$ ' + (value || '0,00');
    }

    function parseCurrency(value) {
        value = String(value || '0').trim();
        if (!value) return 0;
        value = value.replace(/\./g, '').replace(',', '.');
        var number = Number(value);
        return Number.isFinite(number) ? number : 0;
    }

    function formatCurrencyNumber(value) {
        var signal = value < 0 ? '-' : '';
        value = Math.abs(value);
        return signal + value.toFixed(2).replace('.', ',');
    }

    function renderTotalizationResult(totalizacao) {
        totalizacao = totalizacao || {};
        var despesa = totalizacao.Despesa || {};
        var receita = totalizacao.Receita || {};
        var saldoPrevisto = parseCurrency(receita.valorPrevisto) - parseCurrency(despesa.valorPrevisto);
        var saldoRealizado = parseCurrency(receita.valorRealizado) - parseCurrency(despesa.valorRealizado);
        return '<div class="faturamento-totalizacao-result">' +
            '<div class="faturamento-totalizacao-card">' +
            '<h4>Despesa</h4>' +
            '<p><strong>Total Valor Previsto:</strong> ' + currencyLabel(despesa.valorPrevisto) + '</p>' +
            '<p><strong>Total Valor Realizado:</strong> ' + currencyLabel(despesa.valorRealizado) + '</p>' +
            '</div>' +
            '<div class="faturamento-totalizacao-card">' +
            '<h4>Receita</h4>' +
            '<p><strong>Total Valor Previsto:</strong> ' + currencyLabel(receita.valorPrevisto) + '</p>' +
            '<p><strong>Total Valor Realizado:</strong> ' + currencyLabel(receita.valorRealizado) + '</p>' +
            '</div>' +
            '<div class="faturamento-totalizacao-card faturamento-totalizacao-saldo">' +
            '<h4>Saldo</h4>' +
            '<p><strong>Total Valor Previsto:</strong> ' + currencyLabel(formatCurrencyNumber(saldoPrevisto)) + '</p>' +
            '<p><strong>Total Valor Realizado:</strong> ' + currencyLabel(formatCurrencyNumber(saldoRealizado)) + '</p>' +
            '</div>' +
            '</div>';
    }

    function openTotalizationModal() {
        var range = currentMonthRange();
        var backdrop = document.createElement('div');
        backdrop.className = 'crud-modal-backdrop';
        backdrop.innerHTML =
            '<div class="crud-modal faturamento-totalizacao-modal" role="dialog" aria-modal="true">' +
            '<h3>Totalização</h3>' +
            '<div class="faturamento-totalizacao-form">' +
            '<div class="crud-field"><label for="totalizacao-data-inicio">Data início</label>' +
            '<input class="crud-input" id="totalizacao-data-inicio" type="text" inputmode="numeric" placeholder="dd/mm/aaaa" value="' + range.start + '"></div>' +
            '<div class="crud-field"><label for="totalizacao-data-fim">Data fim</label>' +
            '<input class="crud-input" id="totalizacao-data-fim" type="text" inputmode="numeric" placeholder="dd/mm/aaaa" value="' + range.end + '"></div>' +
            '<div class="crud-field"><label for="totalizacao-tipo">Tipo</label>' +
            '<select class="crud-input" id="totalizacao-tipo">' +
            '<option value="">Tudo</option>' +
            '<option value="Receita">Receita</option>' +
            '<option value="Despesa">Despesa</option>' +
            '</select></div>' +
            '</div>' +
            '<div class="faturamento-totalizacao-output" id="faturamento-totalizacao-output"></div>' +
            '<div class="crud-modal-actions">' +
            '<button class="crud-button crud-button-secondary" type="button" data-totalizacao-cancel>Fechar</button>' +
            '<button class="crud-button" type="button" data-totalizacao-confirm><i class="fa fa-check"></i> Confirmar</button>' +
            '</div>' +
            '</div>';
        document.body.appendChild(backdrop);

        var close = function () { backdrop.remove(); };
        var output = backdrop.querySelector('#faturamento-totalizacao-output');
        backdrop.querySelector('[data-totalizacao-cancel]').onclick = close;
        backdrop.addEventListener('click', function (event) {
            if (event.target === backdrop) close();
        });
        backdrop.querySelector('[data-totalizacao-confirm]').onclick = async function () {
            var button = this;
            button.disabled = true;
            output.innerHTML = '<div class="faturamento-totalizacao-loading">Calculando...</div>';
            try {
                var result = await api('/api/faturamento/totalizacao', 'POST', {
                    dataInicio: backdrop.querySelector('#totalizacao-data-inicio').value,
                    dataFim: backdrop.querySelector('#totalizacao-data-fim').value,
                    tipo: backdrop.querySelector('#totalizacao-tipo').value
                });
                output.innerHTML = renderTotalizationResult(result.totalizacao);
            } catch (error) {
                output.innerHTML = '<div class="faturamento-totalizacao-error">' +
                    CrudUI.escapeHtml(error.message || 'Não foi possível totalizar.') + '</div>';
            } finally {
                button.disabled = false;
            }
        };
        backdrop.querySelector('#totalizacao-data-inicio').focus();
    }

    function fields(item) {
        item = item || {};
        return [
            {
                name: 'descricao',
                label: 'Descrição',
                value: item.descricao || '',
                maxLength: 18,
                className: 'faturamento-field-descricao'
            },
            {
                name: 'tipo',
                label: 'Tipo',
                type: 'select',
                value: item.tipo || '',
                required: true,
                className: 'faturamento-field-tipo',
                options: [
                    {value: '', label: ''},
                    {value: 'Receita', label: 'Receita'},
                    {value: 'Despesa', label: 'Despesa'}
                ]
            },
            {
                name: 'dataPrevista',
                label: 'Data prevista',
                type: 'date',
                value: item.dataPrevista || '',
                className: 'faturamento-field-data-prevista'
            },
            {
                name: 'dataRealizada',
                label: 'Data realizada',
                type: 'date',
                value: item.dataRealizada || '',
                className: 'faturamento-field-data-realizada'
            },
            {
                name: 'valorPrevisto',
                label: 'Valor previsto',
                value: item.valorPrevisto || '',
                inputMode: 'decimal',
                placeholder: '0,00',
                className: 'faturamento-field-valor-previsto'
            },
            {
                name: 'valorRealizado',
                label: 'Valor realizado',
                value: item.valorRealizado || '',
                inputMode: 'decimal',
                placeholder: '0,00',
                className: 'faturamento-field-valor-realizado'
            }
        ];
    }

    function detail(label, value, icon) {
        return '<span><i class="fa ' + icon + '"></i> <strong>' + label + ':</strong> ' +
            CrudUI.escapeHtml(value || '') + '</span>';
    }

    function paidLabel(value) {
        if (value === 'S') return 'Sim';
        if (value === 'N') return 'Não';
        return '';
    }

    function addOneMonth(dateValue) {
        if (!dateValue) return '';
        var parts = String(dateValue).split('-').map(Number);
        if (parts.length !== 3 || parts.some(function (part) { return !Number.isFinite(part); })) return dateValue;
        var year = parts[0];
        var month = parts[1];
        var day = parts[2];
        var nextMonth = month === 12 ? 1 : month + 1;
        var nextYear = month === 12 ? year + 1 : year;
        var lastDay = new Date(nextYear, nextMonth, 0).getDate();
        return nextYear + '-' + String(nextMonth).padStart(2, '0') + '-' +
            String(Math.min(day, lastDay)).padStart(2, '0');
    }

    function duplicatePayload(item) {
        return {
            cliente: item.cliente || '',
            descricao: item.descricao || '',
            tipo: item.tipo || '',
            dataPrevista: addOneMonth(item.dataPrevista),
            dataRealizada: addOneMonth(item.dataRealizada),
            valorPrevisto: item.valorPrevisto || '',
            valorRealizado: item.valorRealizado || '',
            valor: item.valor || '',
            pago: item.pago || ''
        };
    }

    function renderItem(item) {
        return '<article class="crud-card faturamento-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.descricao || 'Pagamento') + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '</div></div><div class="crud-card-details">' +
            detail('Tipo', item.tipo, 'fa-tags') +
            detail('Data prevista', item.dataPrevista, 'fa-calendar-day') +
            detail('Data realizada', item.dataRealizada, 'fa-calendar-check') +
            detail('Valor previsto', item.valorPrevisto, 'fa-money-bill') +
            detail('Valor realizado', item.valorRealizado, 'fa-money-check') +
            detail('Concluído', paidLabel(item.pago), 'fa-circle-check') +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.id +
            '" title="Alterar financeiro"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.id +
            '" title="Excluir financeiro"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-action="duplicate-next-month" data-crud-id="' +
            item.id + '" title="Duplicar para o próximo mês"><i class="fa fa-copy"></i>' +
            '<span class="crud-button-label"> Duplicar Prox. mês</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.id; },
            createTitle: 'Incluir financeiro',
            editTitle: 'Alterar financeiro',
            formClass: 'faturamento-form',
            emptyMessage: 'Nenhum financeiro encontrado.',
            fields: fields,
            onFormReady: setupCurrencyFields,
            renderItem: renderItem,
            list: async function () {
                var data = await api('/api/faturamento', 'POST', {
                    termo: searchTerm(),
                    mes: selectedMonth(),
                    tipo: selectedType()
                });
                return filterItems(data.pagamentos || []);
            },
            create: function (values) { return api('/api/faturamento/itens', 'POST', values); },
            update: function (item, values) {
                return api('/api/faturamento/itens/' + encodeURIComponent(item.id), 'PUT', values);
            },
            delete: function (item) {
                return api('/api/faturamento/itens/' + encodeURIComponent(item.id), 'DELETE');
            },
            confirmDelete: function (item) {
                return 'Excluir o financeiro #' + item.id + '?';
            },
            onAction: async function (action, item) {
                if (action !== 'duplicate-next-month' || !item) return;
                var result = await api('/api/faturamento/itens', 'POST', duplicatePayload(item));
                CrudUI.notify(result.message || 'Financeiro duplicado para o próximo mês.');
                await controller.reload();
            }
        });
    }

    function init() {
        var page = document.getElementById('faturamento-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        refreshDisplayedBuildVersion();
        ensureToolbarFilters();
        ensureImportButton();
        ensureTotalizationButton();

        controller = createController().mount({
            root: page,
            list: document.getElementById('faturamento-result'),
            includeButton: document.getElementById('faturamento-include')
        });

        document.getElementById('faturamento-buscar').onclick = function () { controller.reload(); };
        document.getElementById('faturamento-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        document.getElementById('faturamento-mes').addEventListener('change', function () { controller.reload(); });
        document.getElementById('faturamento-tipo').addEventListener('change', function () { controller.reload(); });
        document.getElementById('faturamento-import-agenda').onclick = function () {
            importFromAgenda(this);
        };
        document.getElementById('faturamento-totalizacao').onclick = openTotalizationModal;
        controller.reload();
    }

    window.FaturamentoCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
