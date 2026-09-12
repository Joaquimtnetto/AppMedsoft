(function () {
    function headers() {
        return {
            'Content-Type': 'application/json',
            'X-DB-PATH': localStorage.getItem('db_path') || ''
        };
    }

    function formatDateTime(value) {
        if (!value) return '—';
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat('pt-BR', {
            dateStyle: 'short',
            timeStyle: 'medium'
        }).format(date);
    }

    function typeLabel(value) {
        if (value === 'Email Auto') return 'E-mail automático';
        if (value === 'Email Manual' || value === 'Email') return 'E-mail manual';
        return value === 'Whatzap' ? 'WhatsApp' : (value || '—');
    }

    function messageLabel(item) {
        if (item.mensagem == null || item.mensagem === '') return '—';
        return String(item.mensagem) + (item.mensagem_nome ? ' - ' + item.mensagem_nome : '');
    }

    function renderRows(items) {
        if (!items.length) {
            return '<div class="crud-empty">Nenhuma mensagem enviada encontrada.</div>';
        }
        var rows = items.map(function (item) {
            var icon = item.tipo === 'Whatzap' ? 'fa-brands fa-whatsapp' : 'fa fa-envelope';
            var agendaButton = item.codagenda
                ? '<button type="button" class="mensagens-agenda-button" data-open-agenda="' +
                    CrudUI.escapeHtml(item.codagenda) + '" data-agenda-data="' +
                    CrudUI.escapeHtml(item.agenda_data || '') +
                    '" title="Abrir agendamento" aria-label="Abrir agendamento"><i class="fa fa-plus"></i></button>'
                : '<button type="button" class="mensagens-agenda-button" disabled ' +
                    'title="Log sem agenda vinculada" aria-label="Log sem agenda vinculada"><i class="fa fa-plus"></i></button>';
            var recipientButton = item.destino &&
                String(item.destino).toLocaleLowerCase('pt-BR') !== 'não informado'
                ? '<button type="button" class="mensagens-agenda-button" data-open-recipient="' +
                    CrudUI.escapeHtml(item.destino) + '" data-recipient-type="' +
                    CrudUI.escapeHtml(item.tipo || '') +
                    '" title="Abrir paciente destinatário" aria-label="Abrir paciente destinatário">' +
                    '<i class="fa fa-plus"></i></button>'
                : '<button type="button" class="mensagens-agenda-button" disabled ' +
                    'title="Log sem destinatário informado" aria-label="Log sem destinatário informado">' +
                    '<i class="fa fa-plus"></i></button>';
            return '<tr>' +
                '<td data-label="Código">' + CrudUI.escapeHtml(item.codigo) + '</td>' +
                '<td data-label="Data/Hora">' + CrudUI.escapeHtml(formatDateTime(item.datahoraenvio)) + '</td>' +
                '<td data-label="Tipo"><span class="mensagens-type"><i class="' + icon + '"></i> ' +
                    CrudUI.escapeHtml(typeLabel(item.tipo)) + '</span></td>' +
                '<td data-label="Destino" class="mensagens-destino">' +
                    CrudUI.escapeHtml(item.destino || '—') + '</td>' +
                '<td data-label="Mensagem">' + CrudUI.escapeHtml(messageLabel(item)) + '</td>' +
                '<td data-label="Enviado"><span class="mensagens-status ' +
                    (item.enviado === 'Não' ? 'mensagens-status-error' : 'mensagens-status-success') + '">' +
                    CrudUI.escapeHtml(item.enviado || 'Sim') + '</span></td>' +
                '<td data-label="Motivo" class="mensagens-motivo">' +
                    CrudUI.escapeHtml(item.motivoerro || '—') + '</td>' +
                '<td data-label="Destino" class="mensagens-agenda-action">' + recipientButton + '</td>' +
                '<td data-label="Agenda" class="mensagens-agenda-action">' + agendaButton + '</td>' +
            '</tr>';
        }).join('');
        return '<table class="mensagens-table">' +
            '<thead><tr><th>Código</th><th>Data/Hora</th><th>Tipo</th><th>Destino</th><th>Mensagem</th><th>Enviado</th><th>Motivo</th><th>Destino</th><th>Agenda</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table>';
    }

    function init() {
        var pageRoot = document.getElementById('mensagens-enviadas-page');
        if (!pageRoot || pageRoot.dataset.initialized === 'true') return;
        pageRoot.dataset.initialized = 'true';

        var result = document.getElementById('mensagens-result');
        var summary = document.getElementById('mensagens-resumo');
        var pagination = document.getElementById('mensagens-pagination');
        var previous = document.getElementById('mensagens-anterior');
        var next = document.getElementById('mensagens-proxima');
        var pageLabel = document.getElementById('mensagens-pagina');
        var currentPage = 1;

        async function load(pageNumber) {
            result.innerHTML = '<div class="crud-loading">Carregando mensagens...</div>';
            try {
                var data = await CrudUI.request('/api/mensagens-enviadas', {
                    method: 'POST',
                    headers: headers(),
                    body: JSON.stringify({
                        data_inicial: document.getElementById('mensagens-data-inicial').value,
                        data_final: document.getElementById('mensagens-data-final').value,
                        tipo: document.getElementById('mensagens-tipo').value,
                        destino: document.getElementById('mensagens-destino').value,
                        pagina: pageNumber || 1
                    })
                });
                currentPage = data.pagina;
                result.innerHTML = renderRows(data.mensagens || []);
                summary.textContent = data.total === 1 ? '1 mensagem encontrada' : data.total + ' mensagens encontradas';
                pagination.hidden = data.total === 0;
                pageLabel.textContent = 'Página ' + data.pagina + ' de ' + data.total_paginas;
                previous.disabled = data.pagina <= 1;
                next.disabled = data.pagina >= data.total_paginas;
            } catch (error) {
                summary.textContent = '';
                pagination.hidden = true;
                result.innerHTML = '<div class="crud-error">' +
                    CrudUI.escapeHtml(error.message || 'Não foi possível consultar as mensagens.') + '</div>';
            }
        }

        document.getElementById('mensagens-pesquisar').onclick = function () { load(1); };
        document.getElementById('mensagens-limpar').onclick = function () {
            document.getElementById('mensagens-data-inicial').value = '';
            document.getElementById('mensagens-data-final').value = '';
            document.getElementById('mensagens-tipo').value = '';
            document.getElementById('mensagens-destino').value = '';
            load(1);
        };
        document.getElementById('mensagens-destino').addEventListener('keydown', function (event) {
            if (event.key === 'Enter') load(1);
        });
        result.addEventListener('click', function (event) {
            var recipientButton = event.target.closest('[data-open-recipient]');
            if (recipientButton && !recipientButton.disabled && window.carregarTela) {
                recipientButton.disabled = true;
                CrudUI.request('/api/mensagens-enviadas/destinatario-paciente', {
                    method: 'POST',
                    headers: headers(),
                    body: JSON.stringify({
                        destino: recipientButton.dataset.openRecipient,
                        tipo: recipientButton.dataset.recipientType || ''
                    })
                }).then(function (data) {
                    window.pacienteAgendaPendente = String(data.paciente.codcli);
                    window.carregarTela('consulta_paciente.html');
                }).catch(function (error) {
                    CrudUI.notify(error.message || 'Não foi possível localizar o paciente.', 'error');
                    recipientButton.disabled = false;
                });
                return;
            }
            var button = event.target.closest('[data-open-agenda]');
            if (!button || button.disabled || !window.carregarTela) return;
            window.agendaLogPendente = {
                id: button.dataset.openAgenda,
                data: button.dataset.agendaData || ''
            };
            window.agendaLogLoadingDone = CrudUI.showLoading('Carregando o agendamento vinculado. Aguarde...');
            window.carregarTela('agenda');
        });
        previous.onclick = function () { if (currentPage > 1) load(currentPage - 1); };
        next.onclick = function () { load(currentPage + 1); };
        load(1);
    }

    window.MensagensEnviadas = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
