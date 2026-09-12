(function () {
    var controller;

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
        return document.getElementById('prof-saude-busca').value;
    }

    function ufOptions() {
        return ['', 'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT',
            'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR',
            'SC', 'SP', 'SE', 'TO'].map(function (uf) {
            return {value: uf, label: uf};
        });
    }

    function conselhoOptions() {
        return ['', 'CRM', 'CRN', 'CRO', 'CRP', 'CREFITO', 'CREFONO'].map(function (item) {
            return {value: item, label: item};
        });
    }

    function setupCepLookup(backdrop) {
        var cep = backdrop.querySelector('[name="cep"]');
        if (!cep) return;
        var lastCep = '';

        async function lookupCep() {
            var digits = cep.value.replace(/\D/g, '');
            if (digits.length !== 8) return;
            if (digits === lastCep) return;
            lastCep = digits;
            try {
                var response = await fetch('https://viacep.com.br/ws/' + digits + '/json/');
                var data = await response.json();
                if (!response.ok || data.erro) throw new Error('CEP não encontrado.');
                var endereco = backdrop.querySelector('[name="endereco"]');
                var bairro = backdrop.querySelector('[name="bairro"]');
                var municipio = backdrop.querySelector('[name="municipio"]');
                var uf = backdrop.querySelector('[name="uf"]');
                if (endereco) endereco.value = data.logradouro || endereco.value;
                if (bairro) bairro.value = data.bairro || bairro.value;
                if (municipio) municipio.value = data.localidade || municipio.value;
                if (uf) uf.value = data.uf || uf.value;
            } catch (error) {
                CrudUI.notify(error.message || 'Não foi possível consultar o CEP.', 'error');
            }
        }

        cep.addEventListener('input', lookupCep);
        cep.addEventListener('blur', lookupCep);
        cep.addEventListener('change', lookupCep);
    }

    function validateHorarios(values) {
        [
            ['segunda', 'Segunda'],
            ['terca', 'Terça'],
            ['quarta', 'Quarta'],
            ['quinta', 'Quinta'],
            ['sexta', 'Sexta'],
            ['sabado', 'Sábado'],
            ['domingo', 'Domingo']
        ].forEach(function (day) {
            var inicio = values[day[0] + '_inicio'];
            var termino = values[day[0] + '_termino'];
            if (!inicio && !termino) return;
            if (!inicio || !termino) {
                throw new Error('Informe início e término para ' + day[1] + '.');
            }
            if (termino <= inicio) {
                throw new Error('O horário de término deve ser maior que o início em ' + day[1] + '.');
            }
        });
    }

    function dayFields(item) {
        var days = [
            ['segunda', 'Segunda'],
            ['terca', 'Terça'],
            ['quarta', 'Quarta'],
            ['quinta', 'Quinta'],
            ['sexta', 'Sexta'],
            ['sabado', 'Sábado'],
            ['domingo', 'Domingo']
        ];
        var fields = [
            {name: 'horario_titulo', label: '', type: 'static', value: 'Horários de atendimento', page: 2, className: 'prof-field-horario-titulo'},
            {name: 'horario_dia_header', label: '', type: 'static', value: 'Dia', page: 2, className: 'prof-field-horario-head'},
            {name: 'horario_inicio_header', label: '', type: 'static', value: 'Início', page: 2, className: 'prof-field-horario-head'},
            {name: 'horario_termino_header', label: '', type: 'static', value: 'Término', page: 2, className: 'prof-field-horario-head'}
        ];
        days.forEach(function (day) {
            fields.push(
                {name: day[0] + '_label', label: '', type: 'static', value: day[1], page: 2, className: 'prof-field-dia'},
                {name: day[0] + '_inicio', label: 'Início', type: 'time', value: item[day[0] + '_inicio'] || '', page: 2},
                {name: day[0] + '_termino', label: 'Término', type: 'time', value: item[day[0] + '_termino'] || '', page: 2}
            );
        });
        return fields;
    }

    function fields(item) {
        item = item || {};
        return [
            {name: 'nome', label: 'Nome', value: item.nome || '', required: true, page: 1, className: 'prof-field-nome'},
            {name: 'cep', label: 'Cep', value: item.cep || '', mask: 'cep-br', placeholder: '99999-99', maxLength: 9, inputMode: 'numeric', page: 1},
            {name: 'uf', label: 'UF', type: 'select', value: item.uf || '', options: ufOptions(), page: 1},
            {name: 'municipio', label: 'Município', value: item.municipio || '', maxLength: 30, page: 1},
            {name: 'endereco', label: 'Endereço', value: item.endereco || '', maxLength: 60, page: 1, className: 'prof-field-endereco'},
            {name: 'bairro', label: 'Bairro', value: item.bairro || '', maxLength: 30, page: 1},
            {name: 'email', label: 'Email', value: item.email || '', type: 'email', maxLength: 60, page: 1},
            {name: 'telefone', label: 'Telefone', value: item.telefone || '', mask: 'phone-br-landline', placeholder: '(99)9999-9999', maxLength: 13, inputMode: 'numeric', page: 1},
            {name: 'celular', label: 'Celular', value: item.celular || '', mask: 'phone-br', placeholder: '(99)99999-9999', maxLength: 14, inputMode: 'numeric', page: 1},
            {name: 'cpf', label: 'CPF', value: item.cpf || '', mask: 'cpf-br', placeholder: '999.999.999-99', maxLength: 14, inputMode: 'numeric', page: 1},
            {name: 'conselho', label: 'Conselho', type: 'select', value: item.conselho || '', options: conselhoOptions(), page: 1},
            {name: 'nrconselho', label: 'Nr.Conselho', value: item.nrconselho || '', maxLength: 20, page: 1},
            {name: 'especialidade', label: 'Especialidade', value: item.especialidade || '', maxLength: 40, page: 1},
            {name: 'subespecialidade', label: 'Sub-Especialidade', value: item.subespecialidade || '', maxLength: 40, page: 1},
            {name: 'observacao', label: 'Observação', value: item.observacao || '', type: 'textarea', rows: 3, maxLength: 400, page: 1, className: 'prof-field-observacao'}
        ].concat(dayFields(item));
    }

    function payload(values) {
        validateHorarios(values);
        return {
            nome: values.nome,
            cep: values.cep,
            uf: values.uf,
            municipio: values.municipio,
            endereco: values.endereco,
            bairro: values.bairro,
            email: values.email,
            telefone: values.telefone,
            celular: values.celular,
            cpf: values.cpf,
            conselho: values.conselho,
            nrconselho: values.nrconselho,
            especialidade: values.especialidade,
            subespecialidade: values.subespecialidade,
            observacao: values.observacao,
            segunda_inicio: values.segunda_inicio,
            segunda_termino: values.segunda_termino,
            terca_inicio: values.terca_inicio,
            terca_termino: values.terca_termino,
            quarta_inicio: values.quarta_inicio,
            quarta_termino: values.quarta_termino,
            quinta_inicio: values.quinta_inicio,
            quinta_termino: values.quinta_termino,
            sexta_inicio: values.sexta_inicio,
            sexta_termino: values.sexta_termino,
            sabado_inicio: values.sabado_inicio,
            sabado_termino: values.sabado_termino,
            domingo_inicio: values.domingo_inicio,
            domingo_termino: values.domingo_termino
        };
    }

    function detail(label, value, icon) {
        return '<span><i class="fa ' + icon + '"></i> <strong>' + label + ':</strong> ' +
            CrudUI.escapeHtml(value || '') + '</span>';
    }

    function renderItem(item) {
        return '<article class="crud-card prof-saude-card">' +
            '<div class="crud-card-header"><div class="crud-card-main">' +
            '<div class="crud-card-title">' + CrudUI.escapeHtml(item.nome) + '</div>' +
            '<div class="plano-code">#' + CrudUI.escapeHtml(item.id) + '</div>' +
            '</div></div><div class="crud-card-details">' +
            detail('Conselho', [item.conselho, item.nrconselho].filter(Boolean).join(' '), 'fa-id-card') +
            detail('Especialidade', item.especialidade, 'fa-stethoscope') +
            detail('Telefone', item.telefone || item.celular, 'fa-phone') +
            detail('Município', item.municipio, 'fa-location-dot') +
            '</div><div class="crud-actions">' +
            '<button class="crud-button crud-button-secondary" data-crud-edit="' + item.id +
            '" title="Alterar profissional"><i class="fa fa-pencil"></i>' +
            '<span class="crud-button-label"> Alterar</span></button>' +
            '<button class="crud-button crud-button-danger" data-crud-delete="' + item.id +
            '" title="Excluir profissional"><i class="fa fa-trash"></i>' +
            '<span class="crud-button-label"> Excluir</span></button></div></article>';
    }

    function createController() {
        return new CrudUI.Controller({
            getId: function (item) { return item.id; },
            createTitle: 'Incluir Prof. Saúde',
            editTitle: 'Alterar Prof. Saúde',
            formClass: 'prof-saude-form',
            emptyMessage: 'Nenhum profissional encontrado.',
            hasComplement: true,
            pageCount: 4,
            pageLabels: ['Cadastro', 'Horário', 'Receituário', 'Anamnese'],
            fields: fields,
            renderItem: renderItem,
            onFormReady: setupCepLookup,
            list: async function () {
                var data = await api('/api/prof-saude', 'POST', {termo: searchTerm()});
                return data.profissionais || [];
            },
            create: function (values) { return api('/api/prof-saude/itens', 'POST', payload(values)); },
            update: function (item, values) {
                return api('/api/prof-saude/itens/' + encodeURIComponent(item.id), 'PUT', payload(values));
            },
            delete: function (item) { return api('/api/prof-saude/itens/' + encodeURIComponent(item.id), 'DELETE'); },
            confirmDelete: function (item) {
                return 'Excluir o profissional ' + item.nome + '?';
            }
        });
    }

    function init() {
        var page = document.getElementById('prof-saude-page');
        if (!page || page.dataset.initialized === 'true') return;
        page.dataset.initialized = 'true';

        controller = createController().mount({
            root: page,
            list: document.getElementById('prof-saude-result'),
            includeButton: document.getElementById('prof-saude-include')
        });

        document.getElementById('btn-ok').onclick = function () { controller.reload(); };
        document.getElementById('prof-saude-busca').addEventListener('keypress', function (event) {
            if (event.key === 'Enter') controller.reload();
        });
        controller.reload();
    }

    window.ProfSaudeCrud = {init: init};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
