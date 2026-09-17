(function () {
    function headers() {
        return {
            'Content-Type': 'application/json',
            'X-DB-PATH': localStorage.getItem('db_path') || ''
        };
    }

    function api(method, body) {
        return CrudUI.request('/api/configuracao', {
            method: method,
            headers: headers(),
            body: body ? JSON.stringify(body) : undefined
        });
    }

    function testEmail(body) {
        return CrudUI.request('/api/configuracao/testar-email', {
            method: 'POST',
            headers: headers(),
            body: JSON.stringify(body)
        });
    }

    function whatsappConnection(method, action) {
        return CrudUI.request('/api/whatsapp/' + (action || 'connection'), {
            method: method || 'GET',
            headers: headers()
        });
    }

    function fieldValue(form, name, fallback) {
        var field = form.elements[name];
        if (!field) return fallback == null ? '' : fallback;
        if (field.type === 'checkbox') return field.checked;
        return field.value;
    }

    function setFieldValue(form, name, value) {
        var field = form.elements[name];
        if (!field) return;
        if (field.type === 'checkbox') field.checked = !!value;
        else field.value = value || '';
    }

    function setTextoOptions(form, options) {
        var page = document.getElementById('configuracao-page');
        var expectedType = page && page.dataset.configuracaoTela === 'whatsapp' ? 'Z' : 'E';
        var channelOptions = (options || []).filter(function (option) {
            return !option.tipo || option.tipo === expectedType;
        });
        form.querySelectorAll('.configuracao-texto-select').forEach(function (select) {
            var current = select.value;
            select.innerHTML = '<option value="">Selecione</option>' + channelOptions.map(function (option) {
                return '<option value="' + CrudUI.escapeHtml(option.value) + '">' +
                    CrudUI.escapeHtml(option.label) + '</option>';
            }).join('');
            select.value = current;
        });
    }

    function setFormValues(form, values) {
        Object.keys(values || {}).forEach(function (name) {
            var field = form.elements[name];
            if (!field) return;
            if (field.type === 'checkbox') field.checked = !!values[name];
            else if (name !== 'smtp_senha' && name !== 'whatsapp_token') field.value = values[name] || '';
        });
        if (form.elements.smtp_senha) {
            form.elements.smtp_senha.placeholder = values.possui_smtp_senha
                ? 'Senha já cadastrada — deixe vazio para manter' : 'Informe a senha';
        }
        if (form.elements.whatsapp_token) {
            form.elements.whatsapp_token.placeholder = values.possui_whatsapp_token
                ? 'Token já cadastrado — deixe vazio para manter' : 'Informe o token';
        }
        if (form.elements.whatsapp_modo) {
            form.elements.whatsapp_modo.value = values.whatzapsimplificado
                ? 'simplificado' : 'business';
        }
        updateWhatsappMode(form);
    }

    function updateWhatsappMode(form) {
        if (!form.elements.whatsapp_modo) return;
        var simplified = form.elements.whatsapp_modo.value === 'simplificado';
        form.querySelectorAll('.whatsapp-business-only').forEach(function (field) {
            field.hidden = simplified;
        });
        var note = form.querySelector('.configuracao-simplified-note');
        if (note) note.hidden = !simplified;
    }

    function formValues(form, currentValues) {
        var base = Object.assign({
            smtp_host: '',
            smtp_porta: '',
            smtp_usuario: '',
            smtp_senha: '',
            smtp_remetente: '',
            smtp_tls: true,
            smtp_ssl: false,
            whatsapp_remetente: '5521986496127',
            whatsapp_phone_number_id: '',
            whatsapp_token: '',
            whatsapp_api_version: '',
            whatsapp_template: '',
            whatsapp_idioma: 'pt_BR',
            whatzapsimplificado: true,
            autlembraagendaemail: '',
            autlembraretagendaemail: '',
            autlembraniveremail: '',
            autlembraeventemail: '',
            textolembraagendaemail: '',
            textolembraretagendaemail: '',
            textolembraniveremail: '',
            textolembraeventemail: '',
            autlembraagendawhatzap: '',
            autlembraretagendawhatzap: '',
            autlembraniverwahtzap: '',
            autlembraeventowahtzap: '',
            textolembraagendawahtzap: '',
            textolembraretagendawahtzap: '',
            textolembraniverwahtzap: '',
            textolembraeventwahtzap: ''
        }, currentValues || {});
        return {
            smtp_host: fieldValue(form, 'smtp_host', base.smtp_host),
            smtp_porta: fieldValue(form, 'smtp_porta', base.smtp_porta),
            smtp_usuario: fieldValue(form, 'smtp_usuario', base.smtp_usuario),
            smtp_senha: fieldValue(form, 'smtp_senha', ''),
            smtp_remetente: fieldValue(form, 'smtp_remetente', base.smtp_remetente),
            smtp_tls: fieldValue(form, 'smtp_tls', base.smtp_tls),
            smtp_ssl: fieldValue(form, 'smtp_ssl', base.smtp_ssl),
            whatsapp_remetente: fieldValue(form, 'whatsapp_remetente', base.whatsapp_remetente),
            whatsapp_phone_number_id: fieldValue(form, 'whatsapp_phone_number_id', base.whatsapp_phone_number_id),
            whatsapp_token: fieldValue(form, 'whatsapp_token', ''),
            whatsapp_api_version: fieldValue(form, 'whatsapp_api_version', base.whatsapp_api_version),
            whatsapp_template: fieldValue(form, 'whatsapp_template', base.whatsapp_template),
            whatsapp_idioma: fieldValue(form, 'whatsapp_idioma', base.whatsapp_idioma),
            whatzapsimplificado: form.elements.whatsapp_modo
                ? form.elements.whatsapp_modo.value === 'simplificado'
                : !!base.whatzapsimplificado,
            autlembraagendaemail: fieldValue(form, 'autlembraagendaemail', base.autlembraagendaemail),
            autlembraretagendaemail: fieldValue(form, 'autlembraretagendaemail', base.autlembraretagendaemail),
            autlembraniveremail: fieldValue(form, 'autlembraniveremail', base.autlembraniveremail),
            autlembraeventemail: fieldValue(form, 'autlembraeventemail', base.autlembraeventemail),
            textolembraagendaemail: fieldValue(form, 'textolembraagendaemail', base.textolembraagendaemail),
            textolembraretagendaemail: fieldValue(form, 'textolembraretagendaemail', base.textolembraretagendaemail),
            textolembraniveremail: fieldValue(form, 'textolembraniveremail', base.textolembraniveremail),
            textolembraeventemail: fieldValue(form, 'textolembraeventemail', base.textolembraeventemail),
            autlembraagendawhatzap: fieldValue(form, 'autlembraagendawhatzap', base.autlembraagendawhatzap),
            autlembraretagendawhatzap: fieldValue(form, 'autlembraretagendawhatzap', base.autlembraretagendawhatzap),
            autlembraniverwahtzap: fieldValue(form, 'autlembraniverwahtzap', base.autlembraniverwahtzap),
            autlembraeventowahtzap: fieldValue(form, 'autlembraeventowahtzap', base.autlembraeventowahtzap),
            textolembraagendawahtzap: fieldValue(form, 'textolembraagendawahtzap', base.textolembraagendawahtzap),
            textolembraretagendawahtzap: fieldValue(form, 'textolembraretagendawahtzap', base.textolembraretagendawahtzap),
            textolembraniverwahtzap: fieldValue(form, 'textolembraniverwahtzap', base.textolembraniverwahtzap),
            textolembraeventwahtzap: fieldValue(form, 'textolembraeventwahtzap', base.textolembraeventwahtzap)
        };
    }

    async function init() {
        var page = document.getElementById('configuracao-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var form = document.getElementById('configuracao-form');
        var status = document.getElementById('configuracao-status');
        if (!form || !status || !window.CrudUI) return;
        var submitButton = form.querySelector('[type="submit"]');
        var passwordInput = form.elements.smtp_senha;
        var passwordToggle = document.getElementById('toggle-smtp-senha');
        var testEmailButton = document.getElementById('configuracao-test-email');
        var testEmailResult = document.getElementById('configuracao-email-test-result');
        var whatsappConnectionBox = document.getElementById('whatsapp-connection');
        var whatsappMessage = document.getElementById('whatsapp-connection-message');
        var whatsappPhone = document.getElementById('whatsapp-connected-phone');
        var whatsappRefresh = document.getElementById('whatsapp-refresh-qr');
        var whatsappRestart = document.getElementById('whatsapp-restart-service');
        var whatsappDisconnect = document.getElementById('whatsapp-disconnect');
        var whatsappOpenWeb = document.getElementById('whatsapp-open-web');
        var whatsappPoll = null;
        var whatsappBusy = false;
        var currentValues = {};

        function renderWhatsappConnection(data) {
            if (!whatsappConnectionBox || !page.isConnected) return;
            var visual = whatsappConnectionBox.querySelector('.whatsapp-connection-visual');
            var connected = !!data.connected;
            whatsappConnectionBox.classList.toggle('is-connected', connected);
            whatsappMessage.textContent = data.message || (connected ? 'WhatsApp conectado.' :
                (data.qr ? 'Aguardando leitura do QR Code. O WhatsApp ainda está desconectado.' : 'Preparando conexão...'));
            if (whatsappPhone) {
                whatsappPhone.hidden = !connected || !data.phone;
                whatsappPhone.innerHTML = data.phone
                    ? '<i class="fa fa-phone"></i> Número conectado: <strong>' +
                        CrudUI.escapeHtml(data.phone) + '</strong>'
                    : '';
            }
            whatsappDisconnect.hidden = !connected;
            whatsappRefresh.hidden = connected;
            if (connected) {
                visual.innerHTML = '<div class="whatsapp-connected-icon"><i class="fa-brands fa-whatsapp"></i></div>';
            } else if (data.qr && /^data:image\/png;base64,/.test(data.qr)) {
                visual.innerHTML = '<img class="whatsapp-qr-image" alt="QR Code para conectar o WhatsApp">';
                visual.querySelector('img').src = data.qr;
                whatsappMessage.textContent = 'Aguardando leitura do QR Code. O WhatsApp ainda está desconectado.';
            } else {
                visual.innerHTML = '<div class="crud-loading">' + CrudUI.escapeHtml(data.message || 'Preparando QR Code...') + '</div>';
            }
        }

        async function loadWhatsappConnection() {
            if (!form.elements.whatsapp_modo || form.elements.whatsapp_modo.value !== 'simplificado') return;
            if (whatsappBusy) return;
            if (!whatsappPoll && page.isConnected) {
                whatsappPoll = window.setInterval(function () {
                    if (!page.isConnected) {
                        window.clearInterval(whatsappPoll);
                        whatsappPoll = null;
                        return;
                    }
                    loadWhatsappConnection();
                }, 5000);
            }
            try {
                renderWhatsappConnection(await whatsappConnection('GET'));
            } catch (error) {
                renderWhatsappConnection({message: error.message || 'Não foi possível carregar o QR Code.'});
            }
        }

        async function recoverWhatsappConnection() {
            try {
                var current = await whatsappConnection('GET');
                if (current && (current.qr || current.connected || ['starting', 'qr', 'reconnecting'].indexOf(current.status) !== -1)) {
                    renderWhatsappConnection(current);
                    return true;
                }
            } catch (ignored) {
                // Mantém o erro original, que é mais útil para o usuário.
            }
            return false;
        }

        if (passwordToggle && passwordInput) passwordToggle.onclick = function () {
            var showing = passwordInput.type === 'text';
            passwordInput.type = showing ? 'password' : 'text';
            passwordToggle.title = showing ? 'Exibir senha' : 'Ocultar senha';
            passwordToggle.setAttribute('aria-label', passwordToggle.title);
            passwordToggle.setAttribute('aria-pressed', String(!showing));
            passwordToggle.querySelector('i').className = showing
                ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
            passwordInput.focus();
        };

        if (form.elements.smtp_tls) form.elements.smtp_tls.onchange = function () {
            if (this.checked && form.elements.smtp_ssl) form.elements.smtp_ssl.checked = false;
        };
        if (form.elements.smtp_ssl) form.elements.smtp_ssl.onchange = function () {
            if (this.checked && form.elements.smtp_tls) form.elements.smtp_tls.checked = false;
        };
        if (form.elements.whatsapp_modo) {
            Array.from(form.elements.whatsapp_modo).forEach(function (option) {
                option.onchange = function () {
                    updateWhatsappMode(form);
                    if (this.value === 'simplificado') loadWhatsappConnection();
                };
            });
        }

        if (whatsappRefresh) whatsappRefresh.onclick = async function () {
            if (whatsappBusy) return;
            whatsappBusy = true;
            whatsappRefresh.disabled = true;
            whatsappMessage.textContent = 'Gerando um novo QR Code...';
            try {
                await whatsappConnection('POST', 'reset');
                renderWhatsappConnection({message: 'Preparando novo QR Code...'});
                whatsappBusy = false;
                await loadWhatsappConnection();
            } catch (error) {
                if (!await recoverWhatsappConnection()) {
                    CrudUI.notify(error.message || 'Não foi possível gerar um novo QR Code.', 'error');
                    renderWhatsappConnection({message: error.message || 'Não foi possível gerar um novo QR Code.'});
                }
            } finally {
                whatsappBusy = false;
                whatsappRefresh.disabled = false;
            }
        };
        if (whatsappRestart) whatsappRestart.onclick = async function () {
            if (whatsappBusy) return;
            whatsappBusy = true;
            whatsappRestart.disabled = true;
            whatsappMessage.textContent = 'Reiniciando o serviço WhatsApp...';
            try {
                var result = await whatsappConnection('POST', 'service/restart');
                CrudUI.notify(result.message || 'Serviço WhatsApp reiniciado.', 'success');
                renderWhatsappConnection({message: 'Serviço iniciado. Preparando QR Code...'});
                whatsappBusy = false;
                await loadWhatsappConnection();
            } catch (error) {
                if (!await recoverWhatsappConnection()) {
                    CrudUI.notify(error.message || 'Não foi possível reiniciar o serviço WhatsApp.', 'error');
                    renderWhatsappConnection({message: error.message || 'Não foi possível reiniciar o serviço WhatsApp.'});
                }
            } finally {
                whatsappBusy = false;
                whatsappRestart.disabled = false;
            }
        };
        if (whatsappDisconnect) whatsappDisconnect.onclick = async function () {
            if (whatsappBusy) return;
            whatsappBusy = true;
            whatsappDisconnect.disabled = true;
            try {
                renderWhatsappConnection(await whatsappConnection('POST', 'disconnect'));
                await loadWhatsappConnection();
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível desconectar o WhatsApp.', 'error');
            } finally {
                whatsappBusy = false;
                whatsappDisconnect.disabled = false;
            }
        };
        if (whatsappOpenWeb) whatsappOpenWeb.onclick = function () {
            var whatsappWindow = window.open('https://web.whatsapp.com/', '_blank', 'noopener,noreferrer');
            if (!whatsappWindow) {
                CrudUI.notify('O navegador bloqueou a abertura do WhatsApp Web.', 'error');
            }
        };

        if (testEmailButton) testEmailButton.onclick = async function () {
            testEmailButton.disabled = true;
            testEmailResult.innerHTML = '<div class="crud-loading">Testando conexão...</div>';
            try {
                var result = await testEmail(formValues(form, currentValues));
                var details = (result.responses || []).map(function (response) {
                    return '<small>' + CrudUI.escapeHtml(response) + '</small>';
                }).join('');
                testEmailResult.innerHTML = '<div class="crud-success">' +
                    CrudUI.escapeHtml(result.message) + details + '</div>';
            } catch (error) {
                testEmailResult.innerHTML = '<div class="crud-error">' +
                    CrudUI.escapeHtml(error.message || 'Falha ao testar a conexão SMTP.') + '</div>';
            } finally {
                testEmailButton.disabled = false;
            }
        };

        try {
            var data = await api('POST');
            currentValues = data.configuracao || {};
            setTextoOptions(form, data.textos || []);
            setFormValues(form, currentValues);
            if (form.elements.whatsapp_modo && form.elements.whatsapp_modo.value === 'simplificado') {
                loadWhatsappConnection();
            }
        } catch (error) {
            status.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message) + '</div>';
            if (submitButton) submitButton.disabled = true;
        }

        form.onsubmit = async function (event) {
            event.preventDefault();
            if (submitButton) submitButton.disabled = true;
            try {
                var result = await api('PUT', formValues(form, currentValues));
                setFieldValue(form, 'smtp_senha', '');
                setFieldValue(form, 'whatsapp_token', '');
                CrudUI.notify(result.message || 'Configurações salvas com sucesso.');
                var refreshed = await api('POST');
                currentValues = refreshed.configuracao || {};
                setTextoOptions(form, refreshed.textos || []);
                setFormValues(form, currentValues);
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível salvar as configurações.', 'error');
            } finally {
                if (submitButton) submitButton.disabled = false;
            }
        };
    }

    window.ConfiguracaoMedsoft = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
