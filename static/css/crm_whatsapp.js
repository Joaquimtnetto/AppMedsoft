(function () {
    function headers() {
        return {'Content-Type': 'application/json'};
    }

    function formatDate(value, includeDate) {
        if (!value) return '';
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat('pt-BR', includeDate
            ? {dateStyle: 'short', timeStyle: 'short'}
            : {hour: '2-digit', minute: '2-digit'}).format(date);
    }

    function previewText(item) {
        if (item.ultima_mensagem) return item.ultima_mensagem.replace(/\s+/g, ' ').trim();
        return item.registro_legado ? 'Mensagem antiga sem conteudo armazenado' : 'Sem conteudo';
    }

    function digits(value) {
        return String(value || '').replace(/\D+/g, '');
    }

    function phoneVariants(value) {
        var raw = digits(value);
        var variants = [];
        function add(item) {
            if (item && variants.indexOf(item) === -1) variants.push(item);
        }
        add(raw);
        var local = raw.startsWith('55') ? raw.slice(2) : raw;
        add(local);
        add('55' + local);
        if (local.length === 11 && local.charAt(2) === '9') {
            var withoutNine = local.slice(0, 2) + local.slice(3);
            add(withoutNine);
            add('55' + withoutNine);
        }
        if (local.length === 10) {
            var withNine = local.slice(0, 2) + '9' + local.slice(2);
            add(withNine);
            add('55' + withNine);
        }
        return variants;
    }

    function samePhone(left, right) {
        if (String(left || '') === String(right || '')) return true;
        if (String(left || '').indexOf('@g.us') >= 0 || String(right || '').indexOf('@g.us') >= 0) return false;
        var leftVariants = phoneVariants(left);
        var rightVariants = phoneVariants(right);
        return leftVariants.some(function(a) {
            return rightVariants.some(function(b) { return a === b || a.endsWith(b) || b.endsWith(a); });
        });
    }

    function messageTime(message) {
        if (message.timestamp) return Number(message.timestamp) * 1000;
        var date = new Date(message.datahora || message.created_at || '');
        return Number.isNaN(date.getTime()) ? 0 : date.getTime();
    }

    function renderMessageBubble(message) {
        var incoming = message.direcao === 'entrada' || message.direction === 'incoming';
        var failed = !incoming && (message.enviado === 'Nao' || message.enviado === 'N\u00e3o');
        var content = message.conteudo || message.text || 'Mensagem antiga: o conteudo original nao foi armazenado.';
        var when = message.timestamp
            ? new Date(Number(message.timestamp) * 1000).toISOString()
            : (message.datahora || message.created_at || '');
        return '<article class="crm-chat-message ' + (incoming ? 'is-incoming' : 'is-outgoing') + (failed ? ' is-error' : '') + '">' +
            '<div class="crm-chat-message-text">' + CrudUI.escapeHtml(content) + '</div>' +
            '<div class="crm-chat-message-meta"><time>' + CrudUI.escapeHtml(formatDate(when, true)) + '</time><span>' +
            (incoming ? '<i class="fa fa-reply"></i> Recebida' : (failed ? '<i class="fa fa-circle-xmark"></i> Falha' : '<i class="fa fa-check-double"></i> Enviada')) +
            '</span></div>' +
            (failed && message.motivoerro ? '<div class="crm-chat-error">' + CrudUI.escapeHtml(message.motivoerro) + '</div>' : '') +
            '</article>';
    }

    function displayContactName(item) {
        if (!item) return '';
        if (item.name && item.name !== item.phone) return item.name;
        return item.isGroup ? 'Grupo ' + String(item.phone || '').slice(0, 12) : (item.phone || '');
    }

    function contactId(item) {
        return item && (item.jid || item.phone || '');
    }

    function localKey(phone) {
        return 'medsoft.whatsapp.chat.' + digits(phone).slice(-11);
    }

    function loadLocalMessages(phone) {
        try {
            return JSON.parse(window.localStorage.getItem(localKey(phone)) || '[]');
        } catch (error) {
            return [];
        }
    }

    function saveLocalMessages(phone, messages) {
        try {
            window.localStorage.setItem(localKey(phone), JSON.stringify(messages.slice(-200)));
        } catch (error) {}
    }

    function addLocalMessage(phone, message) {
        var messages = loadLocalMessages(phone);
        messages.push(message);
        saveLocalMessages(phone, messages);
    }

    function messageFingerprint(message) {
        return [
            message.direcao || message.direction || 'saida',
            digits(message.destino || message.phone || ''),
            String(message.conteudo || message.text || '').trim(),
            Math.floor(messageTime(message) / 60000)
        ].join('|');
    }

    function uniqueMessages(messages) {
        var seen = new Set();
        return messages.filter(function(message) {
            var idKey = message.id || message.message_id || '';
            var contentKey = messageFingerprint(message);
            if ((idKey && seen.has('id:' + idKey)) || seen.has('content:' + contentKey)) return false;
            if (idKey) seen.add('id:' + idKey);
            seen.add('content:' + contentKey);
            return true;
        });
    }

    function init() {
        var page = document.getElementById('crm-whatsapp-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var list = document.getElementById('crm-conversations-list');
        var chat = document.getElementById('crm-chat-panel');
        var search = document.getElementById('crm-conversations-search');
        var conversations = [];
        var selectedDestination = '';
        var selectedPatient = null;

        async function loadConnection() {
            var badge = document.getElementById('crm-connected-phone');
            try {
                var status = await CrudUI.request('/api/whatsapp/connection', {method:'GET', headers:headers()});
                badge.classList.toggle('is-offline', !status.connected);
                badge.innerHTML = status.connected
                    ? '<i class="fa fa-phone"></i> ' + CrudUI.escapeHtml(status.phone || 'WhatsApp conectado')
                    : '<i class="fa fa-circle-exclamation"></i> WhatsApp desconectado';
            } catch (error) {
                badge.classList.add('is-offline');
                badge.innerHTML = '<i class="fa fa-circle-exclamation"></i> Servico indisponivel';
            }
        }

        function selectedPatientFromTable() {
            var checked = page.querySelector('[data-crm-patient-selector] [data-patient-check]:checked');
            return checked ? {name: checked.dataset.patientName || '', phone: checked.dataset.patientPhone || ''} : null;
        }

        function showSelectedPatient(patient) {
            selectedPatient = patient || null;
            var phone = patient && patient.phone ? patient.phone : '';
            document.getElementById('crm-direct-phone').value = phone;
            var display = document.getElementById('crm-direct-selected');
            display.innerHTML = phone
                ? '<i class="fa fa-user"></i><div><strong>' + CrudUI.escapeHtml(patient.name || 'Paciente selecionado') + '</strong><span>' + CrudUI.escapeHtml(phone) + '</span></div>'
                : '<i class="fa fa-user"></i><div><strong>Selecione um paciente na lista acima</strong><span>O telefone cadastrado sera utilizado automaticamente.</span></div>';
        }

        function openDirectConversation(patient) {
            showSelectedPatient(patient);
            activateTab('direct');
            loadDirectConversation();
        }

        function conversationToDirect(conversation, destination) {
            var phone = destination || (conversation && conversation.destino) || '';
            return {
                name: (conversation && (conversation.paciente || conversation.nome || conversation.name)) || phone,
                phone: phone
            };
        }

        function activateTab(name) {
            page.querySelectorAll('[data-crm-whatsapp-tab]').forEach(function (button) { button.classList.toggle('is-active', button.dataset.crmWhatsappTab === name); });
            page.querySelectorAll('[data-crm-whatsapp-panel]').forEach(function (panel) { panel.classList.toggle('is-active', panel.dataset.crmWhatsappPanel === name); });
            if (name === 'contacts') loadContacts();
            if (name === 'direct') {
                var current = selectedPatient || selectedPatientFromTable() || (window.MedsoftSelectedWhatsappPatients || [])[0];
                if (current) showSelectedPatient(current);
            }
        }

        async function loadContactsData() {
            var data = await CrudUI.request('/api/whatsapp/contacts', {method: 'GET', headers: headers()});
            return data.contacts || [];
        }

        async function loadContacts() {
            var container = document.getElementById('crm-whatsapp-contacts-list');
            var button = document.getElementById('crm-whatsapp-refresh-contacts');
            container.innerHTML = '<div class="crud-loading">Carregando contatos...</div>';
            if (button) button.disabled = true;
            try {
                var contacts = await loadContactsData();
                container.dataset.contacts = JSON.stringify(contacts);
                renderContacts(contacts);
            } catch (error) {
                container.innerHTML = '<div class="crud-error">Nao foi possivel carregar os contatos. Reinicie o servico Baileys e confirme sua conexao.</div>';
            } finally {
                if (button) button.disabled = false;
            }
        }

        function renderContacts(contacts) {
            var container = document.getElementById('crm-whatsapp-contacts-list');
            var term = document.getElementById('crm-whatsapp-contact-search').value.trim().toLowerCase();
            contacts = contacts.filter(function(item) { return !term || (item.name + ' ' + item.phone).toLowerCase().indexOf(term) >= 0; });
            container.innerHTML = contacts.length ? contacts.map(function(item) {
                var icon = item.isGroup ? 'fa fa-users' : 'fa-brands fa-whatsapp';
                return '<button type="button" class="crm-phone-contact" data-contact-phone="' + CrudUI.escapeHtml(item.jid || item.phone) + '"><i class="' + icon + '"></i><span><strong>' + CrudUI.escapeHtml(displayContactName(item)) + '</strong><small>' + CrudUI.escapeHtml(item.isGroup ? 'Grupo WhatsApp' : item.phone) + '</small></span></button>';
            }).join('') : '<div class="crud-empty">Nenhum contato sincronizado pelo WhatsApp. Clique em Atualizar contatos.</div>';
        }

        async function loadDirectConversation() {
            var phone = document.getElementById('crm-direct-phone').value.trim();
            var history = document.getElementById('crm-direct-history');
            var alerts = document.getElementById('crm-direct-incoming-alerts');
            if (!phone) {
                history.innerHTML = '<div class="crud-empty">Selecione um paciente na lista acima para consultar as mensagens.</div>';
                loadIncomingList();
                return;
            }
            try {
                var data = await CrudUI.request('/api/crm/whatsapp/historico', {
                    method: 'POST', headers: headers(), body: JSON.stringify({destino: phone})
                });
                var receivedData = await CrudUI.request('/api/whatsapp/received?phone=' + encodeURIComponent(phone), {method:'GET', headers:headers()});
                var received = receivedData.messages || [];
                renderIncomingList(receivedData.messages || []);
                var messages = (data.mensagens || []).concat(received.map(function(item) {
                    return {
                        id: item.id,
                        direcao: item.direction === 'outgoing' ? 'saida' : 'entrada',
                        conteudo: item.text,
                        timestamp: item.timestamp,
                        destino: item.phone,
                        phone: item.phone,
                        type: item.type
                    };
                })).concat(loadLocalMessages(phone));
                messages = uniqueMessages(messages);
                messages.sort(function(left, right) { return messageTime(left) - messageTime(right); });
                history.innerHTML = messages.length ? messages.map(renderMessageBubble).join('') : '<div class="crud-empty">Nenhuma mensagem nesta conversa.</div>';
                history.scrollTop = history.scrollHeight;
            } catch(error) { if (alerts) alerts.innerHTML = ''; history.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message) + '</div>'; }
        }

        async function loadIncomingList() {
            try {
                var receivedData = await CrudUI.request('/api/whatsapp/received', {method:'GET', headers:headers()});
                renderIncomingList(receivedData.messages || []);
            } catch (error) {
                var alerts = document.getElementById('crm-direct-incoming-alerts');
                if (alerts) alerts.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message || 'Erro ao carregar recebidas.') + '</div>';
            }
        }

        function refreshDirect() {
            var phone = document.getElementById('crm-direct-phone').value.trim();
            if (phone) {
                loadDirectConversation();
            } else {
                loadIncomingList();
            }
        }

        function renderIncomingList(items) {
            var alerts = document.getElementById('crm-direct-incoming-alerts');
            if (!alerts) return;
            var incoming = (items || []).filter(function(item) { return item.direction === 'incoming'; })
                .sort(function(left, right) { return messageTime(right) - messageTime(left); })
                .slice(0, 8);
            alerts.innerHTML = '<div class="crm-incoming-notice"><strong>Mensagens recebidas</strong>' +
                (incoming.length ? incoming.map(function(item) {
                    return '<button type="button" data-incoming-phone="' + CrudUI.escapeHtml(contactId(item)) + '" data-incoming-name="' + CrudUI.escapeHtml(displayContactName(item)) + '">' +
                        '<span>' + CrudUI.escapeHtml(displayContactName(item)) + '</span><small>' + CrudUI.escapeHtml(item.text) + ' - ' + CrudUI.escapeHtml(formatDate(new Date(Number(item.timestamp) * 1000).toISOString(), false)) + '</small></button>';
                }).join('') : '<div class="crud-empty">Nenhuma recebida capturada pelo Baileys.</div>') +
                '</div>';
        }

        async function sendDirect() {
            var phone = document.getElementById('crm-direct-phone').value.trim();
            var message = document.getElementById('crm-direct-message').value.trim();
            if (!phone) { CrudUI.notify('Selecione um paciente com telefone na lista acima.', 'error'); return; }
            if (!message) { CrudUI.notify('Digite a mensagem.', 'error'); return; }
            try {
                addLocalMessage(phone, {direcao: 'saida', conteudo: message, created_at: new Date().toISOString(), destino: phone, enviado: 'Sim'});
                document.getElementById('crm-direct-message').value = '';
                await loadDirectConversation();
                await CrudUI.request('/api/whatsapp/send', {method:'POST',headers:headers(),body:JSON.stringify({phone:phone,message:message})});
                CrudUI.notify('Mensagem enviada pelo Whatzap.');
                load();
                loadDirectConversation();
            } catch(error) { CrudUI.notify('Falha no envio: ' + (error.message || 'erro nao identificado.'), 'error'); }
        }

        function renderConversations() {
            var term = search.value.trim().toLocaleLowerCase('pt-BR');
            var filtered = conversations.filter(function (item) {
                return !term || ((item.paciente || '') + ' ' + (item.destino || ''))
                    .toLocaleLowerCase('pt-BR').indexOf(term) !== -1;
            });
            if (!filtered.length) {
                list.innerHTML = '<div class="crud-empty">Nenhuma conversa encontrada.</div>';
                return;
            }
            list.innerHTML = filtered.map(function (item) {
                var active = samePhone(item.destino, selectedDestination) ? ' is-active' : '';
                var error = (item.enviado === 'Nao' || item.enviado === 'N\u00e3o') ? '<i class="fa fa-circle-exclamation crm-conversation-error"></i>' : '';
                var counter = Number(item.total || 0) > 0 ? CrudUI.escapeHtml(item.total) : '';
                return '<button type="button" class="crm-conversation' + active + '" data-destination="' +
                    CrudUI.escapeHtml(item.destino) + '"><span class="crm-conversation-avatar"><i class="fa fa-user"></i></span>' +
                    '<span class="crm-conversation-body"><span class="crm-conversation-title">' +
                    CrudUI.escapeHtml(item.paciente || item.destino || 'Sem destinatario') + '</span>' +
                    '<span class="crm-conversation-preview">' + CrudUI.escapeHtml(previewText(item)) + '</span></span>' +
                    '<span class="crm-conversation-side"><time>' + CrudUI.escapeHtml(formatDate(item.ultima_data, true)) +
                    '</time><span>' + error + counter + '</span></span></button>';
            }).join('');
        }

        async function openConversation(destination, continueChat) {
            selectedDestination = destination;
            renderConversations();
            var conversation = conversations.find(function (item) { return samePhone(item.destino, destination); }) || {};
            if (continueChat) {
                openDirectConversation(conversationToDirect(conversation, destination));
                return;
            }
            chat.innerHTML = '<div class="crud-loading">Carregando historico...</div>';
            try {
                var data = await CrudUI.request('/api/crm/whatsapp/historico', {
                    method: 'POST', headers: headers(), body: JSON.stringify({destino: destination})
                });
                var messages = data.mensagens || [];
                messages.sort(function(left, right) { return messageTime(left) - messageTime(right); });
                var bubbles = messages.map(renderMessageBubble).join('') || '<div class="crud-empty">Nenhuma mensagem gravada no historico do MedSoft.</div>';
                chat.innerHTML = '<header class="crm-chat-header"><span class="crm-conversation-avatar"><i class="fa fa-user"></i></span>' +
                    '<div><h3>' + CrudUI.escapeHtml(conversation.paciente || destination) + '</h3><p>' +
                    CrudUI.escapeHtml(destination) + '</p></div></header><div class="crm-chat-history" id="crm-chat-history">' +
                    bubbles + '</div>';
                var history = document.getElementById('crm-chat-history');
                history.scrollTop = history.scrollHeight;
            } catch (error) {
                chat.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message || 'Erro ao carregar historico.') + '</div>';
            }
        }

        async function load() {
            loadConnection();
            list.innerHTML = '<div class="crud-loading">Carregando conversas...</div>';
            try {
                var data = await CrudUI.request('/api/crm/whatsapp/conversas', {method: 'GET', headers: headers()});
                conversations = data.conversas || [];
                renderConversations();
                if (selectedDestination && conversations.some(function (item) { return samePhone(item.destino, selectedDestination); })) {
                    openConversation(selectedDestination);
                }
            } catch (error) {
                list.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message || 'Erro ao carregar conversas.') + '</div>';
            }
        }

        list.addEventListener('click', function (event) {
            var button = event.target.closest('[data-destination]');
            if (button) openConversation(button.dataset.destination, true);
        });
        search.addEventListener('input', renderConversations);
        document.getElementById('crm-whatsapp-refresh').onclick = load;
        page.querySelectorAll('[data-crm-whatsapp-tab]').forEach(function(button) { button.onclick = function() { activateTab(button.dataset.crmWhatsappTab); }; });
        document.getElementById('crm-whatsapp-refresh-contacts').onclick = loadContacts;
        document.getElementById('crm-whatsapp-contact-search').oninput = function() { var value=document.getElementById('crm-whatsapp-contacts-list').dataset.contacts; if(value) renderContacts(JSON.parse(value)); };
        document.getElementById('crm-whatsapp-contacts-list').onclick = function(event) { var button=event.target.closest('[data-contact-phone]'); if(button){openDirectConversation({name:button.innerText.split('\n')[0],phone:button.dataset.contactPhone});} };
        document.getElementById('crm-direct-history').addEventListener('click', function(event) {
            var button = event.target.closest('[data-incoming-phone]');
            if (!button) return;
            openDirectConversation({name: button.dataset.incomingName || button.dataset.incomingPhone, phone: button.dataset.incomingPhone});
        });
        document.getElementById('crm-direct-incoming-alerts').addEventListener('click', function(event) {
            var button = event.target.closest('[data-incoming-phone]');
            if (!button) return;
            openDirectConversation({name: button.dataset.incomingName || button.dataset.incomingPhone, phone: button.dataset.incomingPhone});
        });
        page.addEventListener('crm:patient-selection', function(event) {
            if (event.detail.channel !== 'whatsapp') return;
            showSelectedPatient((event.detail.patients || [])[0] || null);
            loadDirectConversation();
        });
        document.getElementById('crm-start-selected-chat').onclick = function() {
            var current = selectedPatientFromTable() || selectedPatient || (window.MedsoftSelectedWhatsappPatients || [])[0];
            if (!current || !current.phone) { CrudUI.notify('Selecione uma pessoa com telefone.', 'error'); return; }
            openDirectConversation(current);
        };
        document.getElementById('crm-direct-message').addEventListener('keydown', function(event) {
            if (event.key !== 'Enter' || event.shiftKey) return;
            event.preventDefault();
            sendDirect();
        });
        var directSendButton = document.getElementById('crm-direct-send');
        if (directSendButton) directSendButton.onclick = sendDirect;
        document.getElementById('crm-direct-refresh').onclick = refreshDirect;
        load();
        loadIncomingList();
        window.setInterval(function() {
            loadConnection();
            if (selectedDestination) openConversation(selectedDestination);
            if (page.querySelector('[data-crm-whatsapp-panel="direct"]').classList.contains('is-active')) loadDirectConversation();
            else loadIncomingList();
        }, 15000);
    }

    window.CrmWhatsapp = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
