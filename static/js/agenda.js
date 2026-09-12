(function () {
    var controller;
    var planoOptions = [{value: '', label: ''}];
    var procedimentoOptions = [{value: '', label: ''}];
    var profissionalOptions = [{value: '', label: ''}];
    var patientOptions = [{value: '', label: '', patient: null}];
    var draftItem = null;
    var confirmationPending = {};

    function headers() {
        return {
            'Content-Type': 'application/json',
            'X-DB-PATH': localStorage.getItem('db_path') || '',
            'X-CLINICA-ID': localStorage.getItem('codclin') || localStorage.getItem('idempresa') || ''
        };
    }

    function api(url, method, body) {
        return CrudUI.request(url, {
            method: method,
            headers: headers(),
            body: body ? JSON.stringify(body) : undefined
        });
    }

    function selectedDate() {
        return document.getElementById('agenda-date').value;
    }

    function selectedProfessional() {
        var select = document.getElementById('agenda-profissional');
        return select ? select.value : '';
    }

    function patientSearchTerm() {
        var input = document.getElementById('agenda-paciente');
        return input ? input.value.trim() : '';
    }

    function selectedInterval() {
        var select = document.getElementById('agenda-interval');
        return select ? select.value : '30';
    }

    function selectedView() {
        var select = document.getElementById('agenda-view');
        return select ? select.value : 'dia';
    }

    function localDate(value) {
        var parts = String(value || '').split('-').map(Number);
        return parts.length === 3 ? new Date(parts[0], parts[1] - 1, parts[2]) : new Date();
    }

    function isoDate(value) {
        return value.getFullYear() + '-' + String(value.getMonth() + 1).padStart(2, '0') + '-' +
            String(value.getDate()).padStart(2, '0');
    }

    function addDays(value, amount) {
        var result = new Date(value.getFullYear(), value.getMonth(), value.getDate());
        result.setDate(result.getDate() + amount);
        return result;
    }

    function calendarRange() {
        var reference = localDate(selectedDate());
        var view = selectedView();
        if (view === 'dia') {
            return {start: reference, end: reference};
        }
        if (view === 'ano') {
            return {start: new Date(reference.getFullYear(), 0, 1), end: new Date(reference.getFullYear(), 11, 31)};
        }
        if (view === 'mes') {
            return {start: new Date(reference.getFullYear(), reference.getMonth(), 1),
                end: new Date(reference.getFullYear(), reference.getMonth() + 1, 0)};
        }
        var offset = (reference.getDay() + 6) % 7;
        var start = addDays(reference, -offset);
        return {start: start, end: addDays(start, 6)};
    }

    function appointmentsByDate(items) {
        return (items || []).reduce(function (groups, item) {
            var value = String(item.data || '').trim();
            var parts = value.split('/');
            var date = parts.length === 3
                ? parts[2] + '-' + parts[1].padStart(2, '0') + '-' + parts[0].padStart(2, '0')
                : value.slice(0, 10);
            if (!groups[date]) groups[date] = [];
            groups[date].push(item);
            return groups;
        }, {});
    }

    function appointmentMarks(items, compact) {
        if (!items || !items.length) return '';
        if (compact) return '<span class="agenda-calendar-count">' + items.length + '</span>';
        return '<div class="agenda-calendar-marks">' + items.slice(0, 4).map(function (item) {
            return '<span title="' + CrudUI.escapeHtml((item.hora || '') + ' ' + (item.paciente || '')) + '">' +
                CrudUI.escapeHtml(item.hora || '') + ' ' + CrudUI.escapeHtml(item.paciente || '') + '</span>';
        }).join('') + (items.length > 4 ? '<small>+' + (items.length - 4) + ' marcações</small>' : '') + '</div>';
    }

    function calendarDay(date, groups, outside, compact) {
        var key = isoDate(date);
        var selected = key === selectedDate() ? ' agenda-calendar-selected' : '';
        return '<button type="button" class="agenda-calendar-day' + (outside ? ' agenda-calendar-outside' : '') +
            selected + '" data-calendar-date="' + key + '"><strong>' + date.getDate() + '</strong>' +
            appointmentMarks(groups[key], compact) + '</button>';
    }

    function renderWeekCalendar(groups, range) {
        var days = [];
        for (var index = 0; index < 7; index++) days.push(addDays(range.start, index));
        return '<div class="agenda-calendar-heading">Semana de ' + range.start.toLocaleDateString('pt-BR') +
            ' a ' + range.end.toLocaleDateString('pt-BR') + '</div><div class="agenda-week-grid">' +
            days.map(function (date) {
                return '<section class="agenda-week-day"><h4>' +
                    date.toLocaleDateString('pt-BR', {weekday: 'short', day: '2-digit', month: '2-digit'}) + '</h4>' +
                    calendarDay(date, groups, false, false) + '</section>';
            }).join('') + '</div>';
    }

    function monthGrid(year, month, groups, compact) {
        var first = new Date(year, month, 1);
        var start = addDays(first, -((first.getDay() + 6) % 7));
        var cells = [];
        for (var index = 0; index < 42; index++) {
            var date = addDays(start, index);
            cells.push(calendarDay(date, groups, date.getMonth() !== month, compact));
        }
        return '<div class="agenda-month-weekdays"><span>Seg</span><span>Ter</span><span>Qua</span><span>Qui</span>' +
            '<span>Sex</span><span>Sáb</span><span>Dom</span></div><div class="agenda-month-grid">' + cells.join('') + '</div>';
    }

    function renderCalendar(items) {
        var container = document.getElementById('agenda-calendar');
        var reference = localDate(selectedDate());
        var groups = appointmentsByDate(items);
        var view = selectedView();
        if (view === 'semana') {
            container.innerHTML = renderWeekCalendar(groups, calendarRange());
        } else if (view === 'mes') {
            container.innerHTML = '<div class="agenda-calendar-heading">' +
                reference.toLocaleDateString('pt-BR', {month: 'long', year: 'numeric'}) + '</div>' +
                monthGrid(reference.getFullYear(), reference.getMonth(), groups, false);
        } else {
            container.innerHTML = '<div class="agenda-calendar-heading">Ano de ' + reference.getFullYear() + '</div>' +
                '<div class="agenda-year-grid">' + Array.from({length: 12}, function (_item, month) {
                    return '<section class="agenda-year-month"><h4>' +
                        new Date(reference.getFullYear(), month, 1).toLocaleDateString('pt-BR', {month: 'long'}) +
                        '</h4>' + monthGrid(reference.getFullYear(), month, groups, true) + '</section>';
                }).join('') + '</div>';
        }
    }

    async function loadCalendar() {
        if (selectedView() === 'dia') {
            document.getElementById('agenda-calendar').innerHTML = '';
            return;
        }
        var range = calendarRange();
        var data = await api('/api/relatorios/agenda', 'POST', {
            data_inicio: isoDate(range.start),
            data_fim: isoDate(range.end),
            profissional: selectedProfessional()
        });
        var term = patientSearchTerm().toLocaleUpperCase('pt-BR');
        var items = (data.agendamentos || []).filter(function (item) {
            return !term || String(item.paciente || '').toLocaleUpperCase('pt-BR').indexOf(term) !== -1;
        });
        renderCalendar(items);
    }

    function ensureAgendaToolbarLayout() {
        var page = document.getElementById('agenda-page');
        var toolbar = page && page.querySelector('.crud-toolbar');
        var button = document.getElementById('btn-ok');
        if (!page || !toolbar || !button) return;

        toolbar.classList.add('agenda-search-toolbar');

        if (!document.getElementById('agenda-paciente')) {
            var patientField = document.createElement('div');
            patientField.className = 'crud-field agenda-paciente-busca-field';
            patientField.innerHTML =
                '<label for="agenda-paciente">Paciente</label>' +
                '<input class="crud-input" type="text" id="agenda-paciente" placeholder="Digite o paciente">';
            toolbar.insertBefore(patientField, button);
        }

        var interval = document.getElementById('agenda-interval');
        var intervalField = interval && interval.closest('.crud-field');
        if (intervalField) intervalField.classList.add('agenda-interval-field');

        var row = toolbar.closest('.agenda-toolbar-row');
        if (!row) {
            row = document.createElement('div');
            row.className = 'agenda-toolbar-row';
            toolbar.parentNode.insertBefore(row, toolbar);
            row.appendChild(toolbar);
        }
        if (intervalField && intervalField.parentNode !== row) {
            row.appendChild(intervalField);
        }
    }

    function today() {
        var date = new Date();
        return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' +
            String(date.getDate()).padStart(2, '0');
    }

    function statusOptions() {
        return [
            {value: 'AT', label: 'AT - Atendido'},
            {value: 'AG', label: 'AG - Agendado'},
            {value: 'CO', label: 'CO - Confirmado'},
            {value: 'SC', label: 'SC - Solicitado confirmação'}
        ];
    }

    function statusLabel(value) {
        var status = statusOptions().find(function (option) { return option.value === value; });
        return status ? status.label : (value || 'Sem status');
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
        renderProfessionalFilter();
    }

    async function loadProcedimentoOptions() {
        var data = await api('/api/procedimentos', 'POST', {termo: ''});
        procedimentoOptions = [{value: '', label: ''}].concat((data.procedimentos || []).map(function (procedimento) {
            var descricao = procedimento.descricao || '';
            var plano = procedimento.plano ? ' - ' + procedimento.plano : '';
            return {value: descricao, label: descricao + plano};
        }).filter(function (option) { return option.value; }));
    }

    async function loadPatientOptions() {
        var data = await api('/api/pacientes/opcoes', 'POST', {termo: ''});
        patientOptions = [{value: '', label: '', patient: null}].concat(
            (data.pacientes || []).map(function (patient) {
                return {
                    value: String(patient.id),
                    label: patient.nome || '',
                    patient: patient
                };
            }).filter(function (option) { return option.value && option.label; })
        );
    }

    async function loadFormOptions() {
        await Promise.all([loadPlanOptions(), loadProcedimentoOptions(), loadProfissionalOptions(), loadPatientOptions()]);
    }

    function planOptionsFor(item) {
        var currentValue = (item && item.NOMEPLANO) || '';
        var options = planoOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function profissionalOptionsFor(item) {
        var currentValue = (item && item.NOMED) || '';
        var options = profissionalOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function procedimentoOptionsFor(item) {
        var currentValue = (item && item.PROCED) || '';
        var options = procedimentoOptions.slice();
        if (currentValue && !options.some(function (option) { return option.value === currentValue; })) {
            options.push({value: currentValue, label: currentValue});
        }
        return options;
    }

    function normalizeName(value) {
        return String(value || '').trim().toLocaleUpperCase('pt-BR');
    }

    function patientOptionsFor(item) {
        var options = patientOptions.slice();
        var currentName = (item && item.NOMEPACI) || '';
        if (!currentName) return {options: options, value: ''};
        var expected = normalizeName(currentName);
        var match = options.find(function (option) {
            return option.patient && normalizeName(option.patient.nome) === expected;
        });
        if (match) return {options: options, value: match.value};
        var legacyValue = 'nome:' + currentName;
        options.push({
            value: legacyValue,
            label: currentName + ' (cadastro não localizado)',
            patient: {id: null, nome: currentName}
        });
        return {options: options, value: legacyValue};
    }

    function renderProfessionalFilter() {
        var select = document.getElementById('agenda-profissional');
        if (!select) return;
        var currentValue = select.value;
        select.innerHTML = profissionalOptions.map(function (option) {
            return '<option value="' + CrudUI.escapeHtml(option.value || '') + '">' +
                CrudUI.escapeHtml(option.label || '') + '</option>';
        }).join('');
        if (currentValue && profissionalOptions.some(function (option) { return option.value === currentValue; })) {
            select.value = currentValue;
        } else {
            var storedProfessional = localStorage.getItem('nome_medico') || '';
            if (storedProfessional && profissionalOptions.some(function (option) { return option.value === storedProfessional; })) {
                select.value = storedProfessional;
            } else {
                var firstProfessional = profissionalOptions.find(function (option) { return option.value; });
                select.value = firstProfessional ? firstProfessional.value : '';
            }
        }
    }

    function renderAvailability(data) {
        var container = document.getElementById('agenda-availability');
        if (!container) return;
        if (!selectedProfessional()) {
            container.innerHTML = '<div class="agenda-availability-empty">Selecione um Prof. Saúde para visualizar os horários do dia.</div>';
            return;
        }
        if (!selectedDate()) {
            container.innerHTML = '<div class="agenda-availability-empty">Selecione uma data para visualizar os horários do dia.</div>';
            return;
        }
        var slots = data && data.horarios ? data.horarios : [];
        if (!slots.length) {
            container.innerHTML = '<div class="agenda-availability-empty">Nenhum horário de atendimento cadastrado para este dia.</div>';
            return;
        }
        container.innerHTML = '<div class="agenda-availability-header">' +
            '<strong>Horários do dia</strong>' +
            '<span>Intervalo de ' + CrudUI.escapeHtml(data.intervalo || selectedInterval() || 30) + ' min</span>' +
            '</div><div class="agenda-slots">' + slots.map(function (slot) {
                var className = slot.disponivel ? 'agenda-slot agenda-slot-free' : 'agenda-slot agenda-slot-busy';
                var attrs = slot.disponivel ? ' data-slot-time="' + CrudUI.escapeHtml(slot.hora) + '"' : ' disabled';
                var title = slot.disponivel ? 'Agendar ' + slot.hora : 'Ocupado por ' + (slot.paciente || 'paciente');
                var detail = slot.disponivel ? 'Livre' : (slot.paciente || statusLabel(slot.status));
                return '<button type="button" class="' + className + '"' + attrs + ' title="' +
                    CrudUI.escapeHtml(title) + '"><strong>' + CrudUI.escapeHtml(slot.hora) +
                    '</strong><span>' + CrudUI.escapeHtml(detail) + '</span></button>';
            }).join('') + '</div>';
    }

    async function loadAvailability() {
        if (!selectedDate() || !selectedProfessional()) {
            renderAvailability(null);
            return;
        }
        try {
            var data = await api('/api/agenda/disponibilidade', 'POST', {
                data: selectedDate(),
                profissional: selectedProfessional(),
                intervalo: selectedInterval()
            });
            renderAvailability(data);
        } catch (error) {
            document.getElementById('agenda-availability').innerHTML =
                '<div class="crud-error">' + CrudUI.escapeHtml(error.message) + '</div>';
        }
    }

    function fields(item) {
        item = item || draftItem || {};
        var patients = patientOptionsFor(item);
        return [
            {name: 'data', label: 'Data', type: 'date', value: item.DATACONS || selectedDate(), required: true},
            {name: 'hora', label: 'Horário', type: 'time', value: item.HORACONS || '', required: true},
            {
                name: 'paciente_id',
                label: 'Paciente',
                type: 'select',
                value: patients.value,
                options: patients.options,
                required: true,
                wide: true,
                className: 'agenda-patient-field'
            },
            {
                name: 'profissional',
                label: 'Prof. Saúde',
                type: 'select',
                value: item.NOMED || selectedProfessional() || '',
                options: profissionalOptionsFor(item),
                required: true,
                wide: true
            },
            {
                name: 'telefone', label: 'Telefone', type: 'tel', value: item.TELEFONE || '',
                mask: 'phone-br', placeholder: '(99)99999-9999', maxLength: 14,
                inputMode: 'numeric'
            },
            {
                name: 'email', label: 'E-mail', type: 'email', value: item.EMAIL || '',
                placeholder: 'paciente@exemplo.com', maxLength: 120
            },
            {
                name: 'plano',
                label: 'Plano',
                type: 'select',
                value: item.NOMEPLANO || '',
                options: planOptionsFor(item)
            },
            {
                name: 'status',
                label: 'Status',
                type: 'select',
                value: item.ATEND || 'AG',
                options: statusOptions(),
                required: true
            },
            {
                name: 'procedimento',
                label: 'Procedimento',
                type: 'select',
                value: item.PROCED || '',
                options: procedimentoOptionsFor(item),
                wide: true
            },
            {
                name: 'observacao',
                label: 'Observação',
                value: item.OBSERVACAO || '',
                type: 'textarea',
                rows: 3,
                maxLength: 200,
                wide: true
            }
        ];
    }

    function selectedPatient(value) {
        return patientOptions.find(function (option) {
            return String(option.value) === String(value);
        });
    }

    function setFormValue(backdrop, fieldName, value) {
        var field = backdrop.querySelector('[name="' + fieldName + '"]');
        if (!field) return;
        field.value = value || '';
        field.dispatchEvent(new Event('input', {bubbles: true}));
        field.dispatchEvent(new Event('change', {bubbles: true}));
    }

    function applyPatientToForm(backdrop, patient) {
        if (!patient) return;
        setFormValue(backdrop, 'telefone', patient.telefone || '');
        setFormValue(backdrop, 'email', patient.email || '');
        setFormValue(backdrop, 'plano', patient.plano || '');
    }

    function addPatientToAgendaSelect(backdrop, patient) {
        var option = {
            value: String(patient.id),
            label: patient.nome,
            patient: patient
        };
        patientOptions.push(option);
        var select = backdrop.querySelector('[name="paciente_id"]');
        if (!select) return;
        var element = document.createElement('option');
        element.value = option.value;
        element.textContent = option.label;
        select.appendChild(element);
        select.value = option.value;
        applyPatientToForm(backdrop, patient);
    }

    function openQuickPatientForm(agendaBackdrop) {
        CrudUI.openForm({
            title: 'Cadastrar paciente',
            formClass: 'agenda-quick-patient-form',
            fields: [
                {name: 'nome', label: 'Nome', value: '', required: true, wide: true},
                {
                    name: 'telefone', label: 'Telefone', value: '', type: 'tel',
                    mask: 'phone-br', placeholder: '(99)99999-9999', maxLength: 14,
                    inputMode: 'numeric'
                },
                {name: 'email', label: 'E-mail', value: '', type: 'email', maxLength: 120},
                {
                    name: 'plano', label: 'Plano', type: 'select', value: '',
                    options: planoOptions
                }
            ],
            onSubmit: async function (values) {
                var result = await api('/api/pacientes/itens', 'POST', values);
                var patient = {
                    id: result.id,
                    nome: values.nome,
                    telefone: values.telefone || '',
                    email: values.email || '',
                    plano: values.plano || ''
                };
                addPatientToAgendaSelect(agendaBackdrop, patient);
                CrudUI.notify(result.message || 'Paciente incluído com sucesso.');
            }
        });
    }

    function setupPatientPicker(backdrop) {
        var select = backdrop.querySelector('[name="paciente_id"]');
        if (!select) return;
        var field = select.closest('.agenda-patient-field');
        var picker = document.createElement('div');
        picker.className = 'agenda-patient-picker';
        select.parentNode.insertBefore(picker, select);
        picker.appendChild(select);
        var addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.className = 'crud-button crud-button-secondary agenda-patient-add';
        addButton.innerHTML = '<i class="fa fa-user-plus"></i><span> Novo paciente</span>';
        addButton.onclick = function () { openQuickPatientForm(backdrop); };
        picker.appendChild(addButton);
        select.addEventListener('change', function () {
            var option = selectedPatient(select.value);
            applyPatientToForm(backdrop, option && option.patient);
        });
        if (field) field.classList.add('crud-field-wide');
    }

    function setupAgendaForm(backdrop, item) {
        setupPatientPicker(backdrop);
        if (item && item.CODAGEND !== undefined && item.CODAGEND !== null) {
            backdrop.dataset.agendaId = String(item.CODAGEND);
        }
    }

    function syncOpenAgendaStatus() {
        var backdrop = document.querySelector('.crud-modal-backdrop[data-agenda-id]');
        if (!backdrop || !controller) return;
        var item = controller.find(backdrop.dataset.agendaId);
        var status = backdrop.querySelector('[name="status"]');
        if (item && status && item.ATEND) status.value = item.ATEND;
    }

    function appointmentPayload(values) {
        var payload = Object.assign({}, values);
        var option = selectedPatient(payload.paciente_id);
        if (option && option.patient) {
            payload.paciente = option.patient.nome;
            payload.codpac = option.patient.id;
        }
        else if (String(payload.paciente_id || '').indexOf('nome:') === 0) {
            payload.paciente = String(payload.paciente_id).slice(5);
        }
        delete payload.paciente_id;
        return payload;
    }

    function renderItem(item) {
        return '<article class="crud-card">' +
            '<div class="crud-card-header"><span class="crud-time"><i class="fa fa-clock"></i> ' +
            CrudUI.escapeHtml(item.HORACONS) + '</span>' +
            '<div class="crud-card-main"><div class="crud-card-title">' + CrudUI.escapeHtml(item.NOMEPACI) +
            '</div></div></div><div class="crud-card-details">' +
            '<span><i class="fa fa-user-doctor"></i> ' + CrudUI.escapeHtml(item.NOMED || 'Sem profissional') + '</span>' +
            '<span><i class="fa fa-circle-check"></i> ' + CrudUI.escapeHtml(statusLabel(item.ATEND)) + '</span>' +
            '<span><i class="fa fa-phone"></i> ' + CrudUI.escapeHtml(item.TELEFONE || 'Sem telefone') + '</span>' +
            '<span><i class="fa fa-id-card"></i> ' + CrudUI.escapeHtml(item.NOMEPLANO || 'Sem plano') + '</span>' +
            '<span><i class="fa fa-stethoscope"></i> ' + CrudUI.escapeHtml(item.PROCED || 'Sem procedimento') + '</span>' +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-action="patient" data-crud-id="' +
            item.CODAGEND + '" title="Consultar paciente"><i class="fa fa-user"></i>' +
            '<span class="crud-button-label"> Paciente</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.CODAGEND +
            '" title="Alterar agenda de paciente"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-action="confirmation-whatsapp" data-crud-id="' +
            item.CODAGEND + '" title="Confirmação por WhatsApp">' +
            '<i class="fa-brands fa-whatsapp"></i><span class="crud-button-label"> WhatsApp</span></button>' +
            '<button class="crud-button crud-button-secondary" data-crud-action="confirmation-email" data-crud-id="' +
            item.CODAGEND + '" title="Confirmação por E-mail">' +
            '<i class="fa fa-envelope"></i><span class="crud-button-label"> E-mail</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.CODAGEND +
            '" title="Excluir agenda de paciente"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function filterAgendaItems(items) {
        var term = patientSearchTerm().toLocaleUpperCase('pt-BR');
        if (!term) return items || [];
        return (items || []).filter(function (item) {
            return String(item.NOMEPACI || '').toLocaleUpperCase('pt-BR').indexOf(term) !== -1;
        });
    }

    async function openSendConfirmationMessage(action, item) {
        var isWhatsapp = action === 'confirmation-whatsapp';
        var channel = isWhatsapp ? 'WhatsApp' : 'e-mail';
        var data = await api('/api/agenda/textos-confirmacao', 'POST', {
            tipo: isWhatsapp ? 'Z' : 'E'
        });
        var options = data.textos || [];
        if (!options.length) {
            CrudUI.notify('Nenhum texto padrão de ' + channel + ' foi cadastrado.', 'error');
            return;
        }
        CrudUI.openForm({
            title: 'Escolher mensagem de confirmação por ' + channel,
            submitLabel: 'Enviar ' + channel,
            fields: [{
                name: 'codigo_texto',
                label: 'Mensagem padrão',
                type: 'select',
                required: true,
                wide: true,
                options: [{value: '', label: 'Selecione'}].concat(options)
            }],
            onSubmit: async function (values) {
                var itemId = String(item.CODAGEND) + ':' + channel;
                if (confirmationPending[itemId]) return {close: false};
                confirmationPending[itemId] = true;
                try {
                    var endpoint = isWhatsapp
                        ? '/solicitar-confirmacao-whatsapp'
                        : '/solicitar-confirmacao-email';
                    var result = await api(
                        '/api/agenda/itens/' + encodeURIComponent(item.CODAGEND) + endpoint,
                        'POST',
                        {codigo_texto: values.codigo_texto}
                    );
                    CrudUI.notify(result.message || 'Solicitação de confirmação processada.');
                    await controller.reload();
                } catch (error) {
                    throw error;
                } finally {
                    delete confirmationPending[itemId];
                }
            }
        });
    }

    function formatWhatsappHistoryDate(value) {
        if (!value) return 'Data não informada';
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat('pt-BR', {
            dateStyle: 'short', timeStyle: 'short'
        }).format(date);
    }

    async function openWhatsappHistory(item) {
        var data = await api(
            '/api/agenda/itens/' + encodeURIComponent(item.CODAGEND) + '/mensagens-whatsapp',
            'GET'
        );
        var messages = data.mensagens || [];
        var backdrop = document.createElement('div');
        backdrop.className = 'crud-modal-backdrop';
        var history = messages.length ? messages.map(function (message) {
            var failed = message.enviado === 'Não';
            var content = message.conteudo ||
                'Mensagem enviada antes da implantação do histórico de conteúdo. O texto original não foi armazenado.';
            return '<article class="agenda-whatsapp-message' + (failed ? ' is-error' : '') + '">' +
                '<div class="agenda-whatsapp-message-meta"><strong>' +
                CrudUI.escapeHtml(formatWhatsappHistoryDate(message.datahoraenvio)) + '</strong>' +
                '<span>' + CrudUI.escapeHtml(message.destino || 'Sem destinatário') + '</span></div>' +
                '<div class="agenda-whatsapp-message-content">' + CrudUI.escapeHtml(content) + '</div>' +
                '<div class="agenda-whatsapp-message-status">' +
                (failed ? '<i class="fa fa-circle-xmark"></i> Falha: ' +
                    CrudUI.escapeHtml(message.motivoerro || 'Motivo não informado') :
                    '<i class="fa fa-check-double"></i> Enviada') + '</div></article>';
        }).join('') : '<div class="crud-empty">Nenhuma mensagem de WhatsApp foi enviada para este agendamento.</div>';
        backdrop.innerHTML = '<section class="crud-modal agenda-whatsapp-history" role="dialog" aria-modal="true">' +
            '<h3 class="crud-modal-title"><i class="fa-brands fa-whatsapp"></i> Mensagens do agendamento</h3>' +
            '<p class="agenda-whatsapp-patient">' + CrudUI.escapeHtml(item.NOMEPACI || '') + '</p>' +
            '<div class="agenda-whatsapp-history-list">' + history + '</div>' +
            '<div class="crud-modal-actions"><button type="button" class="crud-button crud-button-secondary" data-close-history>Fechar</button>' +
            '<button type="button" class="crud-button" data-new-whatsapp><i class="fa fa-paper-plane"></i> Nova mensagem</button></div>' +
            '</section>';
        function close() { backdrop.remove(); }
        backdrop.querySelector('[data-close-history]').onclick = close;
        backdrop.querySelector('[data-new-whatsapp]').onclick = function () {
            close();
            openSendConfirmationMessage('confirmation-whatsapp', item).catch(function (error) {
                CrudUI.notify(error.message || 'Não foi possível enviar a solicitação.', 'error');
            });
        };
        backdrop.addEventListener('click', function (event) { if (event.target === backdrop) close(); });
        document.body.appendChild(backdrop);
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.CODAGEND; },
            createTitle: 'Incluir agenda de paciente',
            editTitle: 'Alterar agenda de paciente',
            allowDuplicate: true,
            duplicateLabel: 'Duplicar',
            duplicateTitle: 'Duplicar agenda de paciente',
            duplicateFocusField: 'data',
            duplicateMessage: 'Agenda copiada. Informe a nova data e os demais dados, depois clique em Salvar.',
            emptyMessage: 'Nenhuma agenda de paciente encontrada.',
            beforeOpen: loadFormOptions,
            fields: fields,
            onFormReady: setupAgendaForm,
            renderItem: renderItem,
            list: async function () {
                if (!selectedDate() && !patientSearchTerm()) throw new Error('Informe uma data ou um paciente.');
                var data = await api('/api/agenda', 'POST', {
                    data: selectedDate(),
                    profissional: selectedProfessional(),
                    paciente: patientSearchTerm()
                });
                return filterAgendaItems(data.resultados || []);
            },
            create: function (values) {
                return api('/api/agenda/itens', 'POST', appointmentPayload(values));
            },
            update: function (item, values) {
                return api('/api/agenda/itens/' + item.CODAGEND, 'PUT', appointmentPayload(values));
            },
            delete: function (item) { return api('/api/agenda/itens/' + item.CODAGEND, 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir a agenda de paciente de ' + item.NOMEPACI + ' às ' + item.HORACONS + '?';
            },
            afterSave: async function (values) {
                document.getElementById('agenda-date').value = values.data;
                draftItem = null;
                await loadAvailability();
            },
            onAction: async function (action, item) {
                if (action === 'patient' && item && window.carregarTela) {
                    window.pacienteAgendaPendente = item.NOMEPACI.trim();
                    window.carregarTela('consulta_paciente.html');
                }
                if (action === 'confirmation-whatsapp' && item) {
                    try {
                        await openWhatsappHistory(item);
                    } catch (error) {
                        CrudUI.notify(error.message || 'Não foi possível consultar as mensagens.', 'error');
                    }
                }
                if (action === 'confirmation-email' && item) {
                    try {
                        await openSendConfirmationMessage(action, item);
                    } catch (error) {
                        CrudUI.notify(error.message || 'Não foi possível enviar a solicitação.', 'error');
                    }
                }
            }
        });
    }

    function init() {
        var page = document.getElementById('agenda-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';
        var pendingLogAgenda = window.agendaLogPendente || null;
        window.agendaLogPendente = null;
        ensureAgendaToolbarLayout();
        var dateInput = document.getElementById('agenda-date');
        if (pendingLogAgenda && pendingLogAgenda.data) {
            dateInput.value = pendingLogAgenda.data;
        } else if (!dateInput.value) {
            dateInput.value = today();
        }
        renderProfessionalFilter();
        var includeButton = document.getElementById('agenda-include');
        controller = createController().mount({
            root: page,
            list: document.getElementById('agenda-result'),
            includeButton: includeButton
        });
        var includeClick = includeButton.onclick;
        includeButton.onclick = function () {
            draftItem = null;
            includeClick();
        };
        async function reloadAll() {
            var hideLoading = CrudUI.showLoading('Carregando a agenda do profissional. Aguarde...');
            try {
                await Promise.all([controller.reload(), loadAvailability(), loadCalendar()]);
                syncOpenAgendaStatus();
            } finally {
                hideLoading();
            }
        }
        document.getElementById('btn-ok').onclick = reloadAll;
        dateInput.addEventListener('change', reloadAll);
        document.getElementById('agenda-profissional').addEventListener('change', reloadAll);
        document.getElementById('agenda-interval').addEventListener('change', reloadAll);
        document.getElementById('agenda-view').addEventListener('change', reloadAll);
        document.getElementById('agenda-paciente').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') reloadAll();
        });
        if (window._medsoftAgendaFocusHandler) {
            window.removeEventListener('focus', window._medsoftAgendaFocusHandler);
        }
        window._medsoftAgendaFocusHandler = function () {
            if (document.getElementById('agenda-page') === page) reloadAll();
        };
        window.addEventListener('focus', window._medsoftAgendaFocusHandler);
        if (window._medsoftAgendaStorageHandler) {
            window.removeEventListener('storage', window._medsoftAgendaStorageHandler);
        }
        window._medsoftAgendaStorageHandler = function (event) {
            if (event.key === 'medsoft-agenda-confirmed' &&
                    document.getElementById('agenda-page') === page) {
                reloadAll();
            }
        };
        window.addEventListener('storage', window._medsoftAgendaStorageHandler);
        document.getElementById('agenda-availability').addEventListener('click', function (event) {
            var slot = event.target.closest('[data-slot-time]');
            if (!slot) return;
            draftItem = {
                DATACONS: selectedDate(),
                HORACONS: slot.dataset.slotTime,
                NOMED: selectedProfessional(),
                ATEND: 'AG'
            };
            controller.openEditor();
        });
        document.getElementById('agenda-calendar').addEventListener('click', function (event) {
            var day = event.target.closest('[data-calendar-date]');
            if (!day) return;
            dateInput.value = day.dataset.calendarDate;
            reloadAll();
        });
        loadFormOptions().then(async function () {
            await reloadAll();
            if (!pendingLogAgenda) return;
            var item = controller.find(pendingLogAgenda.id);
            if (item) {
                controller.openEditor(item);
            } else {
                CrudUI.notify('O agendamento vinculado ao Log não foi encontrado.', 'error');
            }
        }).catch(function () {
            CrudUI.notify('Não foi possível carregar planos ou profissionais cadastrados.', 'error');
        }).finally(function () {
            if (window.agendaLogLoadingDone) {
                window.agendaLogLoadingDone();
                window.agendaLogLoadingDone = null;
            }
        });
    }

    window.AgendaCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
