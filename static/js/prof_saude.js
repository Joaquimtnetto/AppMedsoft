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

    function fonteReceitaOptions() {
        return [
            'Arial',
            'Verdana',
            'Tahoma',
            'Trebuchet MS',
            'Calibri',
            'Cambria',
            'Times New Roman',
            'Georgia',
            'Garamond',
            'Palatino Linotype',
            'Courier New',
            'Brush Script MT',
            'Lucida Handwriting',
            'Segoe Script',
            'Monotype Corsiva',
            'Edwardian Script ITC'
        ].map(function (item) {
            return {value: item, label: item};
        });
    }

    function tamanhoFonteOptions() {
        return [8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 26, 28, 30].map(function (item) {
            return {value: String(item), label: String(item)};
        });
    }

    function exibirLinhaOptions() {
        return [
            {value: 'S', label: 'Sim'},
            {value: 'N', label: 'Não'}
        ];
    }

    function espessuraLinhaOptions() {
        return ['0.5', '1', '1.5', '2', '2.5', '3'].map(function (item) {
            return {value: item, label: item + ' px'};
        });
    }

    function setupReceitaPreview(backdrop) {
        var form = backdrop.querySelector('form');
        var actions = backdrop.querySelector('.crud-modal-actions');
        if (!form || !actions || actions.querySelector('[data-prof-receita-preview]')) return;

        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'crud-button crud-button-secondary';
        button.setAttribute('data-prof-receita-preview', 'true');
        button.innerHTML = '<i class="fa fa-eye"></i> Pré-visualizar';

        var cancel = actions.querySelector('[data-crud-cancel]');
        actions.insertBefore(button, cancel);

        // O botão de pré-visualização pertence somente à página Receituário (página 3).
        function syncPreviewVisibility() {
            var activePage = backdrop.querySelector('[data-crud-page-button].crud-button-active');
            var showPreview = !!activePage && Number(activePage.dataset.crudPageButton) === 3;
            // Não usar apenas o atributo hidden: .crud-button define display:inline-flex
            // e pode sobrescrever o display:none padrão do navegador.
            button.classList.toggle('crud-field-hidden', !showPreview);
            button.style.display = showPreview ? 'inline-flex' : 'none';
            button.setAttribute('aria-hidden', showPreview ? 'false' : 'true');
        }
        backdrop.querySelectorAll('[data-crud-page-button]').forEach(function (pageButton) {
            pageButton.addEventListener('click', function () {
                window.setTimeout(syncPreviewVisibility, 0);
            });
        });
        syncPreviewVisibility();

        button.addEventListener('click', function () {
            function value(name, fallback) {
                var field = form.querySelector('[name="' + name + '"]');
                return field && field.value ? field.value : (fallback || '');
            }
            function esc(value) {
                return String(value || '')
                    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            }

            var fonteCab = value('fonte_cabecalho', 'Arial');
            var tamCab = value('tamanho_cabecalho', '16');
            var fonteCab2 = value('fonte_cabecalho2', fonteCab);
            var tamCab2 = value('tamanho_cabecalho2', tamCab);
            var fonteCab3 = value('fonte_cabecalho3', fonteCab);
            var tamCab3 = value('tamanho_cabecalho3', tamCab);
            var fonteRod = value('fonte_rodape', 'Arial');
            var tamRod = value('tamanho_rodape', '13');
            var linhaCab = value('linha_cabecalho', 'S');
            var espLinhaCab = value('espessura_linha_cabecalho', '1');
            var linhaRod = value('linha_rodape', 'S');
            var espLinhaRod = value('espessura_linha_rodape', '1');
            var titulo1 = value('tit1');
            var titulo2 = value('tit2');
            var titulo3 = value('tit3');
            var rod1 = value('rod1');
            var rod2 = value('rod2');
            var cidade = value('cidade_receita', value('cidade', ''));

            var preview = window.open('', 'medsoft_receita_preview', 'width=760,height=900,resizable=yes,scrollbars=yes');
            if (!preview) {
                CrudUI.notify('O navegador bloqueou a janela de pré-visualização.');
                return;
            }
            preview.document.open();
            preview.document.write(
                '<!doctype html><html><head><meta charset="utf-8"><title>Pré-visualização do receituário</title>' +
                '<style>' +
                'body{margin:0;background:#e9edf3;font-family:Arial,sans-serif}' +
                '.toolbar{padding:10px;text-align:center;background:#fff;border-bottom:1px solid #ccc}' +
                '.page{position:relative;width:210mm;height:297mm;min-height:297mm;margin:18px auto;background:#fff;box-sizing:border-box;padding:12mm 16mm 12mm;box-shadow:0 2px 12px rgba(0,0,0,.18);display:flex;flex-direction:column;overflow:visible}' +
                '.header{min-height:28mm;display:flex;flex-direction:column;justify-content:center;text-align:center;line-height:1.12;gap:0;overflow:visible}' +
                '.header div{display:block;margin:0;padding:0;width:100%;max-width:none;white-space:nowrap;overflow:visible;font-stretch:normal;font-synthesis:none;transform:none}' +
                '.header .t1{font-family:' + JSON.stringify(fonteCab) + ',sans-serif;font-size:' + parseInt(tamCab,10) + 'pt;transform:scaleX(1.28);transform-origin:center center}' +
                '.header .t2{font-family:' + JSON.stringify(fonteCab2) + ',sans-serif;font-size:' + parseInt(tamCab2,10) + 'pt}' +
                '.header .t3{font-family:' + JSON.stringify(fonteCab3) + ',sans-serif;font-size:' + parseInt(tamCab3,10) + 'pt}' +
                '.line-area{height:5mm;position:relative;flex:0 0 5mm}.line{position:absolute;left:0;right:0;bottom:1mm;margin:0}' +
                '.content-gap{height:8mm;flex:0 0 8mm}' +
                '.sample{font:11pt Arial,sans-serif;margin:0 0 5mm}' +
                '.content-sample{flex:1;font:12pt Arial,sans-serif;line-height:1.55}' +
                '.footer{text-align:center;font-family:' + JSON.stringify(fonteRod) + ',sans-serif;font-size:' + parseInt(tamRod,10) + 'pt;line-height:1.2}' +
                '.footer-line{margin:5mm 0 2.5mm}.footer div{margin:1px 0}' +
                '</style></head><body>' +
                '<div class="toolbar">Pré-visualização — alterações ainda não salvas</div>' +
                '<div class="page">' +
                '<div class="header"><div class="t1">' + esc(titulo1) + '</div><div class="t2">' + esc(titulo2) + '</div><div class="t3">' + esc(titulo3) + '</div></div>' +
                '<div class="line-area">' + (linhaCab === 'S' ? '<div class="line" style="border-top:' + esc(espLinhaCab) + 'px solid #777"></div>' : '') + '</div>' +
                '<div class="content-gap"></div><div class="sample"><b>Paciente:</b> NOME DO PACIENTE</div>' +
                '<div class="content-sample">Exemplo do conteúdo da receita.</div>' +
                '<div class="footer">' + (linhaRod === 'S' ? '<div class="footer-line" style="border-top:' + esc(espLinhaRod) + 'px solid #777"></div>' : '') + '<div>' + esc(rod1) + '</div><div>' + esc(rod2) + '</div><div>' + esc(cidade) + '</div></div>' +
                '</div></body></html>'
            );
            preview.document.close();
        });
    }

    function setupProfSaudeForm(backdrop) {
        setupCepLookup(backdrop);
        setupReceitaPreview(backdrop);
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
        function timeValue(value) {
            value = String(value || '').trim();
            if (/^\d{4}$/.test(value)) return value.slice(0, 2) + ':' + value.slice(2);
            return value;
        }
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


    function receituarioFields(item) {
        item = item || {};
        return [
            {name: 'logoprin', label: 'Logo Clínica', type: 'image', value: item.logoprin || '', page: 3, className: 'prof-field-logo-prin'},
            {name: 'tit1', label: 'Título 1', value: item.tit1 || '', maxLength: 60, page: 3, className: 'prof-field-tit1'},
            {name: 'tit2', label: 'Título 2', value: item.tit2 || '', maxLength: 60, page: 3, className: 'prof-field-tit2'},
            {name: 'tit3', label: 'Título 3', value: item.tit3 || '', maxLength: 60, page: 3, className: 'prof-field-tit3'},
            {name: 'logorec', label: 'Logo Receita', type: 'image', value: item.logorec || '', page: 3, className: 'prof-field-logo-rec'},
            {name: 'rod1', label: 'Rodapé 1', value: item.rod1 || '', maxLength: 60, page: 3, className: 'prof-field-rod1'},
            {name: 'rod2', label: 'Rodapé 2', value: item.rod2 || '', maxLength: 60, page: 3, className: 'prof-field-rod2'},
            {name: 'cidade_receita', label: 'Cidade', value: item.cidade_receita || item.cidade || '', maxLength: 20, page: 3, className: 'prof-field-cidade-rec'},
            {name: 'fonte_cabecalho', label: 'Fonte Título 1', type: 'select', value: item.fonte_cabecalho || 'Arial', options: fonteReceitaOptions(), page: 3, className: 'prof-field-fonte-cab'},
            {name: 'tamanho_cabecalho', label: 'Tamanho Título 1', type: 'select', value: String(item.tamanho_cabecalho || 16), options: tamanhoFonteOptions(), page: 3, className: 'prof-field-tamanho-cab'},
            {name: 'fonte_cabecalho2', label: 'Fonte Título 2', type: 'select', value: item.fonte_cabecalho2 || item.fonte_cabecalho || 'Arial', options: fonteReceitaOptions(), page: 3, className: 'prof-field-fonte-cab2'},
            {name: 'tamanho_cabecalho2', label: 'Tamanho Título 2', type: 'select', value: String(item.tamanho_cabecalho2 || item.tamanho_cabecalho || 16), options: tamanhoFonteOptions(), page: 3, className: 'prof-field-tamanho-cab2'},
            {name: 'fonte_cabecalho3', label: 'Fonte Título 3', type: 'select', value: item.fonte_cabecalho3 || item.fonte_cabecalho || 'Arial', options: fonteReceitaOptions(), page: 3, className: 'prof-field-fonte-cab3'},
            {name: 'tamanho_cabecalho3', label: 'Tamanho Título 3', type: 'select', value: String(item.tamanho_cabecalho3 || item.tamanho_cabecalho || 16), options: tamanhoFonteOptions(), page: 3, className: 'prof-field-tamanho-cab3'},
            {name: 'fonte_rodape', label: 'Fonte do rodapé', type: 'select', value: item.fonte_rodape || 'Arial', options: fonteReceitaOptions(), page: 3, className: 'prof-field-fonte-rod'},
            {name: 'tamanho_rodape', label: 'Tamanho do rodapé', type: 'select', value: String(item.tamanho_rodape || 13), options: tamanhoFonteOptions(), page: 3, className: 'prof-field-tamanho-rod'},
            {name: 'linha_cabecalho', label: 'Linha do cabeçalho', type: 'select', value: item.linha_cabecalho || 'S', options: exibirLinhaOptions(), page: 3, className: 'prof-field-linha-cab'},
            {name: 'espessura_linha_cabecalho', label: 'Grossura linha cabeçalho', type: 'select', value: String(item.espessura_linha_cabecalho || 1), options: espessuraLinhaOptions(), page: 3, className: 'prof-field-esp-linha-cab'},
            {name: 'linha_rodape', label: 'Linha do rodapé', type: 'select', value: item.linha_rodape || 'S', options: exibirLinhaOptions(), page: 3, className: 'prof-field-linha-rod'},
            {name: 'espessura_linha_rodape', label: 'Grossura linha rodapé', type: 'select', value: String(item.espessura_linha_rodape || 1), options: espessuraLinhaOptions(), page: 3, className: 'prof-field-esp-linha-rod'}
        ];
    }

    function anamneseFields(item) {
        item = item || {};
        var labels = ['Temperatura', 'Peso', 'Pressão', 'Parâmetro 1', 'Parâmetro 2', 'Parâmetro 3'];
        return [{
            name: 'anamnese_instrucao', label: '', type: 'static', page: 4,
            className: 'prof-field-anamnese-instrucao',
            value: 'Defina os nomes dos campos do histórico para este profissional. Deixe em branco para usar o nome original.'
        }].concat(labels.map(function (label, index) {
            var name = 'param' + (index + 1);
            return {name: name, label: 'Texto do campo ' + label,
                value: item[name] || '', placeholder: label, page: 4};
        }));
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
        ].concat(dayFields(item), receituarioFields(item), anamneseFields(item));
    }

    function payload(values) {
        validateHorarios(values);

        // Envia explicitamente S/N. Evita qualquer conversão implícita ou valor
        // vazio quando o usuário seleciona "Não" nas linhas do receituário.
        function yesNo(value, fallback) {
            value = String(value == null ? '' : value).trim().toUpperCase();
            if (value === 'N' || value === 'NAO' || value === 'NÃO' || value === 'FALSE' || value === '0') return 'N';
            if (value === 'S' || value === 'SIM' || value === 'TRUE' || value === '1') return 'S';
            return fallback || 'S';
        }

        return {
            nome: values.nome,
            param1: values.param1,
            param2: values.param2,
            param3: values.param3,
            param4: values.param4,
            param5: values.param5,
            param6: values.param6,

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
            tit1: values.tit1,
            tit2: values.tit2,
            tit3: values.tit3,
            rod1: values.rod1,
            rod2: values.rod2,
            cidade_receita: values.cidade_receita,
            fonte_cabecalho: values.fonte_cabecalho,
            tamanho_cabecalho: values.tamanho_cabecalho,
            fonte_cabecalho2: values.fonte_cabecalho2,
            tamanho_cabecalho2: values.tamanho_cabecalho2,
            fonte_cabecalho3: values.fonte_cabecalho3,
            tamanho_cabecalho3: values.tamanho_cabecalho3,
            fonte_rodape: values.fonte_rodape,
            tamanho_rodape: values.tamanho_rodape,
            linha_cabecalho: yesNo(values.linha_cabecalho, 'S'),
            espessura_linha_cabecalho: values.espessura_linha_cabecalho,
            linha_rodape: yesNo(values.linha_rodape, 'S'),
            espessura_linha_rodape: values.espessura_linha_rodape,
            logoprin: values.logoprin,
            logorec: values.logorec,
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


    function confirmarPreferenciasSalvas(response, values) {
        var pref = response && response.prefere ? response.prefere : {};
        var checks = [
            ['fonte_cabecalho', values.fonte_cabecalho],
            ['tamanho_cabecalho', values.tamanho_cabecalho],
            ['fonte_cabecalho2', values.fonte_cabecalho2],
            ['tamanho_cabecalho2', values.tamanho_cabecalho2],
            ['fonte_cabecalho3', values.fonte_cabecalho3],
            ['tamanho_cabecalho3', values.tamanho_cabecalho3]
        ];
        for (var i = 0; i < checks.length; i++) {
            var name = checks[i][0];
            var expected = String(checks[i][1] == null ? '' : checks[i][1]).trim();
            if (!(name in pref)) {
                throw new Error('O backend em execução não retornou ' + name + '. Reinicie/recompile o aplicativo usando o backend/prof_saude_api.py desta versão.');
            }
            var actual = String(pref[name] == null ? '' : pref[name]).trim();
            if (actual !== expected) {
                throw new Error('Falha ao salvar ' + name + ': enviado "' + expected + '", banco retornou "' + actual + '".');
            }
        }
        return response;
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
            pageTitles: ['', '', '', 'Anamnese'],
            fields: fields,
            renderItem: renderItem,
            onFormReady: setupProfSaudeForm,
            list: async function () {
                var data = await api('/api/prof-saude', 'POST', {termo: searchTerm()});
                return data.profissionais || [];
            },
            create: async function (values) {
                var data = payload(values);
                var response = await api('/api/prof-saude/itens', 'POST', data);
                return confirmarPreferenciasSalvas(response, data);
            },
            update: async function (item, values) {
                var data = payload(values);
                var response = await api('/api/prof-saude/itens/' + encodeURIComponent(item.id), 'PUT', data);
                return confirmarPreferenciasSalvas(response, data);
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
