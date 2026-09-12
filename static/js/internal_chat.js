(function() {
    'use strict';

    if (window.MedsoftInternalChat) return;

    const state = {
        open: false,
        loaded: false,
        lastId: 0,
        unread: 0,
        me: null,
        polling: null,
        sending: false,
    };

    const selectors = {
        button: 'medsoft-internal-chat-button',
        badge: 'medsoft-internal-chat-badge',
        panel: 'medsoft-internal-chat-panel',
        body: 'medsoft-internal-chat-body',
        input: 'medsoft-internal-chat-input',
        status: 'medsoft-internal-chat-status',
        title: 'medsoft-internal-chat-title',
    };

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatTime(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    async function requestJson(url, options) {
        const response = await fetch(url, Object.assign({
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
        }, options || {}));
        const payload = await response.json().catch(function() { return {}; });
        if (response.status === 401) {
            const error = new Error(payload.message || 'Sessao expirada.');
            error.authExpired = true;
            throw error;
        }
        if (!response.ok || payload.success === false) {
            throw new Error(payload.message || 'Falha na comunicacao com o chat interno.');
        }
        return payload;
    }

    function hasAuthenticatedSession() {
        const path = window.location.pathname.toLowerCase();
        return !(
            path === '/' ||
            path.endsWith('/login.html') ||
            path.endsWith('/esqueci-senha') ||
            path.indexOf('/reset-password') !== -1
        );
    }

    function setStatus(message, isError) {
        const status = document.getElementById(selectors.status);
        if (!status) return;
        status.textContent = message || '';
        status.classList.toggle('is-error', Boolean(isError));
    }

    function setUnread(value) {
        state.unread = Math.max(0, value || 0);
        const badge = document.getElementById(selectors.badge);
        if (!badge) return;
        badge.textContent = state.unread > 99 ? '99+' : String(state.unread);
        badge.hidden = state.unread <= 0;
    }

    function disableWidget() {
        const widget = document.querySelector('.medsoft-internal-chat');
        if (widget) widget.remove();
        if (state.polling) {
            clearInterval(state.polling);
            state.polling = null;
        }
    }

    function scrollToBottom() {
        const body = document.getElementById(selectors.body);
        if (body) body.scrollTop = body.scrollHeight;
    }

    function renderMessage(message) {
        const body = document.getElementById(selectors.body);
        if (!body) return;
        const empty = body.querySelector('.internal-chat-empty');
        if (empty) empty.remove();
        const item = document.createElement('article');
        item.className = 'internal-chat-message ' + (message.mine ? 'is-mine' : 'is-other');
        item.dataset.messageId = message.id;
        item.innerHTML = [
            '<div class="internal-chat-message-sender">' + escapeHtml(message.mine ? 'Voce' : message.sender_name) + '</div>',
            '<div class="internal-chat-message-text">' + escapeHtml(message.message).replace(/\n/g, '<br>') + '</div>',
            '<div class="internal-chat-message-time">' + escapeHtml(formatTime(message.created_at)) + '</div>',
        ].join('');
        body.appendChild(item);
    }

    function renderMessages(messages, countUnread) {
        if (!Array.isArray(messages) || !messages.length) return;
        let appended = false;
        messages.forEach(function(message) {
            const id = Number(message.id || 0);
            if (!id || document.querySelector('[data-message-id="' + id + '"]')) return;
            renderMessage(message);
            state.lastId = Math.max(state.lastId, id);
            if (countUnread && !state.open && !message.mine) setUnread(state.unread + 1);
            appended = true;
        });
        if (appended && state.open) {
            setUnread(0);
            scrollToBottom();
        }
    }

    async function loadMessages(initial) {
        try {
            const query = initial || !state.lastId ? '' : '?after_id=' + encodeURIComponent(state.lastId);
            const payload = await requestJson('/api/internal-chat/messages' + query);
            renderMessages(payload.messages || [], state.loaded && !initial);
            if (initial && (!payload.messages || !payload.messages.length)) {
                const body = document.getElementById(selectors.body);
                if (body && !body.querySelector('.internal-chat-empty')) {
                    body.innerHTML = '<div class="internal-chat-empty">Nenhuma mensagem interna ainda.</div>';
                }
            }
            setStatus('');
            state.loaded = true;
        } catch (error) {
            if (error.authExpired) {
                disableWidget();
                return;
            }
            setStatus(error.message, true);
        }
    }

    async function sendMessage() {
        const input = document.getElementById(selectors.input);
        if (!input || state.sending) return;
        const text = input.value.trim();
        if (!text) return;
        state.sending = true;
        input.disabled = true;
        try {
            const payload = await requestJson('/api/internal-chat/messages', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: text }),
            });
            input.value = '';
            renderMessages([payload.message], false);
            setStatus('');
        } catch (error) {
            if (error.authExpired) {
                disableWidget();
                return;
            }
            setStatus(error.message, true);
        } finally {
            state.sending = false;
            input.disabled = false;
            input.focus();
        }
    }

    async function clearHistory() {
        const body = document.getElementById(selectors.body);
        try {
            await requestJson('/api/internal-chat/messages', { method: 'DELETE' });
            state.lastId = 0;
            state.unread = 0;
            setUnread(0);
            if (body) body.innerHTML = '<div class="internal-chat-empty">Nenhuma mensagem interna ainda.</div>';
            setStatus('Historico limpo.');
        } catch (error) {
            if (error.authExpired) {
                disableWidget();
                return;
            }
            setStatus(error.message || 'Erro ao limpar historico.', true);
        }
    }

    async function loadMe() {
        try {
            const payload = await requestJson('/api/internal-chat/me');
            state.me = payload;
            const title = document.getElementById(selectors.title);
            if (title && payload.usuario) title.textContent = 'Chat interno - ' + payload.usuario;
        } catch (error) {
            if (error.authExpired) {
                disableWidget();
                return;
            }
            setStatus(error.message, true);
        }
    }

    function openPanel() {
        state.open = true;
        document.getElementById(selectors.panel).classList.add('is-open');
        setUnread(0);
        if (!state.loaded) {
            loadMe();
            loadMessages(true).then(scrollToBottom);
        } else {
            loadMessages(false).then(scrollToBottom);
        }
        const input = document.getElementById(selectors.input);
        if (input) setTimeout(function() { input.focus(); }, 80);
    }

    function closePanel() {
        state.open = false;
        document.getElementById(selectors.panel).classList.remove('is-open');
    }

    function togglePanel() {
        if (state.open) closePanel();
        else openPanel();
    }

    function buildWidget() {
        const wrapper = document.createElement('div');
        wrapper.className = 'medsoft-internal-chat';
        wrapper.innerHTML = [
            '<button type="button" class="internal-chat-fab" id="' + selectors.button + '" title="Chat interno">',
            '  <i class="fa fa-message"></i>',
            '  <span id="' + selectors.badge + '" class="internal-chat-badge" hidden>0</span>',
            '</button>',
            '<section class="internal-chat-panel" id="' + selectors.panel + '" aria-label="Chat interno">',
            '  <header class="internal-chat-header">',
            '    <div>',
            '      <strong id="' + selectors.title + '">Chat interno</strong>',
            '      <span>Mensagens entre usuarios deste login</span>',
            '    </div>',
            '    <button type="button" class="internal-chat-close" title="Fechar"><i class="fa fa-xmark"></i></button>',
            '  </header>',
            '  <div class="internal-chat-body" id="' + selectors.body + '">',
            '    <div class="internal-chat-empty">Carregando mensagens...</div>',
            '  </div>',
            '  <div class="internal-chat-status" id="' + selectors.status + '"></div>',
            '  <footer class="internal-chat-compose">',
            '    <textarea id="' + selectors.input + '" rows="2" maxlength="2000" placeholder="Digite e pressione Enter"></textarea>',
            '    <div class="internal-chat-actions">',
            '      <button type="button" class="internal-chat-clear" title="Limpar historico"><i class="fa fa-eraser"></i></button>',
            '      <button type="button" class="internal-chat-send" title="Enviar"><i class="fa fa-paper-plane"></i></button>',
            '    </div>',
            '  </footer>',
            '</section>',
        ].join('');
        document.body.appendChild(wrapper);

        document.getElementById(selectors.button).addEventListener('click', togglePanel);
        wrapper.querySelector('.internal-chat-close').addEventListener('click', closePanel);
        wrapper.querySelector('.internal-chat-send').addEventListener('click', sendMessage);
        wrapper.querySelector('.internal-chat-clear').addEventListener('click', clearHistory);
        document.getElementById(selectors.input).addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });
    }

    function startPolling() {
        if (state.polling) return;
        state.polling = setInterval(function() {
            loadMessages(!state.loaded);
        }, 5000);
    }

    window.MedsoftInternalChat = {
        init: function() {
            if (!hasAuthenticatedSession()) return;
            if (document.querySelector('.medsoft-internal-chat')) return;
            buildWidget();
            loadMe();
            loadMessages(true);
            startPolling();
        },
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.MedsoftInternalChat.init);
    } else {
        window.MedsoftInternalChat.init();
    }
})();
