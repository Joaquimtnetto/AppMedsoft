(function () {
    function headers() { return {'Content-Type': 'application/json'}; }
    function formatDate(value, full) {
        if (!value) return '';
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat('pt-BR', full
            ? {dateStyle: 'short', timeStyle: 'short'} : {hour: '2-digit', minute: '2-digit'}).format(date);
    }
    function init() {
        var page = document.getElementById('crm-email-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var list = document.getElementById('crm-email-list');
        var chat = document.getElementById('crm-email-chat');
        var search = document.getElementById('crm-email-search');
        var conversations = [], selected = '';

        function renderList() {
            var term = search.value.trim().toLocaleLowerCase('pt-BR');
            var items = conversations.filter(function (item) {
                return !term || (item.paciente + ' ' + item.destino).toLocaleLowerCase('pt-BR').indexOf(term) !== -1;
            });
            list.innerHTML = items.length ? items.map(function (item) {
                return '<button type="button" class="crm-conversation' + (selected === item.destino ? ' is-active' : '') +
                    '" data-email="' + CrudUI.escapeHtml(item.destino) + '"><span class="crm-conversation-avatar crm-email-avatar">' +
                    '<i class="fa fa-envelope"></i></span><span class="crm-conversation-body"><span class="crm-conversation-title">' +
                    CrudUI.escapeHtml(item.paciente || item.destino) + '</span><span class="crm-conversation-preview">' +
                    CrudUI.escapeHtml(item.ultima_mensagem || 'E-mail enviado') + '</span></span><span class="crm-conversation-side"><time>' +
                    CrudUI.escapeHtml(formatDate(item.ultima_data, true)) + '</time><span>' + CrudUI.escapeHtml(item.total) +
                    '</span></span></button>';
            }).join('') : '<div class="crud-empty">Nenhuma conversa encontrada.</div>';
        }

        async function open(email) {
            selected = email; renderList();
            var conversation = conversations.find(function (item) { return item.destino === email; }) || {};
            chat.innerHTML = '<div class="crud-loading">Carregando histórico...</div>';
            try {
                var data = await CrudUI.request('/api/crm/email/historico', {
                    method: 'POST', headers: headers(), body: JSON.stringify({destino: email})
                });
                var bubbles = (data.mensagens || []).map(function (message) {
                    var failed = message.enviado === 'Não';
                    return '<article class="crm-chat-message is-outgoing crm-email-message' + (failed ? ' is-error' : '') + '">' +
                        '<div class="crm-chat-message-text">' + CrudUI.escapeHtml(message.conteudo ||
                            'E-mail antigo: o conteúdo original não foi armazenado.') + '</div><div class="crm-chat-message-meta"><time>' +
                        CrudUI.escapeHtml(formatDate(message.datahora, true)) + '</time><span>' + (failed
                            ? '<i class="fa fa-circle-xmark"></i> Falha' : '<i class="fa fa-check"></i> Enviado') +
                        '</span></div>' + (failed && message.motivoerro ? '<div class="crm-chat-error">' +
                            CrudUI.escapeHtml(message.motivoerro) + '</div>' : '') + '</article>';
                }).join('') || '<div class="crud-empty">Nenhum e-mail nesta conversa.</div>';
                chat.innerHTML = '<header class="crm-chat-header"><span class="crm-conversation-avatar crm-email-avatar">' +
                    '<i class="fa fa-envelope"></i></span><div><h3>' + CrudUI.escapeHtml(conversation.paciente || email) +
                    '</h3><p>' + CrudUI.escapeHtml(email) + '</p></div></header><div class="crm-chat-history" id="crm-email-history">' +
                    bubbles + '</div>';
                var history = document.getElementById('crm-email-history'); history.scrollTop = history.scrollHeight;
            } catch (error) {
                chat.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message || 'Erro ao carregar histórico.') + '</div>';
            }
        }

        async function load() {
            list.innerHTML = '<div class="crud-loading">Carregando conversas...</div>';
            try {
                var data = await CrudUI.request('/api/crm/email/conversas', {method: 'GET', headers: headers()});
                conversations = data.conversas || []; renderList();
                if (selected) open(selected);
            } catch (error) {
                list.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message || 'Erro ao carregar conversas.') + '</div>';
            }
        }
        list.addEventListener('click', function (event) { var button = event.target.closest('[data-email]'); if (button) open(button.dataset.email); });
        search.addEventListener('input', renderList);
        document.getElementById('crm-email-refresh').onclick = load;
        load();
    }
    window.CrmEmail = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}());
