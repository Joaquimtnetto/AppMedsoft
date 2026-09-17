(function () {
    var controller;
    var planoOptions = [{value: '', label: ''}];
    var profissionalOptions = [{value: '', label: ''}];
    var activeDictationStop = null;

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

    function searchField() {
        var field = document.getElementById('paciente-campo-busca');
        return field ? field.value : 'nome';
    }

    function isActive(item) {
        var value = item && item.ativo;
        if (value === false || value === 0) return false;
        return ['N', 'NAO', 'NÃO', 'FALSE', '0', 'INATIVO'].indexOf(
            String(value == null ? '' : value).trim().toUpperCase()
        ) === -1;
    }

    async function loadPlanOptions() {
        var data = await api('/api/planos', 'POST', {termo: ''});
        planoOptions = [{value: '', label: ''}].concat((data.planos || []).map(function (plano) {
            var nome = plano.nome || plano.id || '';
            return {value: nome, label: nome};
        }).filter(function (option) { return option.value; }));
    }

    async function loadProfissionalOptions() {
        var data = await api('/api/prof-saude', 'POST', {termo: ''});
        profissionalOptions = [{value: '', label: ''}].concat((data.profissionais || []).map(function (profissional) {
            var nome = profissional.nome || profissional.id || '';
            return {value: nome, label: nome};
        }).filter(function (option) { return option.value; }));
    }

    async function loadFormOptions() {
        await Promise.all([loadPlanOptions(), loadProfissionalOptions()]);
    }

    function professionalOptionsFor(item) {
        var currentValue = (item && item.nomed) || '';
        var options = profissionalOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function planOptionsFor(item) {
        var currentValue = (item && item.nomeplano1) || '';
        var options = planoOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function plan2OptionsFor(item) {
        var currentValue = (item && item.nomeplano2) || '';
        var options = planoOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function ufOptions() {
        return ['', 'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT',
            'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR',
            'SC', 'SP', 'SE', 'TO'].map(function (uf) {
            return {value: uf, label: uf};
        });
    }

    function setupCepLookup(backdrop) {
        var cep = backdrop.querySelector('[name="cep"]');
        if (!cep) return;

        async function lookupCep() {
            var digits = cep.value.replace(/\D/g, '');
            if (digits.length !== 8) return;
            try {
                var response = await fetch('https://viacep.com.br/ws/' + digits + '/json/');
                var data = await response.json();
                if (!response.ok || data.erro) throw new Error('CEP não encontrado.');
                var endereco = backdrop.querySelector('[name="endereco"]');
                var bairro = backdrop.querySelector('[name="bairro"]');
                var cidade = backdrop.querySelector('[name="cidade"]');
                var uf = backdrop.querySelector('[name="uf"]');
                if (endereco) endereco.value = data.logradouro || endereco.value;
                if (bairro) bairro.value = data.bairro || bairro.value;
                if (cidade) cidade.value = data.localidade || cidade.value;
                if (uf) uf.value = data.uf || uf.value;
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível consultar o CEP.', 'error');
            }
        }

        cep.addEventListener('blur', lookupCep);
        cep.addEventListener('change', lookupCep);
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'nome', label: 'Nome', value: item.nomecli || '', required: true, wide: true},
            {
                name: 'nomed',
                label: 'Prof. Saúde',
                type: 'select',
                value: item.nomed || '',
                options: professionalOptionsFor(item),
                wide: true
            },
            {
                name: 'telefone', label: 'Telefone', value: item.telefone || '', inputMode: 'numeric',
                mask: 'phone-br', placeholder: '(99)99999-9999', maxLength: 14
            },
            {
                name: 'plano',
                label: 'Plano',
                type: 'select',
                value: item.nomeplano1 || '',
                options: planOptionsFor(item)
            },
            {name: 'email', label: 'E-mail', value: item.email || '', type: 'email'},
            {
                name: 'ativo', label: 'Ativo', type: 'select',
                value: isActive(item) ? 'S' : 'N',
                options: [
                    {value: 'S', label: 'SIM'},
                    {value: 'N', label: 'NÃO'}
                ]
            },
            {name: 'nascimento', label: 'Nascimento', type: 'date', value: item.nascimento || '', complement: true},
            {
                name: 'sexo',
                label: 'Sexo',
                type: 'select',
                value: item.sexo || '',
                complement: true,
                options: [
                    {value: '', label: ''},
                    {value: 'M', label: 'M'},
                    {value: 'F', label: 'F'},
                    {value: 'O', label: 'O'}
                ]
            },
            {
                name: 'cpf', label: 'CPF', value: item.cpf || '', mask: 'cpf-br',
                placeholder: '999.999.999-99', maxLength: 14, inputMode: 'numeric', complement: true
            },
            {name: 'rg', label: 'RG', value: item.rg || '', maxLength: 25, complement: true},
            {
                name: 'cep', label: 'CEP', value: item.cep || '', mask: 'cep-br',
                placeholder: '99999-99', maxLength: 9, inputMode: 'numeric', complement: true
            },
            {
                name: 'uf',
                label: 'UF',
                type: 'select',
                value: item.uf || '',
                complement: true,
                options: ufOptions()
            },
            {name: 'endereco', label: 'Endereço', value: item.endereco || '', wide: true, complement: true},
            {name: 'cidade', label: 'Cidade', value: item.cidade || '', complement: true},
            {name: 'bairro', label: 'Bairro', value: item.bairro || '', complement: true},
            {
                name: 'estado_civil',
                label: 'Estado civil',
                type: 'select',
                value: item.estado_civil || '',
                complement: true,
                options: [
                    {value: '', label: ''},
                    {value: 'S', label: 'Solteiro'},
                    {value: 'C', label: 'Casado'},
                    {value: 'SE', label: 'Separado'},
                    {value: 'V', label: 'Viúvo'},
                    {value: 'O', label: 'Outros'}
                ]
            },
            {
                name: 'cor',
                label: 'Côr',
                type: 'select',
                value: item.cor || '',
                complement: true,
                options: [
                    {value: '', label: ''},
                    {value: 'B', label: 'Branco'},
                    {value: 'N', label: 'Negro'},
                    {value: 'P', label: 'Pardo'},
                    {value: 'I', label: 'Índio'},
                    {value: 'O', label: 'Outro'}
                ]
            },
            {name: 'foto', label: 'Foto', type: 'image', value: item.foto || '', wide: true, page: 3},
            {name: 'cont1', label: 'Nr do Plano', value: item.cont1 || '', maxLength: 40, page: 3},
            {name: 'validade_carteira1', label: 'Validade do plano', type: 'date', value: item.validade_carteira1 || '', page: 3},
            {name: 'nompai', label: 'Nome do Pai', value: item.nompai || '', maxLength: 30, page: 3},
            {name: 'nommae', label: 'Nome da Mãe', value: item.nommae || '', maxLength: 30, page: 3},
            {name: 'profcli', label: 'Profissão', value: item.profcli || '', maxLength: 25, page: 3},
            {
                name: 'natcli',
                label: 'Natural',
                type: 'select',
                value: item.natcli || '',
                options: ufOptions(),
                page: 3
            },
            {name: 'recom', label: 'Recomendação', value: item.recom || '', maxLength: 40, page: 3},
            {
                name: 'plano2',
                label: 'Plano 2',
                type: 'select',
                value: item.nomeplano2 || '',
                options: plan2OptionsFor(item),
                page: 3
            },
            {name: 'datult', label: 'Data da última consulta', type: 'date', value: item.datult || '', page: 3},
            {name: 'matricula', label: 'Matrícula', value: item.matricula || '', maxLength: 15, page: 3},
            {name: 'obs', label: 'Observação', value: item.obs || '', maxLength: 30, wide: true, page: 3},
        ];
    }

    function renderItem(item) {
        var profileViews = window.MedsoftProfileViews || {historico: true, exame: true};
        var historyButton = profileViews.historico ?
            '<button class="crud-button crud-button-secondary" data-crud-action="history" data-crud-id="' +
            item.codcli + '" title="Histórico do paciente"><i class="fa fa-history"></i>' +
            '<span class="crud-button-label"> Histórico</span></button>' : '';
        var examButton = profileViews.exame ?
            '<button class="crud-button crud-button-secondary" data-crud-action="exams" data-crud-id="' +
            item.codcli + '" title="Exames do paciente"><i class="fa fa-file-medical"></i>' +
            '<span class="crud-button-label"> Exames</span></button>' : '';
        return '<article class="crud-card">' +
            '<div class="crud-card-header"><span class="crud-title">' +
            CrudUI.escapeHtml(item.nomecli) +
            '</span><span class="crud-badge">#' + CrudUI.escapeHtml(item.codcli) + '</span></div><div class="crud-card-details">' +
            '<span><strong>Idade:</strong> ' + CrudUI.escapeHtml(item.idade || '') + '</span>' +
            '<span><strong>Telefone:</strong> ' + CrudUI.escapeHtml(item.telefone || '') + '</span>' +
            '<span><strong>Plano:</strong> ' + CrudUI.escapeHtml(item.nomeplano1 || '') + '</span>' +
            '<span><strong>Prof Saúde:</strong> ' + CrudUI.escapeHtml(item.nomed || '') + '</span>' +
            '<span><strong>Ativo:</strong> ' + (isActive(item) ? 'SIM' : 'NÃO') + '</span>' +
            '</div><div class="crud-actions">' +
            historyButton + examButton +
            '<button class="crud-button crud-button-secondary" data-crud-action="complement" data-crud-id="' +
            item.codcli + '" title="Cadastro 2/3 do paciente"><i class="fa fa-address-card"></i>' +
            '<span class="crud-button-label"> Cadastro 2/3</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-action="extra" data-crud-id="' +
            item.codcli + '" title="Cadastro 3/3 do paciente"><i class="fa fa-id-card"></i>' +
            '<span class="crud-button-label"> Cadastro 3/3</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.codcli +
            '" title="Alterar paciente"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.codcli +
            '" title="Excluir paciente"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function historicoCell(value, preserveLines) {
        var text = CrudUI.escapeHtml(value || '');
        return preserveLines ? text.replace(/\n/g, '<br>') : text;
    }

    function closeHistoricoModal() {
        var modal = document.getElementById('paciente-historico-modal');
        if (modal) {
            if (modal.cleanupSpeech) modal.cleanupSpeech();
            modal.remove();
        }
    }

    function closeReceitaModal() {
        var modal = document.getElementById('paciente-receita-modal');
        if (modal) {
            if (modal.cleanupDrag) modal.cleanupDrag();
            if (modal.cleanupSpeech) modal.cleanupSpeech();
            modal.remove();
        }
    }

    function enableModalDrag(modal, dialog, handle) {
        var dragging = false;
        var pointerId = null;
        var offsetX = 0;
        var offsetY = 0;

        function pointerDown(event) {
            if (event.button !== undefined && event.button !== 0) return;
            if (event.target.closest('button, input, textarea')) return;
            var rect = dialog.getBoundingClientRect();
            dragging = true;
            pointerId = event.pointerId;
            offsetX = event.clientX - rect.left;
            offsetY = event.clientY - rect.top;
            dialog.style.position = 'fixed';
            dialog.style.left = rect.left + 'px';
            dialog.style.top = rect.top + 'px';
            dialog.style.width = rect.width + 'px';
            dialog.style.height = rect.height + 'px';
            handle.setPointerCapture(pointerId);
            event.preventDefault();
        }

        function pointerMove(event) {
            if (!dragging || event.pointerId !== pointerId) return;
            var maxLeft = Math.max(4, window.innerWidth - dialog.offsetWidth - 4);
            var maxTop = Math.max(4, window.innerHeight - dialog.offsetHeight - 4);
            var left = Math.min(Math.max(4, event.clientX - offsetX), maxLeft);
            var top = Math.min(Math.max(4, event.clientY - offsetY), maxTop);
            dialog.style.left = left + 'px';
            dialog.style.top = top + 'px';
        }

        function pointerUp(event) {
            if (!dragging || event.pointerId !== pointerId) return;
            dragging = false;
            if (handle.hasPointerCapture(pointerId)) handle.releasePointerCapture(pointerId);
            pointerId = null;
        }

        handle.addEventListener('pointerdown', pointerDown);
        handle.addEventListener('pointermove', pointerMove);
        handle.addEventListener('pointerup', pointerUp);
        handle.addEventListener('pointercancel', pointerUp);
        modal.cleanupDrag = function () {
            handle.removeEventListener('pointerdown', pointerDown);
            handle.removeEventListener('pointermove', pointerMove);
            handle.removeEventListener('pointerup', pointerUp);
            handle.removeEventListener('pointercancel', pointerUp);
        };
    }

    function formatDateBr(value) {
        var parts = String(value || '').split('-');
        return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : value;
    }

    function receitaValue(config, name) {
        return String((config && config[name]) || '').trim();
    }

    function setupSpeechDictation(button, textarea) {
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
        var localHost = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname);
        var insecureMicrophone = window.isSecureContext === false ||
            (window.location.protocol !== 'https:' && !localHost);
        if (!SpeechRecognition) {
            button.title = 'Reconhecimento de voz não disponível neste navegador.';
            button.onclick = function () {
                textarea.focus();
                CrudUI.notify(
                    'Este navegador não oferece reconhecimento de voz. ' +
                    'No Android, abra o MedSoft no Chrome. No iPhone, use o microfone do teclado para ditar.',
                    'error'
                );
            };
            return function () {};
        }
        if (insecureMicrophone) {
            button.title = 'No celular, abra o MedSoft por uma conexão HTTPS para liberar o microfone.';
        }

        var recognition = new SpeechRecognition();
        var listening = false;
        var baseText = '';
        var separator = '';
        var finalText = '';

        recognition.lang = 'pt-BR';
        recognition.continuous = !isMobile;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        function updateButton() {
            button.setAttribute('aria-pressed', listening ? 'true' : 'false');
            button.classList.toggle('crud-button-danger', listening);
            button.classList.toggle('crud-button-secondary', !listening);
            button.innerHTML = listening
                ? '<i class="fa fa-stop"></i><span> Parar</span>'
                : '<i class="fa fa-microphone"></i><span> Ditado por voz</span>';
        }

        function stop() {
            if (listening) {
                listening = false;
                try { recognition.stop(); } catch (error) {}
            }
            if (activeDictationStop === stop) activeDictationStop = null;
            updateButton();
        }

        async function requestMicrophonePermission() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return true;
            try {
                var stream = await navigator.mediaDevices.getUserMedia({audio: true});
                stream.getTracks().forEach(function (track) { track.stop(); });
                return true;
            } catch (error) {
                var permissionDenied = error && (
                    error.name === 'NotAllowedError' ||
                    error.name === 'PermissionDeniedError'
                );
                CrudUI.notify(
                    permissionDenied
                        ? 'O acesso ao microfone foi negado. Permita o microfone nas configurações do navegador e tente novamente.'
                        : 'Não foi possível acessar o microfone deste aparelho.',
                    'error'
                );
                return false;
            }
        }

        button.onclick = async function () {
            if (listening) {
                stop();
                return;
            }
            if (insecureMicrophone) {
                CrudUI.notify(
                    'O navegador do celular bloqueou o microfone porque o MedSoft foi aberto por HTTP. ' +
                    'Acesse o sistema por HTTPS e permita o uso do microfone.',
                    'error'
                );
                return;
            }
            if (!await requestMicrophonePermission()) return;
            if (activeDictationStop) activeDictationStop();
            baseText = textarea.value.trimEnd();
            separator = baseText ? '\n' : '';
            finalText = '';
            try {
                recognition.start();
                activeDictationStop = stop;
            } catch (error) {
                CrudUI.notify(
                    'Não foi possível iniciar o microfone. Verifique a permissão do navegador.',
                    'error'
                );
            }
        };

        recognition.onstart = function () {
            listening = true;
            updateButton();
            CrudUI.notify('Ditado iniciado. Fale próximo ao microfone.');
        };

        recognition.onresult = function (event) {
            var interimText = '';
            for (var index = event.resultIndex; index < event.results.length; index += 1) {
                var transcript = event.results[index][0].transcript;
                if (event.results[index].isFinal) finalText += transcript.trim() + ' ';
                else interimText += transcript;
            }
            textarea.value = baseText + separator + finalText + interimText;
            textarea.scrollTop = textarea.scrollHeight;
        };

        recognition.onerror = function (event) {
            var messages = {
                'not-allowed': 'Permita o acesso ao microfone nas configurações do navegador.',
                'service-not-allowed': 'O serviço de voz foi bloqueado. Use Chrome ou Edge com acesso HTTPS.',
                'audio-capture': 'Nenhum microfone disponível foi encontrado.',
                'no-speech': 'Nenhuma fala foi identificada.',
                'network': 'Não foi possível acessar o serviço de reconhecimento de voz. Verifique a internet.',
                'language-not-supported': 'O reconhecimento de voz em português não está disponível neste aparelho.',
                'aborted': 'O ditado foi interrompido.'
            };
            CrudUI.notify(messages[event.error] || 'Não foi possível reconhecer a fala.', 'error');
        };

        recognition.onend = function () {
            listening = false;
            if (activeDictationStop === stop) activeDictationStop = null;
            updateButton();
        };

        updateButton();
        return function () {
            button.onclick = null;
            if (listening) {
                listening = false;
                try { recognition.abort(); } catch (error) {}
            }
            if (activeDictationStop === stop) activeDictationStop = null;
        };
    }

    function showGoogleMeetDialog() {
        var existing = document.getElementById('google-meet-link-modal');
        if (existing) existing.remove();

        var linkModal = document.createElement('div');
        linkModal.id = 'google-meet-link-modal';
        linkModal.className = 'google-meet-link-modal';
        linkModal.innerHTML =
            '<div class="google-meet-link-dialog" role="dialog" aria-modal="true" aria-labelledby="google-meet-title">' +
            '<div class="google-meet-link-header"><div><h3 id="google-meet-title">Teleconsulta</h3>' +
            '<span>Informe o link da reunião (Google Meet)</span></div>' +
            '<button type="button" class="historico-close google-meet-close" title="Fechar">&times;</button></div>' +
            '<form class="google-meet-link-form">' +
            '<label class="crud-field"><span>Link da reunião (Google Meet)</span>' +
            '<input class="crud-input google-meet-link-input" type="url" inputmode="url" ' +
            'placeholder="https://meet.google.com/abc-defg-hij" required></label>' +
            '<div class="google-meet-link-actions">' +
            '<button type="button" class="crud-button crud-button-secondary google-meet-cancel">Cancelar</button>' +
            '<button type="submit" class="crud-button crud-button-primary"><i class="fa fa-external-link"></i><span> Abrir</span></button>' +
            '</div></form></div>';
        document.body.appendChild(linkModal);

        var input = linkModal.querySelector('.google-meet-link-input');
        var close = function () { linkModal.remove(); };
        linkModal.querySelector('.google-meet-close').onclick = close;
        linkModal.querySelector('.google-meet-cancel').onclick = close;
        linkModal.onclick = function (event) { if (event.target === linkModal) close(); };
        linkModal.querySelector('form').onsubmit = function (event) {
            event.preventDefault();
            var meetingUrl;
            try {
                meetingUrl = new URL(input.value.trim());
            } catch (error) {
                CrudUI.notify('Informe um link válido do Google Meet.', 'error');
                input.focus();
                return;
            }
            if (meetingUrl.protocol !== 'https:' || meetingUrl.hostname !== 'meet.google.com' || meetingUrl.pathname === '/') {
                CrudUI.notify('Informe um link iniciado por https://meet.google.com/.', 'error');
                input.focus();
                return;
            }

            var popupWidth = Math.min(460, screen.availWidth);
            var popupHeight = Math.min(560, screen.availHeight);
            var popupLeft = Math.max(0, screen.availLeft + screen.availWidth - popupWidth);
            var popupTop = Math.max(0, screen.availTop + Math.round((screen.availHeight - popupHeight) / 2));
            var popup = window.open(
                meetingUrl.href,
                'medsoft_google_meet',
                'popup=yes,width=' + popupWidth + ',height=' + popupHeight +
                ',left=' + popupLeft + ',top=' + popupTop + ',resizable=yes,scrollbars=yes'
            );
            if (!popup) {
                CrudUI.notify('Permita a abertura de janelas para iniciar o Google Meet.', 'error');
                return;
            }
            popup.focus();
            close();
            CrudUI.notify('Google Meet aberto à direita. O histórico continua disponível.');
        };
        input.focus();
    }

    async function loadReceitaConfig(nomed) {
        var professionalName = String(nomed || '').trim();
        var data = await api('/api/prof-saude', 'POST', {termo: professionalName});
        var profissionais = data.profissionais || [];
        if (professionalName) {
            var expected = professionalName.toLocaleUpperCase('pt-BR');
            var exact = profissionais.find(function (item) {
                return String(item.nome || '').trim().toLocaleUpperCase('pt-BR') === expected;
            });
            if (exact) return exact;
        }
        return profissionais.find(function (item) {
            return item.logorec || item.tit1 || item.tit2 || item.tit3 ||
                item.rod1 || item.rod2 || item.cidade_receita;
        }) || profissionais[0] || {};
    }

    function printReceita(nomecli, dtvisita, texto, config, options) {
        options = options || {};
        var printWindow = window.open('', '_blank', 'width=900,height=1000');
        if (!printWindow) {
            CrudUI.notify('O navegador bloqueou a janela de impressão.', 'error');
            return;
        }
        var logo = receitaValue(config, 'logorec');
        var logoHtml = logo.indexOf('data:image') === 0
            ? '<div class="logo-wrap"><img class="logo" src="' + CrudUI.escapeHtml(logo) + '" alt="Logo da receita"></div>'
            : '<div class="logo-wrap"></div>';
        var printPatientName = options.receitaAvulsa ? '' : (nomecli || '');
        var printDate = options.receitaSemData ? '' : formatDateBr(dtvisita);
        var cidadeData = [receitaValue(config, 'cidade_receita'), printDate]
            .filter(Boolean).join(', ');
        var titulos = ['tit1', 'tit2', 'tit3'].map(function (field, index) {
            return '<div class="title-line title-' + (index + 1) + '">' +
                CrudUI.escapeHtml(receitaValue(config, field)) + '</div>';
        }).join('');
        var rodapes = ['rod1', 'rod2'].map(function (field) {
            return '<div>' + CrudUI.escapeHtml(receitaValue(config, field)) + '</div>';
        }).join('');
        // Título 1 usa as colunas históricas fonte_cabecalho/tamanho_cabecalho.
        // Títulos 2 e 3 têm configuração própria; em bases antigas, usam o Título 1 como fallback.
        var fonteCabecalho = receitaValue(config, 'fonte_cabecalho') || 'Arial';
        var tamanhoCabecalho = parseInt(receitaValue(config, 'tamanho_cabecalho'), 10);
        var fonteCabecalho2 = receitaValue(config, 'fonte_cabecalho2') || fonteCabecalho;
        var tamanhoCabecalho2 = parseInt(receitaValue(config, 'tamanho_cabecalho2'), 10);
        var fonteCabecalho3 = receitaValue(config, 'fonte_cabecalho3') || fonteCabecalho;
        var tamanhoCabecalho3 = parseInt(receitaValue(config, 'tamanho_cabecalho3'), 10);
        var fonteRodape = receitaValue(config, 'fonte_rodape') || 'Arial';
        var tamanhoRodape = parseInt(receitaValue(config, 'tamanho_rodape'), 10);
        var exibirLinhaCabecalho = receitaValue(config, 'linha_cabecalho').toUpperCase() !== 'N';
        var exibirLinhaRodape = receitaValue(config, 'linha_rodape').toUpperCase() !== 'N';
        var espessuraLinhaCabecalho = parseFloat(receitaValue(config, 'espessura_linha_cabecalho'));
        var espessuraLinhaRodape = parseFloat(receitaValue(config, 'espessura_linha_rodape'));
        if (!Number.isFinite(tamanhoCabecalho)) tamanhoCabecalho = 16;
        if (!Number.isFinite(tamanhoCabecalho2)) tamanhoCabecalho2 = tamanhoCabecalho;
        if (!Number.isFinite(tamanhoCabecalho3)) tamanhoCabecalho3 = tamanhoCabecalho;
        if (!Number.isFinite(tamanhoRodape)) tamanhoRodape = 13;
        if (!Number.isFinite(espessuraLinhaCabecalho)) espessuraLinhaCabecalho = 1;
        if (!Number.isFinite(espessuraLinhaRodape)) espessuraLinhaRodape = 1;
        // Não reduzir silenciosamente os tamanhos configurados pelo profissional.
        // A versão anterior limitava os títulos a 36 pt e o rodapé a 24 pt.
        tamanhoCabecalho = Math.max(6, Math.min(96, tamanhoCabecalho));
        tamanhoCabecalho2 = Math.max(6, Math.min(96, tamanhoCabecalho2));
        tamanhoCabecalho3 = Math.max(6, Math.min(96, tamanhoCabecalho3));
        tamanhoRodape = Math.max(6, Math.min(72, tamanhoRodape));
        espessuraLinhaCabecalho = Math.max(0.5, Math.min(5, espessuraLinhaCabecalho));
        espessuraLinhaRodape = Math.max(0.5, Math.min(5, espessuraLinhaRodape));
        var fontesPermitidas = ['Arial', 'Verdana', 'Tahoma', 'Trebuchet MS', 'Calibri', 'Cambria', 'Times New Roman', 'Georgia', 'Garamond', 'Palatino Linotype', 'Courier New', 'Brush Script MT', 'Lucida Handwriting', 'Segoe Script', 'Monotype Corsiva', 'Edwardian Script ITC'];
        if (fontesPermitidas.indexOf(fonteCabecalho) === -1) fonteCabecalho = 'Arial';
        if (fontesPermitidas.indexOf(fonteCabecalho2) === -1) fonteCabecalho2 = fonteCabecalho;
        if (fontesPermitidas.indexOf(fonteCabecalho3) === -1) fonteCabecalho3 = fonteCabecalho;
        if (fontesPermitidas.indexOf(fonteRodape) === -1) fonteRodape = 'Arial';
        printWindow.document.write(
            '<!doctype html><html lang="pt-br"><head><meta charset="utf-8">' +
            '<title>Receita médica</title><style>' +
            '@page{size:A4 portrait;margin:0}*{box-sizing:border-box}' +
            'html,body{width:210mm;height:297mm;margin:0;padding:0}' +
            'body{font-family:Arial,sans-serif;color:#18243a}' +
            /* A impressão usa a própria folha A4 e exatamente o mesmo recuo da pré-visualização. */
            '.page{width:210mm;height:297mm;min-height:297mm;padding:12mm 16mm 12mm;display:flex;flex-direction:column;overflow:hidden}' +
            '.top{min-height:28mm;flex:0 0 auto;position:relative;display:flex;align-items:center;justify-content:center;overflow:visible}' +
            '.logo-wrap{position:absolute;left:0;top:0;height:28mm;width:32mm;display:flex;align-items:center;justify-content:flex-start}' +
            '.logo{display:block;max-width:32mm;max-height:28mm;object-fit:contain;object-position:left center}' +
            '.signature{min-height:35mm;display:flex;align-items:center;justify-content:center}' +
            '.city-date{text-align:center;font-size:10.5pt;font-weight:600}' +
            '.stacked{display:flex;flex-direction:column;text-align:center}' +
            '.titles{width:100%;min-height:28mm;justify-content:center;text-align:center;gap:0;overflow:visible}' +
            '.title-line{display:block;width:100%;max-width:none;white-space:nowrap;overflow:visible;line-height:1.12;margin:0;padding:0;font-stretch:normal;font-style:normal;font-synthesis:none;transform:none}' +
            '.title-1{font-family:' + JSON.stringify(fonteCabecalho) + ',sans-serif;font-size:' + tamanhoCabecalho + 'pt;transform:scaleX(1.28);transform-origin:center center}' +
            '.title-2{font-family:' + JSON.stringify(fonteCabecalho2) + ',sans-serif;font-size:' + tamanhoCabecalho2 + 'pt}' +
            '.title-3{font-family:' + JSON.stringify(fonteCabecalho3) + ',sans-serif;font-size:' + tamanhoCabecalho3 + 'pt}' +
            '.header-rule-area{height:5mm;flex:0 0 5mm;position:relative}' +
            '.header-rule{position:absolute;left:0;right:0;bottom:1mm;border:0;margin:0}' +
            '.header-content-gap{height:8mm;flex:0 0 8mm}' +
            '.patient{margin-bottom:5mm;font-size:11pt}' +
            '.receita{flex:1;white-space:pre-wrap;font-size:12pt;line-height:1.55}' +
            '.footer-rule{border:0;margin:5mm 0 2.5mm}.footers{min-height:7mm;font-family:' + JSON.stringify(fonteRodape) + ',sans-serif;font-size:' + tamanhoRodape + 'pt;line-height:1.2}' +
            '</style></head><body><div class="page">' +
            '<div class="top">' + logoHtml + '<header class="stacked titles">' + titulos + '</header></div>' +
            '<div class="header-rule-area">' +
            (exibirLinhaCabecalho
                ? '<hr class="header-rule" style="border-top:' + espessuraLinhaCabecalho + 'px solid #7d8999">'
                : '') +
            '</div>' +
            '<div class="header-content-gap" aria-hidden="true"></div>' +
            '<div class="patient"><strong>Paciente:</strong> ' + CrudUI.escapeHtml(printPatientName) + '</div>' +
            '<main class="receita">' + CrudUI.escapeHtml(texto || '') + '</main>' +
            '<div class="signature"><div class="city-date">' + CrudUI.escapeHtml(cidadeData) + '</div></div>' +
            '<footer>' + (exibirLinhaRodape ? '<hr class="rule footer-rule" style="border-top:' + espessuraLinhaRodape + 'px solid #7d8999">' : '') + '<div class="stacked footers">' + rodapes +
            '</div></footer></div></body></html>'
        );
        printWindow.document.close();
        printWindow.focus();
        // Aguarda o Chromium/Edge confirmar as fontes locais antes de abrir a impressão.
        // Isso é importante principalmente para Monotype Corsiva / Edwardian Script ITC.
        var abrirImpressao = function () {
            setTimeout(function () { printWindow.print(); }, 120);
        };
        if (printWindow.document.fonts && printWindow.document.fonts.ready) {
            printWindow.document.fonts.ready.then(abrirImpressao, abrirImpressao);
        } else {
            setTimeout(abrirImpressao, 350);
        }
    }

    function showReceitaModal(codcli, nomecli, config) {
        closeReceitaModal();
        var modal = document.createElement('div');
        modal.id = 'paciente-receita-modal';
        modal.className = 'historico-modal receita-modal';
        modal.innerHTML =
            '<div class="receita-dialog" role="dialog" aria-modal="true" aria-labelledby="receita-titulo">' +
            '<form class="receita-form">' +
            '<div class="receita-header">' +
            '<div><h3 id="receita-titulo">Receita de ' + CrudUI.escapeHtml(nomecli || '') + '</h3>' +
            '<span>Receituário médico</span></div>' +
            '<div class="receita-header-actions">' +
            '<button type="button" class="crud-button crud-button-secondary receita-print" title="Imprimir receita" aria-label="Imprimir receita">' +
            '<i class="fa fa-print"></i></button>' +
            '<button type="submit" class="crud-button crud-button-primary receita-history">' +
            '<i class="fa fa-history"></i><span> Atualizar histórico</span></button>' +
            '<button type="button" class="historico-close receita-close" title="Fechar">&times;</button>' +
            '</div></div>' +
            '<div class="receita-paper">' +
            '<div class="receita-padrao-tools">' +
            '<label class="crud-field"><span>Tipo</span>' +
            '<select class="crud-input receita-padrao-tipo">' +
            '<option value="R" selected>Rec</option><option value="X">Ex</option>' +
            '<option value="P">Pr</option><option value="A">An</option>' +
            '</select></label>' +
            '<label class="crud-field"><span>Padrão</span>' +
            '<input type="text" class="crud-input receita-padrao-search" list="receita-padrao-list" ' +
            'placeholder="Buscar padrão cadastrado" autocomplete="off"></label>' +
            '<datalist id="receita-padrao-list"></datalist>' +
            '<button type="button" class="crud-button receita-padrao-add" disabled>' +
            '<i class="fa fa-plus"></i><span> Incluir padrão</span></button></div>' +
            '<div class="receita-date-options">' +
            '<label class="crud-field receita-date"><span>Data</span>' +
            '<input type="date" class="crud-input" name="dtvisita" value="' + localToday() + '" required></label>' +
            '<label class="crud-checkbox-option"><input type="checkbox" name="receita_sem_data">' +
            '<span>Receita sem data</span></label>' +
            '<label class="crud-checkbox-option"><input type="checkbox" name="receita_avulsa">' +
            '<span>Receita avulsa</span></label></div>' +
            '<div class="crud-field receita-memo">' +
            '<div class="dictation-heading"><label for="receita-texto">Receita</label>' +
            '<button type="button" class="crud-button crud-button-secondary dictation-button receita-dictation" ' +
            'aria-pressed="false"><i class="fa fa-microphone"></i><span> Ditado por voz</span></button></div>' +
            '<textarea id="receita-texto" name="historico" required></textarea></div>' +
            '</div></form></div>';

        document.body.appendChild(modal);
        var form = modal.querySelector('.receita-form');
        var memo = form.querySelector('[name="historico"]');
        var dateInput = form.querySelector('[name="dtvisita"]');
        var semDataInput = form.querySelector('[name="receita_sem_data"]');
        var receitaAvulsaInput = form.querySelector('[name="receita_avulsa"]');
        var padraoTipo = form.querySelector('.receita-padrao-tipo');
        var padraoSearch = form.querySelector('.receita-padrao-search');
        var padraoList = form.querySelector('#receita-padrao-list');
        var padraoAddButton = form.querySelector('.receita-padrao-add');
        var dictationButton = form.querySelector('.receita-dictation');
        var dialog = modal.querySelector('.receita-dialog');
        var header = modal.querySelector('.receita-header');
        var padroes = [];
        var padraoSearchTimer;
        var padraoRequest = 0;

        function normalizePadraoName(value) {
            return String(value || '').trim().toLocaleUpperCase('pt-BR');
        }

        function selectedPadrao() {
            var expected = normalizePadraoName(padraoSearch.value);
            return padroes.find(function (item) {
                return normalizePadraoName(item.nome) === expected;
            });
        }

        function updatePadraoSelection() {
            padraoAddButton.disabled = !selectedPadrao();
        }

        async function loadPadroes(term) {
            var requestNumber = ++padraoRequest;
            try {
                var data = await api('/api/anamnese', 'POST', {
                    termo: term || '',
                    tipo: padraoTipo.value
                });
                if (requestNumber !== padraoRequest) return;
                padroes = data.anamneses || [];
                padraoList.innerHTML = padroes.map(function (item) {
                    return '<option value="' + CrudUI.escapeHtml(item.nome || '') + '"></option>';
                }).join('');
                updatePadraoSelection();
            } catch (error) {
                if (requestNumber !== padraoRequest) return;
                padroes = [];
                padraoList.innerHTML = '';
                updatePadraoSelection();
                CrudUI.notify(error.message || 'Não foi possível buscar os padrões.', 'error');
            }
        }

        enableModalDrag(modal, dialog, header);
        modal.cleanupSpeech = setupSpeechDictation(dictationButton, memo);

        loadPadroes('');

        padraoSearch.oninput = function () {
            updatePadraoSelection();
            clearTimeout(padraoSearchTimer);
            padraoSearchTimer = setTimeout(function () {
                loadPadroes(padraoSearch.value.trim());
            }, 250);
        };
        padraoSearch.onchange = updatePadraoSelection;
        padraoTipo.onchange = function () {
            padraoSearch.value = '';
            padroes = [];
            padraoList.innerHTML = '';
            padraoAddButton.disabled = true;
            loadPadroes('');
        };
        padraoAddButton.onclick = function () {
            var padrao = selectedPadrao();
            if (!padrao) {
                CrudUI.notify('Selecione um padrão cadastrado.', 'error');
                padraoSearch.focus();
                return;
            }
            var padraoText = String(padrao.texto || '').trim();
            if (!padraoText) {
                CrudUI.notify('O padrão selecionado não possui texto cadastrado.', 'error');
                return;
            }
            var existingText = memo.value.trimEnd();
            memo.value = existingText ? existingText + '\n\n' + padraoText : padraoText;
            memo.focus();
            memo.setSelectionRange(memo.value.length, memo.value.length);
            CrudUI.notify('Texto do padrão incluído na receita.');
        };

        modal.querySelector('.receita-close').onclick = closeReceitaModal;
        modal.querySelector('.receita-print').onclick = function () {
            if (!memo.value.trim()) {
                CrudUI.notify('Digite a receita antes de imprimir.', 'error');
                memo.focus();
                return;
            }
            printReceita(nomecli, dateInput.value, memo.value, config, {
                receitaSemData: semDataInput.checked,
                receitaAvulsa: receitaAvulsaInput.checked
            });
        };
        form.onsubmit = function (event) {
            event.preventDefault();
            if (!memo.value.trim()) {
                CrudUI.notify('Digite a receita antes de atualizar o histórico.', 'error');
                memo.focus();
                return;
            }
            var historicoModal = document.getElementById('paciente-historico-modal');
            var historicoForm = historicoModal && historicoModal.querySelector('.historico-form');
            if (!historicoForm) {
                CrudUI.notify('Abra o formulário de Histórico antes de copiar a receita.', 'error');
                return;
            }
            var historicoMemo = historicoForm.querySelector('[name="historico"]');
            var historicoDate = historicoForm.querySelector('[name="dtvisita"]');
            var existingText = historicoMemo.value.trimEnd();
            historicoMemo.value = existingText
                ? existingText + '\n\n' + memo.value.trim()
                : memo.value.trim();
            historicoDate.value = dateInput.value;
            historicoForm.hidden = false;
            historicoModal.querySelector('.historico-include').disabled = true;
            closeReceitaModal();
            historicoMemo.focus();
            historicoMemo.setSelectionRange(historicoMemo.value.length, historicoMemo.value.length);
            CrudUI.notify('Receita copiada. Revise o histórico e clique em Salvar.');
        };
        modal.onclick = function (event) {
            if (event.target === modal) closeReceitaModal();
        };
        memo.focus();
    }

    function localToday() {
        var today = new Date();
        var month = String(today.getMonth() + 1).padStart(2, '0');
        var day = String(today.getDate()).padStart(2, '0');
        return today.getFullYear() + '-' + month + '-' + day;
    }

    function historicoPatientTitle(nomecli, patient) {
        patient = patient || {};
        var parts = [CrudUI.escapeHtml(nomecli || '')];
        if (patient.idade !== null && patient.idade !== undefined && patient.idade !== '') {
            parts.push('Idade: ' + CrudUI.escapeHtml(patient.idade) + ' anos');
        }
        if (patient.nomeplano1) {
            parts.push('Plano: ' + CrudUI.escapeHtml(patient.nomeplano1));
        }
        return parts.join(' ');
    }

    function showHistoricoModal(codcli, nomecli, consultas, patient) {
        closeHistoricoModal();
        consultas = consultas || [];
        if (typeof patient === 'string') patient = {nomed: patient};
        patient = patient || {};
        var nomed = patient.nomed || '';
        var headerTitle = historicoPatientTitle(nomecli, patient);

        var rows = consultas.map(function (c) {
            return '<tr>' +
                '<td class="historico-select"><input type="checkbox" class="historico-item-check" data-consulta-id="' +
                CrudUI.escapeHtml(c.cod) + '" aria-label="Selecionar histórico de ' + CrudUI.escapeHtml(c.dtvisita) + '"></td>' +
                '<td class="historico-data">' + historicoCell(c.dtvisita) + '</td>' +
                '<td>' + historicoCell(c.medico_nome || '') + '</td>' +
                '<td class="historico-texto">' + historicoCell(c.historico, true) + '</td>' +
                '</tr>';
        }).join('');

        var body = consultas.length ? (
            '<div class="historico-table-wrap"><table class="historico-table">' +
            '<thead><tr>' +
            '<th class="historico-select"></th><th>Data</th><th>Prof. Saúde</th><th>Histórico</th>' +
            '</tr></thead><tbody>' + rows + '</tbody></table></div>'
        ) : '<div class="crud-empty">Nenhuma consulta registrada para este paciente.</div>';

        var modal = document.createElement('div');
        modal.id = 'paciente-historico-modal';
        modal.className = 'historico-modal';
        modal.innerHTML =
            '<div class="historico-dialog" role="dialog" aria-modal="true">' +
            '<div class="historico-header">' +
            '<div><h3>' + headerTitle + '</h3>' +
            '<span>Tabela consulta</span></div>' +
            '<div class="historico-header-actions">' +
            '<button type="button" class="crud-button crud-button-primary historico-include" title="Incluir histórico">' +
            '<i class="fa fa-plus"></i><span> Incluir</span></button>' +
            '<button type="button" class="crud-button crud-button-secondary historico-alterar" title="Alterar histórico selecionado" disabled>' +
            '<i class="fa fa-pencil"></i><span> Alterar</span></button>' +
            '<button type="button" class="crud-button crud-button-secondary historico-receita" title="Criar receita">' +
            '<i class="fa fa-file-text-o"></i><span> Receita</span></button>' +
            '<button type="button" class="historico-close" title="Fechar">&times;</button>' +
            '</div></div>' +
            '<form class="historico-form" hidden>' +
            '<label class="crud-field"><span>Data</span>' +
            '<input type="date" class="crud-input" name="dtvisita" value="' + localToday() + '" required></label>' +
            '<div class="historico-anamnese-tools">' +
            '<label class="crud-field historico-padrao-tipo-field"><span>Tipo</span>' +
            '<select class="crud-input historico-padrao-tipo">' +
            '<option value="R">Rec</option><option value="X">Ex</option>' +
            '<option value="P">Pr</option><option value="A" selected>An</option>' +
            '</select></label>' +
            '<label class="crud-field"><span>Padrão</span>' +
            '<input type="text" class="crud-input historico-anamnese-search" list="historico-anamnese-list" ' +
            'placeholder="Buscar padrão cadastrado" autocomplete="off"></label>' +
            '<datalist id="historico-anamnese-list"></datalist>' +
            '<button type="button" class="crud-button historico-anamnese-add" disabled>' +
            '<i class="fa fa-plus"></i><span> Incluir padrão</span></button></div>' +
            '<div class="crud-field historico-form-memo">' +
            '<div class="dictation-heading"><label for="historico-texto">Histórico</label><div class="historico-memo-tools">' +
            '<button type="button" class="crud-button crud-button-secondary google-meet-button" title="Abrir reunião do Google Meet">' +
            '<i class="fa fa-video-camera"></i><span> Teleconsulta</span></button>' +
            '<button type="button" class="crud-button crud-button-secondary dictation-button historico-dictation" ' +
            'aria-pressed="false"><i class="fa fa-microphone"></i><span> Ditado por voz</span></button>' +
            '<button type="button" class="crud-button crud-button-secondary historico-organizar-texto" disabled ' +
            'title="Organizar o texto pelos tópicos do padrão selecionado">' +
            '<i class="fa fa-list-alt"></i><span> Organizar texto</span></button></div></div>' +
            '<textarea id="historico-texto" name="historico" rows="7" required></textarea></div>' +
            '<div class="historico-organization-review" hidden>Revise cuidadosamente o texto organizado antes de salvar.</div>' +
            '<div class="historico-form-actions">' +
            '<button type="button" class="crud-button historico-form-cancel">Cancelar</button>' +
            '<button type="submit" class="crud-button crud-button-primary"><i class="fa fa-check"></i><span> Salvar</span></button>' +
            '</div></form>' + body + '</div>';

        document.body.appendChild(modal);
        var dialog = modal.querySelector('.historico-dialog');
        var form = modal.querySelector('.historico-form');
        var includeButton = modal.querySelector('.historico-include');
        var alterButton = modal.querySelector('.historico-alterar');
        var receitaButton = modal.querySelector('.historico-receita');
        var cancelButton = modal.querySelector('.historico-form-cancel');
        var submitButton = form.querySelector('[type="submit"]');
        var historicoMemo = form.querySelector('[name="historico"]');
        var dictationButton = form.querySelector('.historico-dictation');
        var organizeButton = form.querySelector('.historico-organizar-texto');
        var organizationReview = form.querySelector('.historico-organization-review');
        var googleMeetButton = form.querySelector('.google-meet-button');
        var padraoTipo = form.querySelector('.historico-padrao-tipo');
        var anamneseSearch = form.querySelector('.historico-anamnese-search');
        var anamneseList = form.querySelector('#historico-anamnese-list');
        var anamneseAddButton = form.querySelector('.historico-anamnese-add');
        var anamneses = [];
        var anamneseSearchTimer;
        var anamneseRequest = 0;
        var activeAnamnese = null;
        var editingConsultation = null;

        function isoVisitDate(value) {
            var match = String(value || '').match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
            return match ? match[3] + '-' + match[2] + '-' + match[1] : localToday();
        }

        modal.querySelectorAll('.historico-item-check').forEach(function (checkbox) {
            checkbox.onchange = function () {
                modal.querySelectorAll('.historico-item-check').forEach(function (other) {
                    if (other !== checkbox) other.checked = false;
                });
                alterButton.disabled = !checkbox.checked;
            };
        });

        alterButton.onclick = function () {
            var checked = modal.querySelector('.historico-item-check:checked');
            if (!checked) return;
            editingConsultation = consultas.find(function (item) { return String(item.cod) === checked.dataset.consultaId; });
            if (!editingConsultation) return;
            form.hidden = false;
            dialog.classList.add('historico-editing');
            includeButton.disabled = true;
            alterButton.disabled = true;
            form.querySelector('[name="dtvisita"]').value = isoVisitDate(editingConsultation.dtvisita);
            historicoMemo.value = editingConsultation.historico || '';
            submitButton.querySelector('span').textContent = ' Salvar alteração';
            historicoMemo.focus();
        };

        var planCapabilities = window.MedsoftPlanCapabilities || {
            teleconsulta: true, ditadovoz: true
        };
        if (planCapabilities.ditadovoz) {
            modal.cleanupSpeech = setupSpeechDictation(dictationButton, historicoMemo);
        } else {
            dictationButton.disabled = true;
            dictationButton.title = 'Ditado por voz não disponível no plano contratado';
            modal.cleanupSpeech = function () {};
        }
        if (planCapabilities.teleconsulta) {
            googleMeetButton.onclick = showGoogleMeetDialog;
        } else {
            googleMeetButton.disabled = true;
            googleMeetButton.title = 'Teleconsulta não disponível no plano contratado';
        }

        function normalizeAnamneseName(value) {
            return String(value || '').trim().toLocaleUpperCase('pt-BR');
        }

        function selectedAnamnese() {
            var expected = normalizeAnamneseName(anamneseSearch.value);
            return anamneses.find(function (item) {
                return normalizeAnamneseName(item.nome) === expected;
            });
        }

        function updateAnamneseSelection() {
            anamneseAddButton.disabled = !selectedAnamnese();
        }

        async function loadAnamneses(term) {
            var requestNumber = ++anamneseRequest;
            try {
                var data = await api('/api/anamnese', 'POST', {
                    termo: term || '',
                    tipo: padraoTipo.value
                });
                if (requestNumber !== anamneseRequest) return;
                anamneses = data.anamneses || [];
                anamneseList.innerHTML = anamneses.map(function (item) {
                    return '<option value="' + CrudUI.escapeHtml(item.nome || '') + '"></option>';
                }).join('');
                updateAnamneseSelection();
            } catch (error) {
                if (requestNumber !== anamneseRequest) return;
                anamneses = [];
                anamneseList.innerHTML = '';
                updateAnamneseSelection();
                CrudUI.notify(error.message || 'Não foi possível buscar os padrões.', 'error');
            }
        }

        includeButton.onclick = function () {
            form.hidden = false;
            dialog.classList.add('historico-editing');
            includeButton.disabled = true;
            alterButton.disabled = true;
            editingConsultation = null;
            submitButton.querySelector('span').textContent = ' Salvar';
            loadAnamneses('');
            historicoMemo.focus();
        };
        anamneseSearch.oninput = function () {
            updateAnamneseSelection();
            clearTimeout(anamneseSearchTimer);
            anamneseSearchTimer = setTimeout(function () {
                loadAnamneses(anamneseSearch.value.trim());
            }, 250);
        };
        anamneseSearch.onchange = updateAnamneseSelection;
        padraoTipo.onchange = function () {
            anamneseSearch.value = '';
            anamneses = [];
            anamneseList.innerHTML = '';
            anamneseAddButton.disabled = true;
            loadAnamneses('');
        };
        anamneseAddButton.onclick = function () {
            var anamnese = selectedAnamnese();
            if (!anamnese) {
                CrudUI.notify('Selecione um padrão cadastrado.', 'error');
                anamneseSearch.focus();
                return;
            }
            var protocolText = String(anamnese.texto || '').trim();
            if (!protocolText) {
                CrudUI.notify('O padrão selecionado não possui texto cadastrado.', 'error');
                return;
            }
            var existingText = historicoMemo.value.trimEnd();
            historicoMemo.value = existingText ? existingText + '\n\n' + protocolText : protocolText;
            activeAnamnese = anamnese;
            organizeButton.disabled = false;
            organizationReview.hidden = true;
            historicoMemo.focus();
            historicoMemo.setSelectionRange(historicoMemo.value.length, historicoMemo.value.length);
            CrudUI.notify('Texto do padrão incluído no histórico.');
        };
        organizeButton.onclick = async function () {
            var currentText = historicoMemo.value.trim();
            var patternText = activeAnamnese && String(activeAnamnese.texto || '').trim();
            if (!currentText || !patternText) {
                CrudUI.notify('Selecione e inclua um padrão antes de organizar.', 'error');
                return;
            }
            if (!window.confirm('O texto atual será substituído pela versão organizada. Deseja continuar?')) return;
            organizeButton.disabled = true;
            try {
                var result = await api('/api/consultas-paciente/organizar', 'POST', {
                    texto_livre: currentText,
                    padrao: patternText
                });
                historicoMemo.value = result.historico || currentText;
                organizationReview.hidden = false;
                historicoMemo.focus();
                CrudUI.notify('Texto organizado localmente. Revise o conteúdo antes de salvar.');
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível organizar o histórico.', 'error');
            } finally {
                organizeButton.disabled = !activeAnamnese;
            }
        };
        receitaButton.onclick = async function () {
            receitaButton.disabled = true;
            try {
                var config = await loadReceitaConfig(nomed);
                showReceitaModal(codcli, nomecli, config);
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível carregar o receituário.', 'error');
                showReceitaModal(codcli, nomecli, {});
            } finally {
                receitaButton.disabled = false;
            }
        };
        cancelButton.onclick = function () {
            clearTimeout(anamneseSearchTimer);
            form.reset();
            form.querySelector('[name="dtvisita"]').value = localToday();
            anamneses = [];
            anamneseList.innerHTML = '';
            anamneseAddButton.disabled = true;
            activeAnamnese = null;
            organizeButton.disabled = true;
            organizationReview.hidden = true;
            form.hidden = true;
            dialog.classList.remove('historico-editing');
            includeButton.disabled = false;
            editingConsultation = null;
            submitButton.querySelector('span').textContent = ' Salvar';
            alterButton.disabled = !modal.querySelector('.historico-item-check:checked');
        };
        form.onsubmit = async function (event) {
            event.preventDefault();
            submitButton.disabled = true;
            try {
                var values = new FormData(form);
                var targetUrl = editingConsultation
                    ? '/api/consultas-paciente/itens/' + encodeURIComponent(editingConsultation.cod)
                    : '/api/consultas-paciente/itens';
                var result = await api(targetUrl, editingConsultation ? 'PUT' : 'POST', {
                    codpac: codcli,
                    dtvisita: values.get('dtvisita'),
                    historico: values.get('historico')
                });
                var visitDate = String(values.get('dtvisita') || '');
                if (patient) patient.datult = visitDate;
                var updatedPatient = patient;
                if (controller) {
                    try {
                        await controller.reload();
                        updatedPatient = controller.find(codcli) || patient;
                    } catch (reloadError) {
                        console.warn('Histórico salvo, mas a lista de pacientes não foi recarregada.', reloadError);
                    }
                }
                CrudUI.notify(result.message || (editingConsultation ? 'Histórico alterado com sucesso.' : 'Histórico incluído com sucesso.'));
                closeHistoricoModal();
                window.abrirHistoricoPaciente(codcli, nomecli, updatedPatient || patient);
            } catch (error) {
                CrudUI.notify(error.message || 'Erro ao salvar histórico.', 'error');
                submitButton.disabled = false;
            }
        };
        modal.querySelector('.historico-close').onclick = closeHistoricoModal;
        modal.onclick = function (event) {
            if (event.target === modal) closeHistoricoModal();
        };
    }

    function closeExamModal() {
        var modal = document.getElementById('paciente-exame-modal');
        if (modal) modal.remove();
    }

    function imageFileData(file) {
        if (!file) return Promise.resolve('');
        var allowedTypes = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ];
        if (allowedTypes.indexOf(String(file.type || '').toLowerCase()) === -1) {
            return Promise.reject(new Error('Selecione um documento JPG, PNG, GIF, WebP, PDF, DOC ou DOCX.'));
        }
        if (file.size > 10 * 1024 * 1024) {
            return Promise.reject(new Error('O documento deve ter no máximo 10 MB.'));
        }
        return new Promise(function (resolve, reject) {
            var reader = new FileReader();
            reader.onload = function () { resolve(String(reader.result || '')); };
            reader.onerror = function () { reject(new Error('Não foi possível ler o documento.')); };
            reader.readAsDataURL(file);
        });
    }

    function showExamModal(patient) {
        if (window.MedsoftProfileViews && !window.MedsoftProfileViews.exame) {
            CrudUI.notify('Seu perfil não permite visualizar o histórico de exames.', 'error');
            return;
        }
        closeExamModal();
        var patientId = patient.codcli;
        var baseUrl = '/api/pacientes/' + encodeURIComponent(patientId) + '/exames';
        var modal = document.createElement('div');
        modal.id = 'paciente-exame-modal';
        modal.className = 'historico-modal exame-modal';
        modal.innerHTML =
            '<div class="historico-dialog exame-dialog" role="dialog" aria-modal="true" aria-labelledby="exame-titulo">' +
            '<div class="historico-header"><div><h3 id="exame-titulo">Exames de ' +
            CrudUI.escapeHtml(patient.nomecli || '') + '</h3><span>Documentos e resultados vinculados ao paciente</span></div>' +
            '<div class="historico-header-actions">' +
            '<button type="button" class="crud-button exame-include"><i class="fa fa-plus"></i><span> Incluir exame</span></button>' +
            '<button type="button" class="historico-close exame-close" title="Fechar">&times;</button></div></div>' +
            '<form class="exame-form" hidden>' +
            '<input type="hidden" name="idexame">' +
            '<label class="crud-field exame-name"><span>Nome</span><input class="crud-input" name="nome" maxlength="20" required></label>' +
            '<label class="crud-field"><span>Data</span><input class="crud-input" type="date" name="data" required></label>' +
            '<div class="crud-field exame-image-field"><label for="exame-imagem">Documentos</label>' +
            '<input class="crud-input" id="exame-imagem" type="file" name="imagem" accept="image/jpeg,image/png,image/gif,image/webp,application/pdf,.doc,.docx">' +
            '<div class="exame-image-preview-wrap"><img class="exame-image-preview" alt="Prévia do exame" hidden>' +
            '<span class="exame-image-empty">Nenhum documento selecionado</span></div>' +
            '<label class="exame-remove-image"><input type="checkbox" name="remover_imagem"> Remover documento atual</label></div>' +
            '<label class="crud-field exame-observation"><span>Observação</span>' +
            '<textarea class="crud-input" name="observacao" rows="4" maxlength="300" placeholder="Observações sobre o exame"></textarea></label>' +
            '<div class="historico-form-actions"><button type="button" class="crud-button crud-button-secondary exame-form-cancel">Cancelar</button>' +
            '<button type="submit" class="crud-button"><i class="fa fa-check"></i><span> Salvar</span></button></div></form>' +
            '<div class="exame-list"><div class="crud-loading">Carregando...</div></div></div>';
        document.body.appendChild(modal);

        var form = modal.querySelector('.exame-form');
        var list = modal.querySelector('.exame-list');
        var imageInput = form.querySelector('[name="imagem"]');
        var imagePreview = form.querySelector('.exame-image-preview');
        var imageEmpty = form.querySelector('.exame-image-empty');
        var exams = [];

        function imageUrl(examId) {
            return baseUrl + '/' + encodeURIComponent(examId) + '/imagem';
        }

        function resetForm() {
            form.reset();
            form.querySelector('[name="idexame"]').value = '';
            form.querySelector('[name="data"]').value = localToday();
            imagePreview.onerror = null;
            imagePreview.hidden = true;
            imagePreview.removeAttribute('src');
            imageEmpty.textContent = 'Nenhum documento selecionado';
            imageEmpty.hidden = false;
            form.hidden = true;
        }

        function showForm(exam) {
            resetForm();
            form.hidden = false;
            if (exam) {
                form.querySelector('[name="idexame"]').value = exam.id;
                form.querySelector('[name="nome"]').value = exam.nome || '';
                form.querySelector('[name="data"]').value = exam.data || localToday();
                form.querySelector('[name="observacao"]').value = exam.observacao || '';
                if (exam.tem_imagem) {
                    imageEmpty.textContent = 'Documento atual anexado';
                    imagePreview.onerror = function () {
                        imagePreview.hidden = true;
                        imagePreview.removeAttribute('src');
                        imageEmpty.hidden = false;
                    };
                    imagePreview.src = imageUrl(exam.id);
                    imagePreview.hidden = false;
                    imageEmpty.hidden = true;
                }
            }
            form.querySelector('[name="nome"]').focus();
        }

        function renderExams() {
            if (!exams.length) {
                list.innerHTML = '<div class="crud-empty">Nenhum exame cadastrado para este paciente.</div>';
                return;
            }
            list.innerHTML = exams.map(function (exam) {
                var image = exam.tem_imagem
                    ? '<a class="exame-thumbnail-link exame-no-image" href="' + imageUrl(exam.id) + '" target="_blank" title="Abrir documento">' +
                      '<i class="fa fa-file-medical"></i><span>Documento</span></a>'
                    : '<div class="exame-no-image"><i class="fa fa-file"></i><span>Sem documento</span></div>';
                return '<article class="exame-card">' + image + '<div class="exame-card-main"><strong>' +
                    CrudUI.escapeHtml(exam.nome) + '</strong><span>Data: ' + CrudUI.escapeHtml(formatDateBr(exam.data)) +
                    '</span>' + (exam.observacao ? '<span>Observação: ' +
                    CrudUI.escapeHtml(exam.observacao) + '</span>' : '') + '</div>' +
                    '<div class="crud-actions"><button type="button" class="crud-button crud-button-secondary" data-exam-edit="' +
                    exam.id + '"><i class="fa fa-pencil"></i><span class="crud-button-label"> Alterar</span></button>' +
                    '<button type="button" class="crud-button crud-button-danger" data-exam-delete="' + exam.id +
                    '"><i class="fa fa-trash"></i><span class="crud-button-label"> Excluir</span></button></div></article>';
            }).join('');
        }

        async function loadExams() {
            list.innerHTML = '<div class="crud-loading">Carregando...</div>';
            try {
                var data = await api(baseUrl, 'GET');
                exams = data.exames || [];
                renderExams();
            } catch (error) {
                list.innerHTML = '<div class="crud-error">' + CrudUI.escapeHtml(error.message) + '</div>';
            }
        }

        imageInput.onchange = function () {
            var file = imageInput.files && imageInput.files[0];
            if (!file) return;
            imageFileData(file).then(function (value) {
                if (String(file.type || '').toLowerCase().indexOf('image/') === 0) {
                    imagePreview.src = value;
                    imagePreview.hidden = false;
                    imageEmpty.hidden = true;
                } else {
                    imagePreview.hidden = true;
                    imagePreview.removeAttribute('src');
                    imageEmpty.textContent = file.name;
                    imageEmpty.hidden = false;
                }
                form.querySelector('[name="remover_imagem"]').checked = false;
            }).catch(function (error) {
                imageInput.value = '';
                CrudUI.notify(error.message, 'error');
            });
        };
        modal.querySelector('.exame-include').onclick = function () { showForm(null); };
        modal.querySelector('.exame-form-cancel').onclick = resetForm;
        modal.querySelector('.exame-close').onclick = closeExamModal;
        modal.onclick = function (event) { if (event.target === modal) closeExamModal(); };
        list.onclick = async function (event) {
            var edit = event.target.closest('[data-exam-edit]');
            var deletion = event.target.closest('[data-exam-delete]');
            if (edit) {
                showForm(exams.find(function (exam) { return String(exam.id) === edit.dataset.examEdit; }));
            }
            if (deletion) {
                var exam = exams.find(function (item) { return String(item.id) === deletion.dataset.examDelete; });
                if (!exam || !window.confirm('Excluir o exame ' + exam.nome + '?')) return;
                try {
                    var result = await api(baseUrl + '/' + encodeURIComponent(exam.id), 'DELETE');
                    CrudUI.notify(result.message || 'Exame excluído com sucesso.');
                    await loadExams();
                } catch (error) {
                    CrudUI.notify(error.message, 'error');
                }
            }
        };
        form.onsubmit = async function (event) {
            event.preventDefault();
            var submit = form.querySelector('[type="submit"]');
            submit.disabled = true;
            try {
                var examId = form.querySelector('[name="idexame"]').value;
                var file = imageInput.files && imageInput.files[0];
                var payload = {
                    nome: form.querySelector('[name="nome"]').value,
                    data: form.querySelector('[name="data"]').value,
                    observacao: form.querySelector('[name="observacao"]').value,
                    remover_imagem: form.querySelector('[name="remover_imagem"]').checked
                };
                if (file) payload.imagem = await imageFileData(file);
                var result = await api(
                    examId ? baseUrl + '/' + encodeURIComponent(examId) : baseUrl,
                    examId ? 'PUT' : 'POST',
                    payload
                );
                CrudUI.notify(result.message || 'Exame salvo com sucesso.');
                resetForm();
                await loadExams();
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível salvar o exame.', 'error');
            } finally {
                submit.disabled = false;
            }
        };
        resetForm();
        loadExams();
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.codcli; },
            createTitle: 'Incluir paciente',
            editTitle: 'Alterar paciente',
            emptyMessage: 'Nenhum paciente encontrado.',
            hasComplement: true,
            pageCount: 3,
            complementDisabled: function (item) { return !item; },
            complementHeader: function (item) {
                return item && item.nomecli ? 'Paciente: ' + item.nomecli : '';
            },
            keepOpenAfterCreate: true,
            itemFromCreate: function (values, result) {
                return {
                    codcli: result.id,
                    nomecli: values.nome,
                    nomed: values.nomed,
                    telefone: values.telefone,
                    nomeplano1: values.plano,
                    email: values.email,
                    ativo: values.ativo !== 'N',
                    nomeplano2: values.plano2
                };
            },
            beforeOpen: loadFormOptions,
            onFormReady: setupCepLookup,
            fields: fields,
            renderItem: renderItem,
            list: async function () {
                var term = searchTerm();
                var field = searchField();
                if (!term) throw new Error('Digite o valor que deseja buscar.');
                var data = await api('/api/consulta-paciente', 'POST', {termo: term, campo: field});
                return data.pacientes || [];
            },
            create: function (values) {
                return api('/api/pacientes/itens', 'POST', {
                    nome: values.nome,
                    nomed: values.nomed,
                    telefone: values.telefone,
                    plano: values.plano,
                    email: values.email,
                    ativo: values.ativo,
                    nascimento: values.nascimento,
                    cpf: values.cpf,
                    rg: values.rg,
                    sexo: values.sexo,
                    endereco: values.endereco,
                    uf: values.uf,
                    cep: values.cep,
                    cidade: values.cidade,
                    bairro: values.bairro,
                    estado_civil: values.estado_civil,
                    cor: values.cor,
                    foto: values.foto,
                    cont1: values.cont1,
                    validade_carteira1: values.validade_carteira1,
                    nompai: values.nompai,
                    nommae: values.nommae,
                    profcli: values.profcli,
                    natcli: values.natcli,
                    recom: values.recom,
                    plano2: values.plano2,
                    datult: values.datult,
                    matricula: values.matricula,
                    obs: values.obs
                });
            },
            update: function (item, values) {
                return api('/api/pacientes/itens/' + item.codcli, 'PUT', {
                    nome: values.nome,
                    nomed: values.nomed,
                    telefone: values.telefone,
                    plano: values.plano,
                    email: values.email,
                    ativo: values.ativo,
                    nascimento: values.nascimento,
                    cpf: values.cpf,
                    rg: values.rg,
                    sexo: values.sexo,
                    endereco: values.endereco,
                    uf: values.uf,
                    cep: values.cep,
                    cidade: values.cidade,
                    bairro: values.bairro,
                    estado_civil: values.estado_civil,
                    cor: values.cor,
                    foto: values.foto,
                    cont1: values.cont1,
                    validade_carteira1: values.validade_carteira1,
                    nompai: values.nompai,
                    nommae: values.nommae,
                    profcli: values.profcli,
                    natcli: values.natcli,
                    recom: values.recom,
                    plano2: values.plano2,
                    datult: values.datult,
                    matricula: values.matricula,
                    obs: values.obs
                });
            },
            delete: function (item) { return api('/api/pacientes/itens/' + item.codcli, 'DELETE'); },
            confirmDelete: function (item) {
                return 'Marcar o paciente ' + item.nomecli + ' como inativo?';
            },
            onAction: function (action, item) {
                if (action === 'history' && item && window.abrirHistoricoPaciente) {
                    window.abrirHistoricoPaciente(item.codcli, item.nomecli, item);
                }
                if (action === 'exams' && item) {
                    showExamModal(item);
                }
                if (action === 'complement' && item && controller) {
                    controller.openEditor(item, {initialPage: 2});
                }
                if (action === 'extra' && item && controller) {
                    controller.openEditor(item, {initialPage: 3});
                }
            }
        });
    }

    function init() {
        var page = document.getElementById('paciente-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var searchInput = document.getElementById('paciente-busca');
        var searchFieldInput = document.getElementById('paciente-campo-busca');
        
        controller = createController().mount({
            root: page,
            list: document.getElementById('paciente-result'),
            includeButton: document.getElementById('paciente-include')
        });
        
        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        if (searchFieldInput) {
            searchFieldInput.onchange = function () {
                var placeholders = {
                    nome: 'Digite o nome',
                    sobrenome: 'Digite o sobrenome',
                    cpf: 'Digite o CPF',
                    telefone: 'Digite o telefone'
                };
                searchInput.placeholder = placeholders[searchFieldInput.value] || 'Digite o paciente';
                searchInput.value = '';
                searchInput.focus();
            };
        }
        loadPlanOptions().catch(function () {
            CrudUI.notify('Não foi possível carregar os planos cadastrados.', 'error');
        });
        
        // Permitir buscar pressionando Enter
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') controller.reload();
        });

        if (window.pacienteAgendaPendente) {
            searchInput.value = window.pacienteAgendaPendente;
            window.pacienteAgendaPendente = '';
            controller.reload();
        }
    }

    window.PacienteCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

    // Função para abrir histórico do paciente
    window.abrirHistoricoPaciente = function(codcli, nomecli, patient) {
        if (window.MedsoftProfileViews && !window.MedsoftProfileViews.historico) {
            CrudUI.notify('Seu perfil não permite visualizar o histórico clínico.', 'error');
            return;
        }
        if (typeof patient === 'string') patient = {nomed: patient};
        patient = patient || {};
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
            if (!data.success) throw new Error(data.message || 'Erro ao buscar historico.');
            showHistoricoModal(codcli, nomecli, data.consultas || [], patient);
        })
        .catch(err => CrudUI.notify('Erro ao buscar histórico: ' + err.message, 'error'));
    };
}());
