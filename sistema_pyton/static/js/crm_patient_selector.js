(function () {
    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function valueOf(patient, names) {
        var keys = Object.keys(patient || {});
        for (var i = 0; i < names.length; i += 1) {
            var wanted = names[i].toLowerCase();
            var key = keys.find(function (item) { return item.toLowerCase().replace(/_+$/, '') === wanted; });
            if (key) return patient[key];
        }
        return '';
    }

    function patientDate(value) {
        var text = String(value || '').trim(), match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
        match = text.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        return match ? new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1])) : null;
    }

    function formatPatientDate(value) {
        var date = patientDate(value);
        if (!date || Number.isNaN(date.getTime())) return 'Não informado';
        return String(date.getDate()).padStart(2, '0') + '/' +
            String(date.getMonth() + 1).padStart(2, '0') + '/' + date.getFullYear();
    }

    function formatSex(value) {
        var sex = String(value || '').trim().toUpperCase();
        if (sex.charAt(0) === 'M') return 'Masculino';
        if (sex.charAt(0) === 'F') return 'Feminino';
        return sex || 'Não informado';
    }

    function init(root) {
        if (!root || root.dataset.patientSelectorReady === 'true') return;
        root.dataset.patientSelectorReady = 'true';
        var channel = root.dataset.channel;
        var allPatients = [], visiblePatients = [];
        var sortKey = '', sortDirection = 'asc';
        var results = root.querySelector('[data-patient-results]');
        var filters = root.querySelector('[data-patient-filters]');

        function selected() {
            return Array.from(root.querySelectorAll('[data-patient-check]:checked')).map(function (box) {
                return visiblePatients[Number(box.dataset.patientCheck)];
            }).filter(Boolean);
        }

        function updateCount() {
            var label = root.querySelector('[data-selected-count]');
            var patients = selected();
            if (label) label.textContent = 'Selecionados: ' + patients.length;
            root.dispatchEvent(new CustomEvent('crm:patient-selection', {
                bubbles: true,
                detail: {channel: channel, patients: patients.map(function (patient) {
                    return {
                        name: valueOf(patient, ['nomecli', 'nome']),
                        phone: valueOf(patient, ['telres', 'telefone', 'celular']),
                        email: valueOf(patient, ['email', 'emailcli'])
                    };
                })}
            }));
            if (channel === 'whatsapp') window.MedsoftSelectedWhatsappPatients = patients.map(function (patient) {
                return {name: valueOf(patient, ['nomecli', 'nome']), phone: valueOf(patient, ['telres', 'telefone', 'celular'])};
            });
        }

        function sortValue(patient, key) {
            if (key === 'nome') return String(valueOf(patient, ['nomecli', 'nome']) || '').toLocaleUpperCase('pt-BR');
            if (key === 'sexo') return String(valueOf(patient, ['sexo']) || '').toLocaleUpperCase('pt-BR');
            if (key === 'aniversario') {
                var birthday = patientDate(valueOf(patient, ['datanasc', 'nascimento']));
                return birthday ? (birthday.getMonth() + 1) * 100 + birthday.getDate() : Number.MAX_SAFE_INTEGER;
            }
            if (key === 'ultima') {
                var visit = patientDate(valueOf(patient, ['datult', 'datault']));
                return visit ? visit.getTime() : Number.MAX_SAFE_INTEGER;
            }
            if (key === 'telefone') return String(valueOf(patient, ['telres', 'telefone', 'celular']) || '');
            return String(valueOf(patient, ['email', 'emailcli']) || '').toLocaleUpperCase('pt-BR');
        }

        function sortedItems(items) {
            if (!sortKey) return items.slice();
            return items.slice().sort(function (left, right) {
                var leftValue = sortValue(left, sortKey), rightValue = sortValue(right, sortKey);
                var comparison = typeof leftValue === 'number'
                    ? leftValue - rightValue
                    : String(leftValue).localeCompare(String(rightValue), 'pt-BR', {numeric: true});
                return sortDirection === 'asc' ? comparison : -comparison;
            });
        }

        function sortableHeader(key, label) {
            var arrow = sortKey === key ? (sortDirection === 'asc' ? '↑' : '↓') : '↕';
            return '<th><button type="button" class="crm-sort-button" data-sort-column="' + key + '">' +
                escapeHtml(label) + ' <span aria-hidden="true">' + arrow + '</span></button></th>';
        }

        function renderTable(items) {
            visiblePatients = sortedItems(items);
            if (!visiblePatients.length) {
                results.innerHTML = '<div class="crud-empty">Nenhum paciente encontrado.</div>';
                return;
            }
            var rows = visiblePatients.map(function (patient, index) {
                var code = valueOf(patient, ['codcli', 'codigo']);
                var name = valueOf(patient, ['nomecli', 'nome']);
                var sex = valueOf(patient, ['sexo']);
                var birthday = valueOf(patient, ['datanasc', 'nascimento']);
                var lastVisit = valueOf(patient, ['datult', 'datault']);
                var phone = valueOf(patient, ['telres', 'telefone', 'celular']);
                var email = valueOf(patient, ['email', 'emailcli']);
                return '<tr><td><input type="checkbox" data-patient-check="' + index + '" data-patient-name="' +
                    escapeHtml(name) + '" data-patient-phone="' + escapeHtml(phone) + '" aria-label="Selecionar ' + escapeHtml(name) + '"></td>' +
                    '<td>' + escapeHtml(name) + '</td>' +
                    '<td>' + escapeHtml(formatSex(sex)) + '</td><td>' + escapeHtml(formatPatientDate(birthday)) + '</td>' +
                    '<td>' + escapeHtml(formatPatientDate(lastVisit)) + '</td><td>' + escapeHtml(phone || 'Não informado') + '</td>' +
                    (channel === 'email' ? '<td>' + escapeHtml(email || 'Não informado') + '</td>' : '') + '</tr>';
            }).join('');
            var buttonLabel = channel === 'email' ? 'Enviar e-mail' : 'Enviar Whatzap';
            results.innerHTML = '<div class="crm-patient-selection-actions"><strong>Total: ' + visiblePatients.length + '</strong>' +
                '<span data-selected-count>Selecionados: 0</span><button class="crud-button" type="button" data-send-selected>' +
                '<i class="' + (channel === 'email' ? 'fa fa-envelope' : 'fa-brands fa-whatsapp') + '"></i> ' + buttonLabel + '</button></div>' +
                '<div class="crm-patient-table-wrap"><table class="crud-table"><thead><tr><th><input type="checkbox" data-select-all></th>' +
                sortableHeader('nome', 'Nome') + sortableHeader('sexo', 'Sexo') +
                sortableHeader('aniversario', 'Aniversário') + sortableHeader('ultima', 'Última consulta') +
                sortableHeader('telefone', 'Telefone') + (channel === 'email' ? sortableHeader('email', 'E-mail') : '') +
                '</tr></thead><tbody>' + rows + '</tbody></table></div>';
            var selectAll = root.querySelector('[data-select-all]');
            selectAll.onchange = function () {
                root.querySelectorAll('[data-patient-check]').forEach(function (box) { box.checked = selectAll.checked; });
                updateCount();
            };
            root.querySelectorAll('[data-patient-check]').forEach(function (box) { box.onchange = updateCount; });
            root.querySelectorAll('[data-sort-column]').forEach(function (button) {
                button.onclick = function () {
                    var nextKey = button.dataset.sortColumn;
                    if (sortKey === nextKey) sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
                    else { sortKey = nextKey; sortDirection = 'asc'; }
                    renderTable(visiblePatients);
                };
            });
            root.querySelector('[data-send-selected]').onclick = sendSelected;
        }

        function renderFilters() {
            var plans = {};
            allPatients.forEach(function (patient) {
                [valueOf(patient, ['nomeplano1']), valueOf(patient, ['nomeplano2'])].forEach(function (plan) {
                    plan = String(plan || '').trim(); if (plan) plans[plan.toUpperCase()] = plan;
                });
            });
            var planOptions = Object.keys(plans).sort().map(function (key) { return '<option>' + escapeHtml(plans[key]) + '</option>'; }).join('');
            var months = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
            filters.hidden = false;
            filters.innerHTML = '<div class="crud-field"><label>Plano</label><select class="crud-input" data-filter-plan><option value="">Todos</option>' + planOptions + '</select></div>' +
                '<div class="crud-field"><label>Sexo</label><select class="crud-input" data-filter-sex><option value="">Todos</option><option value="M">Masculino</option><option value="F">Feminino</option></select></div>' +
                '<div class="crud-field"><label>Aniversariantes</label><select class="crud-input" data-filter-birthday><option value="">Todos</option>' + months.map(function (m,i) { return '<option value="' + (i+1) + '">' + m + '</option>'; }).join('') + '</select></div>' +
                '<div class="crud-field"><label>Última consulta</label><select class="crud-input" data-filter-visit><option value="">Todos</option>' + Array.from({length:12}, function(_,i) { return '<option value="' + (i+1) + '">' + (i+1) + (i ? ' meses' : ' mês') + '</option>'; }).join('') + '</select></div>' +
                '<button class="crud-button" type="button" data-apply-filters><i class="fa fa-filter"></i> Filtrar</button>';
            filters.querySelector('[data-apply-filters]').onclick = applyFilters;
        }

        function applyFilters() {
            var plan = filters.querySelector('[data-filter-plan]').value.trim().toUpperCase();
            var sex = filters.querySelector('[data-filter-sex]').value;
            var birthday = Number(filters.querySelector('[data-filter-birthday]').value || 0);
            var months = Number(filters.querySelector('[data-filter-visit]').value || 0);
            var cutoff = new Date(); if (months) cutoff.setMonth(cutoff.getMonth() - months);
            renderTable(allPatients.filter(function (patient) {
                var patientPlans = [valueOf(patient, ['nomeplano1']), valueOf(patient, ['nomeplano2'])].map(function (v) { return String(v || '').trim().toUpperCase(); });
                var patientSex = String(valueOf(patient, ['sexo']) || '').trim().toUpperCase();
                var birth = patientDate(valueOf(patient, ['datanasc', 'nascimento']));
                var visit = patientDate(valueOf(patient, ['datult', 'datault']));
                return (!plan || patientPlans.indexOf(plan) >= 0) && (!sex || patientSex.charAt(0) === sex) &&
                    (!birthday || (birth && birth.getMonth() + 1 === birthday)) && (!months || (visit && visit > cutoff));
            }));
        }

        async function loadPatients(all) {
            var term = root.querySelector('[data-patient-search]').value.trim();
            if (!all && !term) { CrudUI.notify('Informe o paciente para pesquisar.', 'error'); return; }
            results.innerHTML = '<div class="crud-loading">Carregando pacientes...</div>';
            var response = await fetch('/api/relatorios/pacientes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                todos: all, termo: term, campo: root.querySelector('[data-patient-search-field]').value
            })});
            var data = await response.json();
            if (!response.ok || data.success === false) throw new Error(data.message || 'Erro ao buscar pacientes.');
            allPatients = data.pacientes || []; renderFilters(); renderTable(allPatients);
        }

        async function sendSelected() {
            var patients = selected();
            if (!patients.length) { CrudUI.notify('Selecione pelo menos um paciente.', 'error'); return; }
            var type = channel === 'email' ? 'E' : 'Z';
            var response = await fetch('/api/agenda/textos-confirmacao', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tipo:type})});
            var data = await response.json();
            if (!response.ok || data.success === false) { CrudUI.notify(data.message || 'Erro ao carregar os textos padrão.', 'error'); return; }
            if (!(data.textos || []).length) { CrudUI.notify('Nenhum texto padrão foi cadastrado para este canal.', 'error'); return; }
            CrudUI.openForm({title:'Enviar mensagem', submitLabel:'Enviar', fields:[{name:'codigo_texto',label:'Mensagem padrão',type:'select',required:true,wide:true,options:[{value:'',label:'Selecione'}].concat(data.textos)}], onSubmit:async function(values) {
                var sendResponse = await fetch('/api/relatorios/pacientes/enviar-mensagem', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({canal:channel,codigo_texto:values.codigo_texto,pacientes:patients.map(function(p){return valueOf(p,['codcli','codigo']);})})});
                var sendData = await sendResponse.json();
                if (!sendResponse.ok || sendData.success === false) throw new Error(sendData.message || 'Não foi possível enviar as mensagens.');
                CrudUI.notify(sendData.message || 'Mensagens processadas.');
            }});
        }

        root.querySelector('[data-patient-search-button]').onclick = function () { loadPatients(false).catch(function(e){ results.innerHTML='<div class="crud-error">'+escapeHtml(e.message)+'</div>'; }); };
        root.querySelector('[data-patient-show-all]').onclick = function () { loadPatients(true).catch(function(e){ results.innerHTML='<div class="crud-error">'+escapeHtml(e.message)+'</div>'; }); };
        root.querySelector('[data-patient-search]').onkeydown = function (event) { if (event.key === 'Enter') root.querySelector('[data-patient-search-button]').click(); };
    }

    function initAll(container) {
        (container || document).querySelectorAll('[data-crm-patient-selector]').forEach(init);
    }

    window.CrmPatientSelector = {init: initAll};
    initAll(document);
}());
