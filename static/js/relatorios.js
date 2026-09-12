(function () {
    var pacientes = [];
    var pacientesOriginais = [];
    var colunas = [];
    var agendaItems = [];
    var agendaColumns = [];
    var genericItems = [];
    var genericColumns = [];
    var genericTitle = '';
    var genericTotalization = false;

    function escapeHtml(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function columnLabel(name) {
        var normalized = String(name || '').trim().toLowerCase().replace(/_+$/g, '').replace(/\s+/g, '');
        var friendlyNames = {
            descamb: 'Descrição',
            valorch: 'Valor',
            valor_ch: 'Valor',
            descricao: 'Descrição',
            data_prevista: 'Data Prevista',
            data_realizada: 'Data Realizada',
            valor_previsto: 'Valor Previsto',
            valor_realizado: 'Valor Realizado',
            pago: 'Pago',
            cliente: 'Cliente',
            codigo: 'Código',
            nomecli: 'Nome',
            natcli: 'Naturalidade',
            corcli: 'Cor',
            est_civ: 'Est. Civil',
            estciv: 'Est. Civil',
            profcli: 'Profissão',
            datanasc: 'Data Nasc.',
            endcli: 'Endereço',
            baicli: 'Bairro',
            cidadecli: 'Cidade',
            cepcli: 'CEP',
            ufcli: 'UF',
            telres: 'Tel. Res.',
            telcom: 'Tel. Comerc.',
            ramalcli: 'Ramal',
            nomeplano1: 'Plano 1',
            cont1: 'Nr. Cart. 1',
            nomeplano2: 'Plano 2',
            cont2: 'Nr. Carteira 2',
            recom: 'Recomendação',
            datult: 'Data Última Consulta',
            nompai: 'Nome Pai',
            nommae: 'Nome da Mãe',
            historico_clinico: 'Histórico Clínico'
        };
        if (friendlyNames[normalized]) return friendlyNames[normalized];
        return String(name || '').replace(/_/g, ' ').replace(/\b\w/g, function (letter) {
            return letter.toUpperCase();
        });
    }

    async function api(body) {
        var response = await fetch('/api/relatorios/pacientes', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
        });
        var data = await response.json();
        if (!response.ok || data.success === false) throw new Error(data.message || 'Erro ao buscar pacientes.');
        return data;
    }

    async function loadProfessionalOptions(select) {
        var response = await fetch('/api/prof-saude', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({termo: ''})
        });
        var data = await response.json();
        if (!response.ok || data.success === false) {
            throw new Error(data.message || 'Erro ao carregar profissionais de saúde.');
        }
        select.innerHTML = '<option value="">Selecione</option>' + (data.profissionais || []).map(function (item) {
            return '<option value="' + escapeHtml(item.nome || item.id) + '">' + escapeHtml(item.nome || item.id) + '</option>';
        }).join('');
    }

    async function agendaApi(body) {
        var response = await fetch('/api/relatorios/agenda', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
        });
        var data = await response.json();
        if (!response.ok || data.success === false) throw new Error(data.message || 'Erro ao buscar a agenda.');
        return data;
    }

    async function loadAgendaPlanOptions(select) {
        var response = await fetch('/api/planos', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({termo: ''})
        });
        var data = await response.json();
        if (!response.ok || data.success === false) throw new Error(data.message || 'Erro ao carregar os planos.');
        select.innerHTML = '<option value="">Todos</option>' + (data.planos || []).map(function (item) {
            var name = item.nome || item.id || '';
            return name ? '<option value="' + escapeHtml(name) + '">' + escapeHtml(name) + '</option>' : '';
        }).join('');
    }

    async function genericReportApi(reportType) {
        var response = await fetch('/api/relatorios/cadastros/' + encodeURIComponent(reportType), {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
        });
        var data = await response.json();
        if (!response.ok || data.success === false) throw new Error(data.message || 'Erro ao gerar o relatório.');
        return data;
    }

    async function financialReportApi(body) {
        var response = await fetch('/api/relatorios/financeiro', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
        });
        var data = await response.json();
        if (!response.ok || data.success === false) throw new Error(data.message || 'Erro ao gerar o relatório financeiro.');
        return data;
    }

    function selectedGenericItems() {
        return Array.from(document.querySelectorAll('.relatorio-generico-item-check:checked')).map(function (checkbox) {
            return genericItems[Number(checkbox.dataset.index)];
        }).filter(Boolean);
    }

    function selectedGenericColumns() {
        return Array.from(document.querySelectorAll('.relatorio-generico-coluna-check:checked')).map(function (checkbox) {
            return checkbox.dataset.column;
        });
    }

    function updateGenericSelection() {
        var checks = Array.from(document.querySelectorAll('.relatorio-generico-item-check'));
        var selected = checks.filter(function (checkbox) { return checkbox.checked; }).length;
        var label = document.getElementById('relatorio-generico-selecionados');
        if (label) label.textContent = 'Selecionados: ' + selected;
        var selectAll = document.getElementById('relatorio-generico-selecionar-todos');
        if (selectAll) {
            selectAll.checked = checks.length > 0 && selected === checks.length;
            selectAll.indeterminate = selected > 0 && selected < checks.length;
        }
    }

    function genericDataTableHtml(items, fields, includeTotals) {
        var table = '<table><thead><tr>' + fields.map(function (field) {
            return '<th>' + escapeHtml(columnLabel(field)) + '</th>';
        }).join('') + '</tr></thead><tbody>' + items.map(function (item) {
            return '<tr>' + fields.map(function (field) {
                return '<td>' + escapeHtml(item[field]) + '</td>';
            }).join('') + '</tr>';
        }).join('') + '</tbody></table>';
        return table + (includeTotals === false || !financialTotalsSelected() ? '' : genericTotalsHtml(items, fields));
    }

    function financialNumber(value) {
        var text = String(value === null || value === undefined ? '' : value).trim();
        if (!text) return 0;
        if (text.indexOf(',') >= 0) text = text.replace(/\./g, '').replace(',', '.');
        var number = Number(text);
        return Number.isFinite(number) ? number : 0;
    }

    function financialCurrency(value) {
        return Number(value || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }

    function financialPeriodHtml() {
        if (genericTitle !== 'Financeiro') return '';
        var startInput = document.getElementById('relatorio-financeiro-inicio');
        var endInput = document.getElementById('relatorio-financeiro-fim');
        function formatDate(value) {
            var parts = String(value || '').split('-');
            return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : value;
        }
        return '<div class="report-period"><strong>Data Inicial:</strong> ' +
            escapeHtml(formatDate(startInput ? startInput.value : '')) +
            ' &nbsp;&nbsp; <strong>Data Final:</strong> ' +
            escapeHtml(formatDate(endInput ? endInput.value : '')) + '</div>';
    }

    function financialTotalsSelected() {
        var checkbox = document.getElementById('relatorio-financeiro-totalizacao-check');
        return Boolean(checkbox && checkbox.checked);
    }

    function financialTotalsData(items) {
        var totals = items.reduce(function (result, item) {
            var type = String(item.tipo || '').trim().toLowerCase();
            if (type === 'receita') {
                result.receitaPrevista += financialNumber(item.valor_previsto);
                result.receitaRealizada += financialNumber(item.valor_realizado);
            } else if (type === 'despesa') {
                result.despesaPrevista += financialNumber(item.valor_previsto);
                result.despesaRealizada += financialNumber(item.valor_realizado);
            }
            return result;
        }, {receitaPrevista: 0, receitaRealizada: 0, despesaPrevista: 0, despesaRealizada: 0});
        return [
            ['Total Receita - Previsto', totals.receitaPrevista],
            ['Total Receita - Realizado', totals.receitaRealizada],
            ['Total Despesa - Previsto', totals.despesaPrevista],
            ['Total Despesa - Realizado', totals.despesaRealizada],
            ['Saldo Realizado (Receita - Despesa)', totals.receitaRealizada - totals.despesaRealizada],
            ['Saldo Previsto (Receita - Despesa)', totals.receitaPrevista - totals.despesaPrevista]
        ];
    }

    function financialPieChartHtml(title, receita, despesa) {
        var total = receita + despesa;
        var receitaPercent = total ? (receita / total) * 100 : 0;
        var gradient = total ?
            '#26a69a 0% ' + receitaPercent.toFixed(2) + '%, #ef5350 ' +
            receitaPercent.toFixed(2) + '% 100%' : '#d8e1ee 0% 100%';
        return '<section class="relatorio-agenda-grafico-card"><h4>' + escapeHtml(title) + '</h4>' +
            '<div class="relatorio-agenda-grafico-conteudo"><div class="relatorio-agenda-pizza" ' +
            'style="background:conic-gradient(' + gradient + ')" role="img" aria-label="' +
            escapeHtml(title) + '"></div><ul>' +
            '<li><span class="relatorio-agenda-grafico-cor" style="background:#26a69a"></span>' +
            '<strong>Receita</strong><span>R$ ' + escapeHtml(financialCurrency(receita)) + '</span></li>' +
            '<li><span class="relatorio-agenda-grafico-cor" style="background:#ef5350"></span>' +
            '<strong>Despesa</strong><span>R$ ' + escapeHtml(financialCurrency(despesa)) + '</span></li>' +
            '</ul></div></section>';
    }

    function showFinancialCharts() {
        var result = document.getElementById('relatorio-financeiro-grafico-result');
        if (!result) return;
        if (!genericTotalization) {
            genericTotalization = true;
            document.getElementById('relatorio-financeiro-totalizacao-result').innerHTML =
                genericTotalsHtml(genericItems, genericColumns, true);
        }
        var values = financialTotalsData(genericItems);
        result.innerHTML = '<div class="relatorio-agenda-graficos"><h3>Gráficos Financeiros</h3>' +
            '<div class="relatorio-agenda-graficos-grid">' +
            financialPieChartHtml('Previsto', values[0][1], values[2][1]) +
            financialPieChartHtml('Realizado', values[1][1], values[3][1]) + '</div></div>';
        result.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }

    function financialTotalsExcelHtml(items) {
        var rows = financialTotalsData(items).map(function (item) {
            return '<tr><td><strong>' + escapeHtml(item[0]) + ':</strong> R$ ' +
                escapeHtml(financialCurrency(item[1])) + '</td></tr>';
        }).join('');
        return '<table class="excel-totalizacao"><thead><tr><th>Totalização Financeira</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table>';
    }

    function financialPeriodExcelHtml() {
        return '<table class="excel-periodo"><tbody><tr><td>' + financialPeriodHtml() + '</td></tr></tbody></table>';
    }

    function genericTotalsHtml(items, fields, showSelector) {
        if (!genericTotalization || genericTitle !== 'Financeiro') return '';
        var values = financialTotalsData(items);
        var title = showSelector ?
            '<label class="crud-checkbox-option relatorio-financeiro-totalizacao-title">' +
            '<input type="checkbox" id="relatorio-financeiro-totalizacao-check"> ' +
            '<strong>Totalização Financeira</strong></label>' : '<strong>Totalização Financeira</strong>';
        return '<div class="relatorio-financeiro-totais">' + title +
            '<div class="relatorio-agenda-total-chips">' + values.map(function (item) {
                return '<span><strong>' + escapeHtml(item[0]) + ':</strong> R$ ' +
                    escapeHtml(financialCurrency(item[1])) + '</span>';
            }).join('') + '</div></div>';
    }

    function genericSelection() {
        var items = selectedGenericItems();
        var fields = selectedGenericColumns();
        var totalsOnly = genericTitle === 'Financeiro' && financialTotalsSelected();
        if (!items.length && !totalsOnly) { alert('Selecione pelo menos um registro.'); return null; }
        if (items.length && !fields.length) { alert('Selecione pelo menos uma coluna.'); return null; }
        return {items: items, fields: fields};
    }

    function exportGenericExcel() {
        var selection = genericSelection();
        if (!selection) return;
        var isFinancial = genericTitle === 'Financeiro';
        var content = '<html><head><meta charset="utf-8"><style>' +
            'table{border-collapse:collapse;margin-bottom:12px}th,td{border:1px solid #b8c8dc;padding:6px;text-align:left}' +
            '.excel-periodo td{font-weight:bold;background:#eef5ff}.excel-totalizacao{min-width:420px}' +
            '.excel-totalizacao th{background:#dceaff}.excel-totalizacao td{background:#f7faff}' +
            '</style></head><body>' + (isFinancial ? financialPeriodExcelHtml() : '') +
            (selection.items.length ? genericDataTableHtml(selection.items, selection.fields, false) : '') +
            (isFinancial && financialTotalsSelected() ?
                financialTotalsExcelHtml(selection.items.length ? selection.items : genericItems) : '') +
            '</body></html>';
        var link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([content], {type: 'application/vnd.ms-excel'}));
        link.download = 'relatorio-' + genericTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-') + '.xls';
        link.click(); setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
    }

    function printGenericReport() {
        var selection = genericSelection();
        if (!selection) return;
        var page = document.getElementById('relatorios-page');
        var company = page ? page.dataset.empresa || '' : '';
        var groups = [];
        if (selection.items.length) {
            for (var index = 0; index < selection.fields.length; index += 7) groups.push(selection.fields.slice(index, index + 7));
        }
        var tables = groups.map(function (fields, index) {
            return '<section class="group">' + (index ? '<h2>Continuação dos campos</h2>' : '') +
                genericDataTableHtml(selection.items, fields, false) + '</section>';
        }).join('') + (financialTotalsSelected() ?
            genericTotalsHtml(selection.items.length ? selection.items : genericItems, selection.fields) : '');
        var popup = window.open('', '_blank', 'width=1100,height=750');
        if (!popup) return;
        popup.document.write('<!doctype html><html><head><meta charset="utf-8"><title>Relatório - ' +
            escapeHtml(genericTitle) + '</title><style>@page{size:landscape;margin:12mm}body{font-family:Arial;margin:0}' +
            'h1{font-size:20px;margin:0 0 4px}.company{font-weight:bold;margin-bottom:6px}' +
            '.report-period{margin-bottom:14px}.group{margin-bottom:18px;' +
            'page-break-inside:avoid}.group h2{font-size:13px}table{width:100%;table-layout:fixed;border-collapse:collapse}' +
            'th,td{border:1px solid #bbb;padding:5px;font-size:9px;text-align:left;overflow-wrap:anywhere}' +
            'th{background:#eee}.relatorio-financeiro-totais{margin-top:12px;padding:12px 16px;border:1px solid #cbdcf5;' +
            'border-radius:8px;background:#eef5ff;color:#173f75;text-align:left}' +
            '.relatorio-financeiro-totais>.relatorio-agenda-total-chips{display:flex;flex-direction:column;' +
            'align-items:flex-start;gap:7px;margin-top:10px}.relatorio-financeiro-totais span{display:block;padding:6px 9px;' +
            'border:1px solid #d5e3f7;border-radius:7px;background:#fff}</style></head><body><h1>Relatório - ' +
            escapeHtml(genericTitle) + '</h1><div class="company">Empresa: ' + escapeHtml(company) + '</div>' +
            financialPeriodHtml() + tables + '</body></html>');
        popup.document.close(); popup.focus(); popup.print();
    }

    function renderGenericReport(data) {
        genericItems = data.registros || [];
        genericColumns = data.colunas || [];
        genericTitle = data.titulo || 'Relatório';
        var result = document.getElementById(
            genericTitle === 'Financeiro' ? 'relatorio-financeiro-result' : 'relatorios-result'
        );
        if (!genericItems.length) {
            result.innerHTML = '<div class="crud-empty">Nenhum registro encontrado.</div>';
            return;
        }
        var header = genericColumns.map(function (field) {
            return '<th><label class="relatorio-column-label"><input type="checkbox" ' +
                'class="relatorio-generico-coluna-check" data-column="' + escapeHtml(field) + '" checked> ' +
                '<span>' + escapeHtml(columnLabel(field)) + '</span></label></th>';
        }).join('');
        var rows = genericItems.map(function (item, index) {
            return '<tr><td class="relatorio-select-cell"><input type="checkbox" ' +
                'class="relatorio-generico-item-check" data-index="' + index + '"></td>' +
                genericColumns.map(function (field) { return '<td>' + escapeHtml(item[field]) + '</td>'; }).join('') + '</tr>';
        }).join('');
        var totalizationButton = genericTitle === 'Financeiro' ?
            '<button class="crud-button crud-button-secondary" id="relatorio-financeiro-totalizar" type="button">' +
            '<i class="fa fa-calculator"></i> Totalização</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-financeiro-grafico" type="button">' +
            '<i class="fa fa-chart-pie"></i> Gráfico</button>' : '';
        result.innerHTML = '<div class="crud-toolbar relatorios-actions"><strong>' + escapeHtml(genericTitle) +
            ' — Total: ' + genericItems.length + '</strong><span id="relatorio-generico-selecionados">Selecionados: 0</span>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-generico-excel" type="button">' +
            '<i class="fa fa-file-excel"></i> Excel</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-generico-imprimir" type="button">' +
            '<i class="fa fa-print"></i> Imprimir</button>' + totalizationButton + '</div><div class="crud-table-wrap">' +
            '<table class="crud-table"><thead><tr><th class="relatorio-select-cell"><input type="checkbox" ' +
            'id="relatorio-generico-selecionar-todos"></th>' + header + '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
            '<div id="relatorio-financeiro-totalizacao-result">' +
            genericTotalsHtml(genericItems, genericColumns, true) + '</div>' +
            '<div id="relatorio-financeiro-grafico-result"></div>';
        var selectAll = document.getElementById('relatorio-generico-selecionar-todos');
        selectAll.onchange = function () {
            document.querySelectorAll('.relatorio-generico-item-check').forEach(function (checkbox) {
                checkbox.checked = selectAll.checked;
            });
            updateGenericSelection();
        };
        document.querySelectorAll('.relatorio-generico-item-check').forEach(function (checkbox) {
            checkbox.onchange = updateGenericSelection;
        });
        document.getElementById('relatorio-generico-excel').onclick = exportGenericExcel;
        document.getElementById('relatorio-generico-imprimir').onclick = printGenericReport;
        var totalization = document.getElementById('relatorio-financeiro-totalizar');
        if (totalization) totalization.onclick = function () {
            genericTotalization = true;
            document.getElementById('relatorio-financeiro-totalizacao-result').innerHTML =
                genericTotalsHtml(genericItems, genericColumns, true);
        };
        var chart = document.getElementById('relatorio-financeiro-grafico');
        if (chart) chart.onclick = showFinancialCharts;
    }

    async function loadGenericReport(reportType) {
        var result = document.getElementById('relatorios-result');
        result.innerHTML = '<div class="crud-empty">Carregando relatório...</div>';
        try {
            renderGenericReport(await genericReportApi(reportType));
        } catch (error) {
            result.innerHTML = '<div class="crud-error">' + escapeHtml(error.message) + '</div>';
        }
    }

    function renderAgenda(items, fields) {
        var result = document.getElementById('relatorio-agenda-result');
        agendaItems = items;
        agendaColumns = fields;
        if (!items.length) {
            result.innerHTML = '<div class="crud-empty">Nenhum agendamento encontrado para os filtros informados.</div>';
            return;
        }
        var labels = {
            codigo: 'Código', data: 'Data', hora: 'Hora', paciente: 'Paciente',
            prof_saude: 'Prof. Saúde', telefone: 'Telefone', plano: 'Plano',
            procedimento: 'Procedimento', status: 'Status', observacao: 'Observação', email: 'E-mail'
        };
        var header = fields.map(function (field) {
            return '<th><label class="relatorio-column-label"><input type="checkbox" ' +
                'class="relatorio-agenda-coluna-check" data-column="' + escapeHtml(field) + '" checked> ' +
                '<span>' + escapeHtml(labels[field] || columnLabel(field)) + '</span></label></th>';
        }).join('');
        var rows = items.map(function (item, index) {
            return '<tr><td class="relatorio-select-cell"><input type="checkbox" ' +
                'class="relatorio-agenda-item-check" data-index="' + index + '" aria-label="Selecionar agendamento"></td>' +
                fields.map(function (field) {
                return '<td>' + escapeHtml(item[field]) + '</td>';
            }).join('') + '</tr>';
        }).join('');
        result.innerHTML = '<div class="crud-toolbar"><strong>Total: ' + items.length + '</strong>' +
            '<span id="relatorio-agenda-selecionados">Selecionados: 0</span>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-agenda-excel" type="button">' +
            '<i class="fa fa-file-excel"></i> Excel</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-agenda-imprimir" type="button">' +
            '<i class="fa fa-print"></i> Imprimir</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-agenda-totalizacao" type="button">' +
            '<i class="fa fa-calculator"></i> Totalização</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorio-agenda-grafico" type="button">' +
            '<i class="fa fa-chart-pie"></i> Gráfico</button></div>' +
            '<div class="crud-table-wrap"><table class="crud-table"><thead><tr>' +
            '<th class="relatorio-select-cell"><input type="checkbox" id="relatorio-agenda-selecionar-todos" ' +
            'aria-label="Selecionar todos os agendamentos"></th>' + header +
            '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
            '<div id="relatorio-agenda-totalizacao-result"></div>' +
            '<div id="relatorio-agenda-grafico-result"></div>';
        var selectAll = document.getElementById('relatorio-agenda-selecionar-todos');
        selectAll.onchange = function () {
            document.querySelectorAll('.relatorio-agenda-item-check').forEach(function (checkbox) {
                checkbox.checked = selectAll.checked;
            });
            updateAgendaSelection();
        };
        document.querySelectorAll('.relatorio-agenda-item-check').forEach(function (checkbox) {
            checkbox.onchange = updateAgendaSelection;
        });
        document.getElementById('relatorio-agenda-excel').onclick = exportAgendaExcel;
        document.getElementById('relatorio-agenda-imprimir').onclick = printAgenda;
        document.getElementById('relatorio-agenda-totalizacao').onclick = showAgendaTotals;
        document.getElementById('relatorio-agenda-grafico').onclick = showAgendaCharts;
    }

    function agendaGroupTotals(field, emptyLabel) {
        var groups = {};
        agendaItems.forEach(function (item) {
            var raw = String(item[field] || '').trim();
            var key = raw.toLocaleUpperCase('pt-BR') || '__EMPTY__';
            if (!groups[key]) groups[key] = {label: raw || emptyLabel, total: 0};
            groups[key].total += 1;
        });
        return Object.keys(groups).sort(function (left, right) {
            return groups[left].label.localeCompare(groups[right].label, 'pt-BR');
        }).map(function (key) { return groups[key]; });
    }

    function agendaTotalsSection(title, prefix, groups) {
        return '<section><h4>' + escapeHtml(title) + '</h4><div class="relatorio-agenda-total-chips">' +
            groups.map(function (group) {
                return '<span><strong>' + escapeHtml(prefix + group.label) + ':</strong> ' + group.total + '</span>';
            }).join('') + '</div></section>';
    }

    function agendaTotalsData() {
        var statusLabels = {AG: 'AG', AT: 'AT', CO: 'CO', SC: 'SC'};
        var statuses = agendaGroupTotals('status', 'Sem status').map(function (group) {
            group.label = statusLabels[group.label.toLocaleUpperCase('pt-BR')] || group.label;
            return group;
        });
        return {statuses: statuses, plans: agendaGroupTotals('plano', 'Sem plano')};
    }

    function agendaPieChartHtml(title, groups) {
        var colors = ['#3478f6', '#ef5350', '#26a69a', '#ffb300', '#8e5ad7', '#ec6ea4', '#5c6bc0', '#66bb6a'];
        var total = groups.reduce(function (sum, group) { return sum + group.total; }, 0);
        var current = 0;
        var slices = groups.map(function (group, index) {
            var start = current;
            current += total ? (group.total / total) * 100 : 0;
            return colors[index % colors.length] + ' ' + start.toFixed(2) + '% ' + current.toFixed(2) + '%';
        }).join(', ');
        var legend = groups.map(function (group, index) {
            return '<li><span class="relatorio-agenda-grafico-cor" style="background:' +
                colors[index % colors.length] + '"></span><strong>' + escapeHtml(group.label) +
                '</strong><span>' + group.total + '</span></li>';
        }).join('');
        return '<section class="relatorio-agenda-grafico-card"><h4>' + escapeHtml(title) + '</h4>' +
            '<div class="relatorio-agenda-grafico-conteudo"><div class="relatorio-agenda-pizza" ' +
            'style="background:conic-gradient(' + slices + ')" role="img" aria-label="' +
            escapeHtml(title) + '"></div><ul>' + legend + '</ul></div></section>';
    }

    function showAgendaCharts() {
        var result = document.getElementById('relatorio-agenda-grafico-result');
        if (!result) return;
        if (!document.querySelector('.relatorio-agenda-totalizacao-box')) showAgendaTotals();
        var totals = agendaTotalsData();
        result.innerHTML = '<div class="relatorio-agenda-graficos"><h3>Gráficos da Agenda</h3>' +
            '<div class="relatorio-agenda-graficos-grid">' +
            agendaPieChartHtml('Por Status', totals.statuses) +
            agendaPieChartHtml('Por Plano', totals.plans) + '</div></div>';
        result.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }

    function agendaTotalsExportHtml() {
        var totals = agendaTotalsData();
        function table(title, groups) {
            return '<h3>' + escapeHtml(title) + '</h3><table><thead><tr><th>Descrição</th><th>Total</th></tr></thead><tbody>' +
                groups.map(function (group) {
                    return '<tr><td>' + escapeHtml(group.label) + '</td><td>' + group.total + '</td></tr>';
                }).join('') + '</tbody></table>';
        }
        return '<section class="agenda-totalizacao"><h2>Totalização da Agenda</h2>' +
            '<p><strong>Total geral:</strong> ' + agendaItems.length + '</p>' +
            table('Por Status', totals.statuses) + table('Por Plano', totals.plans) + '</section>';
    }

    function agendaTotalsSelected() {
        var checkbox = document.getElementById('relatorio-agenda-totalizacao-check');
        return Boolean(checkbox && checkbox.checked);
    }

    function agendaPeriodHtml() {
        var startInput = document.getElementById('relatorio-agenda-inicio');
        var endInput = document.getElementById('relatorio-agenda-fim');
        function formatDate(value) {
            var parts = String(value || '').split('-');
            return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : value;
        }
        return '<div class="report-period"><strong>Data Inicial:</strong> ' +
            escapeHtml(formatDate(startInput ? startInput.value : '')) +
            ' &nbsp;&nbsp; <strong>Data Final:</strong> ' +
            escapeHtml(formatDate(endInput ? endInput.value : '')) + '</div>';
    }

    function showAgendaTotals() {
        var result = document.getElementById('relatorio-agenda-totalizacao-result');
        if (!result) return;
        var totals = agendaTotalsData();
        result.innerHTML = '<div class="relatorio-agenda-totalizacao-box">' +
            '<div class="relatorio-agenda-totalizacao-header">' +
            '<label class="crud-checkbox-option"><input type="checkbox" ' +
            'id="relatorio-agenda-totalizacao-check" aria-label="Selecionar totalização da agenda"> ' +
            '<strong>Totalização da Agenda</strong></label>' +
            '<span>Total geral: ' + agendaItems.length + '</span></div>' +
            agendaTotalsSection('Por Status', 'Total ', totals.statuses) +
            agendaTotalsSection('Por Plano', 'Total ', totals.plans) + '</div>';
        result.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }

    function selectedAgendaItems() {
        return Array.from(document.querySelectorAll('.relatorio-agenda-item-check:checked')).map(function (checkbox) {
            return agendaItems[Number(checkbox.dataset.index)];
        }).filter(Boolean);
    }

    function selectedAgendaColumns() {
        return Array.from(document.querySelectorAll('.relatorio-agenda-coluna-check:checked')).map(function (checkbox) {
            return checkbox.dataset.column;
        });
    }

    function updateAgendaSelection() {
        var checks = Array.from(document.querySelectorAll('.relatorio-agenda-item-check'));
        var selected = checks.filter(function (checkbox) { return checkbox.checked; }).length;
        var label = document.getElementById('relatorio-agenda-selecionados');
        if (label) label.textContent = 'Selecionados: ' + selected;
        var selectAll = document.getElementById('relatorio-agenda-selecionar-todos');
        if (selectAll) {
            selectAll.checked = checks.length > 0 && selected === checks.length;
            selectAll.indeterminate = selected > 0 && selected < checks.length;
        }
    }

    function agendaDataTableHtml(items, fields) {
        var labels = {
            codigo: 'Código', data: 'Data', hora: 'Hora', paciente: 'Paciente', prof_saude: 'Prof. Saúde',
            telefone: 'Telefone', plano: 'Plano', procedimento: 'Procedimento', status: 'Status',
            observacao: 'Observação', email: 'E-mail'
        };
        return '<table><thead><tr>' + fields.map(function (field) {
            return '<th>' + escapeHtml(labels[field] || columnLabel(field)) + '</th>';
        }).join('') + '</tr></thead><tbody>' + items.map(function (item) {
            return '<tr>' + fields.map(function (field) { return '<td>' + escapeHtml(item[field]) + '</td>'; }).join('') + '</tr>';
        }).join('') + '</tbody></table>';
    }

    function agendaSelection() {
        var items = selectedAgendaItems();
        var fields = selectedAgendaColumns();
        var includeTotals = agendaTotalsSelected();
        if (!items.length && !includeTotals) {
            alert('Selecione pelo menos um agendamento ou marque a Totalização da Agenda.');
            return null;
        }
        if (items.length && !fields.length) { alert('Selecione pelo menos uma coluna.'); return null; }
        return {items: items, fields: fields};
    }

    function exportAgendaExcel() {
        var selection = agendaSelection();
        if (!selection) return;
        var content = '<html><head><meta charset="utf-8"><style>' +
            'table{border-collapse:collapse;margin-bottom:12px}th,td{border:1px solid #b8c8dc;padding:6px;text-align:left}' +
            '.report-period{font-weight:bold;background:#eef5ff;padding:6px;margin-bottom:12px}' +
            '</style></head><body>' + agendaPeriodHtml() +
            (selection.items.length ? agendaDataTableHtml(selection.items, selection.fields) : '') +
            (agendaTotalsSelected() ? agendaTotalsExportHtml() : '') + '</body></html>';
        var link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([content], {type: 'application/vnd.ms-excel'}));
        link.download = 'relatorio-agenda.xls'; link.click();
        setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
    }

    function printAgenda() {
        var selection = agendaSelection();
        if (!selection) return;
        var companyPage = document.getElementById('relatorios-page');
        var company = companyPage ? companyPage.dataset.empresa || '' : '';
        var groups = [];
        if (selection.items.length) {
            for (var index = 0; index < selection.fields.length; index += 7) groups.push(selection.fields.slice(index, index + 7));
        }
        var tables = groups.map(function (fields, index) {
            return '<section class="group">' + (index ? '<h2>Continuação dos campos</h2>' : '') +
                agendaDataTableHtml(selection.items, fields) + '</section>';
        }).join('');
        var popup = window.open('', '_blank', 'width=1100,height=750');
        if (!popup) return;
        popup.document.write('<!doctype html><html><head><meta charset="utf-8"><title>Relatório da Agenda</title>' +
            '<style>@page{size:landscape;margin:12mm}body{font-family:Arial;margin:0}h1{font-size:20px;margin:0 0 4px}' +
            '.company{font-weight:bold;margin-bottom:6px}.report-period{margin-bottom:14px}' +
            '.group{margin-bottom:18px;page-break-inside:avoid}' +
            '.group h2{font-size:13px}table{width:100%;table-layout:fixed;border-collapse:collapse}' +
            'th,td{border:1px solid #bbb;padding:5px;font-size:9px;text-align:left;overflow-wrap:anywhere}' +
            'th{background:#eee}</style></head><body><h1>Relatório da Agenda</h1><div class="company">Empresa: ' +
            escapeHtml(company) + '</div>' + agendaPeriodHtml() + tables +
            (agendaTotalsSelected() ? agendaTotalsExportHtml() : '') + '</body></html>');
        popup.document.close(); popup.focus(); popup.print();
    }

    function dataTableHtml(items, selectedColumns) {
        var fields = selectedColumns || colunas;
        var header = fields.map(function (column) {
            return '<th>' + escapeHtml(columnLabel(column)) + '</th>';
        }).join('');
        var rows = items.map(function (item) {
            return '<tr>' + fields.map(function (column) {
                return '<td>' + escapeHtml(item[column]) + '</td>';
            }).join('') + '</tr>';
        }).join('');
        return '<table><thead><tr>' + header + '</tr></thead><tbody>' + rows + '</tbody></table>';
    }

    function reportTableHtml(items) {
        if (!items.length) return '<div class="crud-empty">Nenhum paciente encontrado.</div>';
        var header = colunas.map(function (column) {
            return '<th><label class="relatorio-column-label"><input type="checkbox" ' +
                'class="relatorio-coluna-check" data-column="' + escapeHtml(column) + '" checked> ' +
                '<span>' + escapeHtml(columnLabel(column)) + '</span></label></th>';
        }).join('');
        var rows = items.map(function (item, index) {
            return '<tr><td class="relatorio-select-cell"><input type="checkbox" class="relatorio-paciente-check" ' +
                'data-index="' + index + '" aria-label="Selecionar ' + escapeHtml(item.nomecli || item.codcli || index + 1) + '"></td>' +
                colunas.map(function (column) { return '<td>' + escapeHtml(item[column]) + '</td>'; }).join('') + '</tr>';
        }).join('');
        return '<div class="crud-toolbar relatorios-actions"><strong>Total: ' + items.length + '</strong>' +
            '<span id="relatorios-selecionados">Selecionados: 0</span>' +
            '<button class="crud-button crud-button-secondary" id="relatorios-excel" type="button">' +
            '<i class="fa fa-file-excel"></i> Excel</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorios-imprimir" type="button">' +
            '<i class="fa fa-print"></i> Imprimir</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorios-email" type="button">' +
            '<i class="fa fa-envelope"></i> E-mail</button>' +
            '<button class="crud-button crud-button-secondary" id="relatorios-whatsapp" type="button">' +
            '<i class="fa-brands fa-whatsapp"></i> WhatsApp</button></div>' +
            '<div class="crud-table-wrap"><table class="crud-table" id="relatorios-pacientes-tabela"><thead><tr>' +
            '<th class="relatorio-select-cell"><input type="checkbox" id="relatorios-selecionar-todos" ' +
            'aria-label="Selecionar todos os pacientes"></th>' + header + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
    }

    function selectedPatients() {
        return Array.from(document.querySelectorAll('.relatorio-paciente-check:checked')).map(function (checkbox) {
            return pacientes[Number(checkbox.dataset.index)];
        }).filter(Boolean);
    }

    function updateSelectionCount() {
        var count = selectedPatients().length;
        var label = document.getElementById('relatorios-selecionados');
        if (label) label.textContent = 'Selecionados: ' + count;
    }

    function requireSelection() {
        var selected = selectedPatients();
        if (!selected.length) {
            alert('Selecione pelo menos um paciente.');
            return null;
        }
        return selected;
    }

    async function sendPatientMessages(channel) {
        var selected = requireSelection();
        if (!selected) return;
        var isWhatsapp = channel === 'whatsapp';
        var channelLabel = isWhatsapp ? 'WhatsApp' : 'e-mail';
        var patternsResponse = await fetch('/api/agenda/textos-confirmacao', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tipo: isWhatsapp ? 'Z' : 'E'})
        });
        var patternsData = await patternsResponse.json();
        if (!patternsResponse.ok || patternsData.success === false) {
            throw new Error(patternsData.message || 'Erro ao carregar os textos padrão.');
        }
        if (!(patternsData.textos || []).length) {
            alert('Nenhum texto padrão de ' + channelLabel + ' foi cadastrado.');
            return;
        }
        CrudUI.openForm({
            title: 'Enviar mensagem por ' + channelLabel,
            submitLabel: 'Enviar ' + channelLabel,
            fields: [{
                name: 'codigo_texto',
                label: 'Mensagem padrão',
                type: 'select',
                required: true,
                wide: true,
                options: [{value: '', label: 'Selecione'}].concat(patternsData.textos)
            }],
            onSubmit: async function (values) {
                var response = await fetch('/api/relatorios/pacientes/enviar-mensagem', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        canal: channel,
                        codigo_texto: values.codigo_texto,
                        pacientes: selected.map(function (patient) { return patient.codcli; })
                    })
                });
                var data = await response.json();
                if (!response.ok || data.success === false) {
                    var details = (data.resultados || []).filter(function (item) {
                        return !item.sucesso;
                    }).map(function (item) {
                        return (item.paciente || item.paciente_id) + ': ' + item.erro;
                    }).join('\n');
                    throw new Error((data.message || 'Falha no envio.') + (details ? '\n' + details : ''));
                }
                CrudUI.notify(data.message || 'Mensagens processadas.');
            }
        });
    }

    function selectedReportColumns() {
        var selected = Array.from(document.querySelectorAll('.relatorio-coluna-check:checked')).map(function (checkbox) {
            return checkbox.dataset.column;
        });
        if (!selected.length) {
            alert('Selecione pelo menos uma coluna.');
            return null;
        }
        return selected;
    }

    function exportExcel() {
        var selected = requireSelection();
        if (!selected) return;
        var fields = selectedReportColumns();
        if (!fields) return;
        var content = '<html><head><meta charset="utf-8"></head><body>' + dataTableHtml(selected, fields) + '</body></html>';
        var link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([content], {type: 'application/vnd.ms-excel'}));
        link.download = 'relatorio-pacientes.xls';
        link.click();
        setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
    }

    function printReport() {
        var selected = requireSelection();
        if (!selected) return;
        var fields = selectedReportColumns();
        if (!fields) return;
        var page = document.getElementById('relatorios-page');
        var company = page ? page.dataset.empresa || '' : '';
        var fieldGroups = [];
        for (var index = 0; index < fields.length; index += 7) {
            fieldGroups.push(fields.slice(index, index + 7));
        }
        var tables = fieldGroups.map(function (group, groupIndex) {
            return '<section class="report-column-group">' +
                (groupIndex ? '<h2>Continuação dos campos</h2>' : '') +
                dataTableHtml(selected, group) + '</section>';
        }).join('');
        var popup = window.open('', '_blank', 'width=1100,height=750');
        if (!popup) return;
        popup.document.write('<!doctype html><html><head><meta charset="utf-8"><title>Relatório de Pacientes</title>' +
            '<style>@page{size:landscape;margin:12mm}body{font-family:Arial;margin:0}h1{font-size:20px;margin:0 0 4px}' +
            '.company{font-size:14px;font-weight:bold;margin-bottom:14px}.report-column-group{margin:0 0 18px;' +
            'page-break-inside:avoid}.report-column-group h2{font-size:13px;margin:12px 0 5px}' +
            'table{width:100%;table-layout:fixed;border-collapse:collapse}th,td{border:1px solid #bbb;padding:5px;' +
            'text-align:left;font-size:9px;white-space:normal;overflow-wrap:anywhere}th{background:#eee}</style></head>' +
            '<body><h1>Relatório de Pacientes</h1><div class="company">Empresa: ' + escapeHtml(company) +
            '</div>' + tables + '</body></html>');
        popup.document.close(); popup.focus(); popup.print();
    }

    function patientFilterOptions() {
        var plans = {};
        pacientesOriginais.forEach(function (item) {
            [item.nomeplano1, item.nomeplano2].forEach(function (plan) {
                plan = String(plan || '').trim();
                if (plan) plans[plan.toLocaleUpperCase('pt-BR')] = plan;
            });
        });
        var planOptions = Object.keys(plans).sort(function (left, right) {
            return plans[left].localeCompare(plans[right], 'pt-BR');
        }).map(function (key) {
            return '<option value="' + escapeHtml(plans[key]) + '">' + escapeHtml(plans[key]) + '</option>';
        }).join('');
        var months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
        var monthOptions = months.map(function (month, index) {
            return '<option value="' + (index + 1) + '">' + (index + 1) + ' - ' + month + '</option>';
        }).join('');
        var recentOptions = Array.from({length: 12}, function (_item, index) {
            var value = index + 1;
            return '<option value="' + value + '">' + value + (value === 1 ? ' mês' : ' meses') + '</option>';
        }).join('');
        return '<div class="crud-toolbar relatorio-paciente-filtros">' +
            '<div class="crud-field"><label for="relatorio-paciente-filtro-plano">Plano</label>' +
            '<select class="crud-input" id="relatorio-paciente-filtro-plano"><option value="">Todos</option>' +
            planOptions + '</select></div>' +
            '<div class="crud-field"><label for="relatorio-paciente-filtro-sexo">Sexo</label>' +
            '<select class="crud-input" id="relatorio-paciente-filtro-sexo"><option value="">Todos</option>' +
            '<option value="M">Masculino</option><option value="F">Feminino</option></select></div>' +
            '<div class="crud-field"><label for="relatorio-paciente-filtro-aniversario">Aniversariantes</label>' +
            '<select class="crud-input" id="relatorio-paciente-filtro-aniversario"><option value="">Todos</option>' +
            monthOptions + '</select></div>' +
            '<div class="crud-field"><label for="relatorio-paciente-filtro-ultima">Última consulta</label>' +
            '<select class="crud-input" id="relatorio-paciente-filtro-ultima"><option value="">Todos</option>' +
            recentOptions + '</select></div>' +
            '<button class="crud-button" id="relatorio-paciente-aplicar-filtros" type="button">' +
            '<i class="fa fa-filter"></i> Filtrar</button></div>';
    }

    function patientDate(value) {
        var text = String(value || '').trim();
        if (!text) return null;
        var match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
        match = text.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        return match ? new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1])) : null;
    }

    function renderPatientTable(items) {
        pacientes = items;
        var tableResult = document.getElementById('relatorio-paciente-tabela-result');
        if (!tableResult) return;
        tableResult.innerHTML = reportTableHtml(items);
        var selectAll = document.getElementById('relatorios-selecionar-todos');
        if (selectAll) selectAll.onchange = function () {
            document.querySelectorAll('.relatorio-paciente-check').forEach(function (checkbox) {
                checkbox.checked = selectAll.checked;
            });
            updateSelectionCount();
        };
        document.querySelectorAll('.relatorio-paciente-check').forEach(function (checkbox) {
            checkbox.onchange = function () {
                var checks = Array.from(document.querySelectorAll('.relatorio-paciente-check'));
                if (selectAll) {
                    selectAll.checked = checks.length > 0 && checks.every(function (item) { return item.checked; });
                    selectAll.indeterminate = checks.some(function (item) { return item.checked; }) && !selectAll.checked;
                }
                updateSelectionCount();
            };
        });
        var excel = document.getElementById('relatorios-excel');
        var print = document.getElementById('relatorios-imprimir');
        var email = document.getElementById('relatorios-email');
        var whatsapp = document.getElementById('relatorios-whatsapp');
        if (excel) excel.onclick = exportExcel;
        if (print) print.onclick = printReport;
        if (email) email.onclick = function () {
            sendPatientMessages('email').catch(function (error) { alert(error.message); });
        };
        if (whatsapp) whatsapp.onclick = function () {
            sendPatientMessages('whatsapp').catch(function (error) { alert(error.message); });
        };
    }

    function applyPatientFilters() {
        var plan = document.getElementById('relatorio-paciente-filtro-plano').value.trim().toLocaleUpperCase('pt-BR');
        var sex = document.getElementById('relatorio-paciente-filtro-sexo').value;
        var birthdayMonth = Number(document.getElementById('relatorio-paciente-filtro-aniversario').value || 0);
        var recentMonths = Number(document.getElementById('relatorio-paciente-filtro-ultima').value || 0);
        var cutoff = new Date();
        if (recentMonths) cutoff.setMonth(cutoff.getMonth() - recentMonths);
        var filtered = pacientesOriginais.filter(function (item) {
            var plans = [item.nomeplano1, item.nomeplano2].map(function (value) {
                return String(value || '').trim().toLocaleUpperCase('pt-BR');
            });
            var itemSex = String(item.sexo || '').trim().toLocaleUpperCase('pt-BR');
            var birthDate = patientDate(item.datanasc_ || item.datanasc || item.nascimento);
            var lastVisit = patientDate(item.datult_ || item.datult || item.datault_ || item.datault);
            if (plan && plans.indexOf(plan) < 0) return false;
            if (sex && itemSex.charAt(0) !== sex) return false;
            if (birthdayMonth && (!birthDate || birthDate.getMonth() + 1 !== birthdayMonth)) return false;
            if (recentMonths && (!lastVisit || lastVisit <= cutoff)) return false;
            return true;
        });
        renderPatientTable(filtered);
    }

    function renderPatients(items, fields) {
        pacientesOriginais = items;
        colunas = fields || [];
        var result = document.getElementById('relatorios-result');
        result.innerHTML = patientFilterOptions() + '<div id="relatorio-paciente-tabela-result"></div>';
        document.getElementById('relatorio-paciente-aplicar-filtros').onclick = applyPatientFilters;
        renderPatientTable(items);
    }

    async function loadPatients(all) {
        var input = document.getElementById('relatorio-paciente-termo');
        var term = input ? input.value.trim() : '';
        var searchField = document.getElementById('relatorio-paciente-campo');
        if (!all && !term) throw new Error('Informe o valor para pesquisar o paciente.');
        var history = document.getElementById('relatorio-incluir-historico');
        var data = await api({
            todos: all,
            termo: term,
            campo: searchField ? searchField.value : 'nome',
            historico_clinico: !!(history && history.checked)
        });
        renderPatients(data.pacientes || [], data.colunas || []);
    }

    function showPatientOptions() {
        var result = document.getElementById('relatorios-result');
        result.innerHTML = '<div class="crud-toolbar"><div class="crud-field"><label for="relatorio-paciente-modo">Pacientes</label>' +
            '<select class="crud-input" id="relatorio-paciente-modo"><option value="">Selecione</option>' +
            '<option value="buscar">Buscar paciente</option><option value="todos">Todos</option></select></div>' +
            '<div class="crud-field" id="relatorio-paciente-campo-field" hidden>' +
            '<label for="relatorio-paciente-campo">Buscar por</label>' +
            '<select class="crud-input" id="relatorio-paciente-campo"><option value="nome">Nome</option>' +
            '<option value="cpf">CPF</option><option value="telefone">Telefone</option></select></div>' +
            '<div class="crud-field" id="relatorio-paciente-busca" hidden><label for="relatorio-paciente-termo">Paciente</label>' +
            '<input class="crud-input" id="relatorio-paciente-termo" placeholder="Nome do paciente"></div>' +
            '<button class="crud-button" id="relatorio-paciente-buscar" type="button" hidden>' +
            '<i class="fa fa-search"></i> Buscar</button>' +
            '<label class="crud-checkbox-option relatorio-historico-option"><input type="checkbox" ' +
            'id="relatorio-incluir-historico" value="true"> <span>Histórico Clínico</span></label></div>';
        var mode = document.getElementById('relatorio-paciente-modo');
        var searchFieldWrapper = document.getElementById('relatorio-paciente-campo-field');
        var searchField = document.getElementById('relatorio-paciente-campo');
        var field = document.getElementById('relatorio-paciente-busca');
        var button = document.getElementById('relatorio-paciente-buscar');
        mode.onchange = function () {
            searchFieldWrapper.hidden = mode.value !== 'buscar';
            field.hidden = mode.value !== 'buscar'; button.hidden = mode.value !== 'buscar';
            if (mode.value === 'buscar') document.getElementById('relatorio-paciente-termo').focus();
            if (mode.value === 'todos') loadPatients(true).catch(function (error) {
                result.innerHTML = '<div class="crud-error">' + escapeHtml(error.message) + '</div>';
            });
        };
        searchField.onchange = function () {
            var placeholders = {nome: 'Nome do paciente', cpf: 'CPF do paciente', telefone: 'Telefone do paciente'};
            document.getElementById('relatorio-paciente-termo').placeholder = placeholders[this.value] || 'Pesquisar';
        };
        button.onclick = function () { loadPatients(false).catch(function (error) { alert(error.message); }); };
    }

    function showAgendaOptions() {
        var result = document.getElementById('relatorios-result');
        result.innerHTML = '<div class="crud-toolbar relatorio-agenda-filtros">' +
            '<div class="crud-field"><label for="relatorio-agenda-inicio">Data Início</label>' +
            '<input class="crud-input" id="relatorio-agenda-inicio" type="date"></div>' +
            '<div class="crud-field"><label for="relatorio-agenda-fim">Data Fim</label>' +
            '<input class="crud-input" id="relatorio-agenda-fim" type="date"></div>' +
            '<div class="crud-field"><label for="relatorio-agenda-profissional-modo">Prof. Saúde</label>' +
            '<select class="crud-input" id="relatorio-agenda-profissional-modo">' +
            '<option value="todos">Todos</option><option value="especifico">Específico</option></select></div>' +
            '<div class="crud-field" id="relatorio-agenda-profissional-field" hidden>' +
            '<label for="relatorio-agenda-profissional">Profissional específico</label>' +
            '<select class="crud-input" id="relatorio-agenda-profissional"><option value="">Selecione</option></select></div>' +
            '<div class="crud-field"><label for="relatorio-agenda-plano">Plano</label>' +
            '<select class="crud-input" id="relatorio-agenda-plano"><option value="">Todos</option></select></div>' +
            '<button class="crud-button" id="relatorio-agenda-buscar" type="button">' +
            '<i class="fa fa-search"></i> Buscar</button>' +
            '</div>' +
            '<div id="relatorio-agenda-result"></div>';

        var mode = document.getElementById('relatorio-agenda-profissional-modo');
        var professionalField = document.getElementById('relatorio-agenda-profissional-field');
        var professional = document.getElementById('relatorio-agenda-profissional');
        var plan = document.getElementById('relatorio-agenda-plano');
        loadAgendaPlanOptions(plan).catch(function (error) { alert(error.message); });
        mode.onchange = function () {
            professionalField.hidden = mode.value !== 'especifico';
            professionalField.style.display = mode.value === 'especifico' ? '' : 'none';
            if (mode.value === 'especifico' && professional.options.length <= 1) {
                loadProfessionalOptions(professional).catch(function (error) { alert(error.message); });
            }
        };
        professionalField.style.display = 'none';
        document.getElementById('relatorio-agenda-buscar').onclick = async function () {
            var start = document.getElementById('relatorio-agenda-inicio').value;
            var end = document.getElementById('relatorio-agenda-fim').value;
            if (!start || !end) {
                alert('Informe a Data Início e a Data Fim.');
                return;
            }
            if (end < start) {
                alert('A Data Fim deve ser igual ou posterior à Data Início.');
                return;
            }
            if (mode.value === 'especifico' && !professional.value) {
                alert('Selecione o profissional de saúde.');
                professional.focus();
                return;
            }
            var button = this;
            button.disabled = true;
            try {
                var data = await agendaApi({
                    data_inicio: start,
                    data_fim: end,
                    profissional: mode.value === 'especifico' ? professional.value : '',
                    plano: plan.value
                });
                renderAgenda(data.agendamentos || [], data.colunas || []);
            } catch (error) {
                document.getElementById('relatorio-agenda-result').innerHTML =
                    '<div class="crud-error">' + escapeHtml(error.message) + '</div>';
            } finally {
                button.disabled = false;
            }
        };
    }

    function showFinancialOptions() {
        var result = document.getElementById('relatorios-result');
        result.innerHTML = '<div class="crud-toolbar relatorio-financeiro-filtros">' +
            '<div class="crud-field"><label for="relatorio-financeiro-inicio">Data Inicial</label>' +
            '<input class="crud-input" id="relatorio-financeiro-inicio" type="date"></div>' +
            '<div class="crud-field"><label for="relatorio-financeiro-fim">Data Final</label>' +
            '<input class="crud-input" id="relatorio-financeiro-fim" type="date"></div>' +
            '<div class="crud-field"><label for="relatorio-financeiro-tipo">Tipo</label>' +
            '<select class="crud-input" id="relatorio-financeiro-tipo">' +
            '<option value="">Todas</option><option value="Despesa">Despesa</option>' +
            '<option value="Receita">Receita</option></select></div>' +
            '<button class="crud-button" id="relatorio-financeiro-buscar" type="button">' +
            '<i class="fa fa-search"></i> Buscar</button></div>' +
            '<div id="relatorio-financeiro-result"></div>';
        document.getElementById('relatorio-financeiro-buscar').onclick = async function () {
            var start = document.getElementById('relatorio-financeiro-inicio').value;
            var end = document.getElementById('relatorio-financeiro-fim').value;
            var type = document.getElementById('relatorio-financeiro-tipo').value;
            genericTotalization = false;
            if (!start || !end) { alert('Informe a Data Inicial e a Data Final.'); return; }
            if (end < start) { alert('A Data Final deve ser igual ou posterior à Data Inicial.'); return; }
            this.disabled = true;
            try {
                renderGenericReport(await financialReportApi({data_inicio: start, data_fim: end, tipo: type}));
            } catch (error) {
                document.getElementById('relatorio-financeiro-result').innerHTML =
                    '<div class="crud-error">' + escapeHtml(error.message) + '</div>';
            } finally {
                this.disabled = false;
            }
        };
    }

    function init() {
        var type = document.getElementById('relatorios-tipo');
        var search = document.getElementById('relatorios-buscar');
        if (!type || !search) return;
        search.onclick = function () {
            if (type.value === 'paciente') showPatientOptions();
            else if (type.value === 'agenda') showAgendaOptions();
            else if (type.value === 'financeiro') showFinancialOptions();
            else if (type.value === 'plano' || type.value === 'prof-saude' || type.value === 'procedimentos') {
                loadGenericReport(type.value);
            }
            else document.getElementById('relatorios-result').innerHTML =
                '<div class="crud-empty">Selecione um relatório disponível para continuar.</div>';
        };
    }

    window.Relatorios = {init: init};
}());
