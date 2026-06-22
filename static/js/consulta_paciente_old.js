// JS para consulta de paciente (externo)
console.log('[MedSoft] consulta_paciente.js carregado');
// Função global para funcionar também em telas carregadas dinamicamente.
async function buscarPaciente(event) {
        if (event) event.preventDefault();
        const termo = document.getElementById('busca-paciente').value;
        const resultadoDiv = document.getElementById('resultado-paciente');
        resultadoDiv.innerHTML = '';
        if (!termo) {
            resultadoDiv.innerHTML = '<span style="color:#e74c3c;">Digite um nome ou código.</span>';
            return;
        }
        resultadoDiv.innerHTML = '<span style="color:#357ae8;">Buscando paciente...</span>';
        try {
            const db_path = localStorage.getItem('db_path');
            const response = await fetch('/api/consulta-paciente', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-DB-PATH': db_path || ''
                },
                body: JSON.stringify({ termo })
            });
            if (!response.ok) {
                throw new Error('Erro HTTP: ' + response.status);
            }
            const data = await response.json();
            resultadoDiv.innerHTML = `
                <table class="paciente-table">
                    <thead>
                        <tr>
                            <th>Paciente</th>
                            <th class="acao-col">Ações</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.success && data.pacientes.length > 0 ?
                            data.pacientes.map((p, idx, arr) => {
                                let idade = '';
                                if (p.idade !== null && p.idade !== undefined) {
                                    idade = p.idade;
                                }
                                return `
                                <tr class="paciente-main">
                                    <td><b>${p.nomecli}</b></td>
                                    <td class="acao" rowspan="2">
                                        <button class="btn-acao" title="Histórico" onclick="abrirHistoricoPaciente('${p.codcli}', '${p.nomecli}')">
                                            <i class='fa fa-notes-medical'></i>
                                        </button>
                                    </td>
                                </tr>
                                <tr class="paciente-info">
                                    <td colspan="2">Idade: ${idade} &nbsp; | &nbsp; Convênio: ${p.nomeplano1}</td>
                                </tr>
                                ${(idx < arr.length - 1) ? '<tr class="separador"><td colspan="2"></td></tr>' : ''}
                                `;
                            }).join('')
                            : `<tr><td colspan='2' style='text-align:center;color:#e74c3c;'>Nenhum paciente encontrado.</td></tr>`}
                    </tbody>
                </table>
            `;
        } catch (err) {
            resultadoDiv.innerHTML = `<span style='color:#e74c3c;'>Erro ao buscar paciente: ${err.message}</span>`;
            console.error('[MedSoft] Erro na busca de paciente:', err);
        }
        return false;
}

function configurarBuscaPaciente() {
    const form = document.getElementById('form-consulta-paciente');
    if (!form) {
        console.warn('[MedSoft] Formulário de consulta de paciente não encontrado!');
        return;
    }
    form.onsubmit = buscarPaciente;
}

setTimeout(configurarBuscaPaciente, 0);

// Função para buscar e exibir histórico do paciente
function abrirHistoricoPaciente(codcli, nomecli) {
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
        let conteudo = `<h3>Histórico de ${nomecli}</h3>`;
        if (data.success && data.consultas && data.consultas.length > 0) {
            conteudo += '<ul style="max-height:300px;overflow:auto;text-align:left;">';
            data.consultas.forEach(c => {
                conteudo += `<li><b>Data:</b> ${c.dtvisita} <br><b>Diagnóstico:</b> ${c.diag || ''} <br><b>Histórico:</b> ${c.historico || ''}</li><hr>`;
            });
            conteudo += '</ul>';
        } else {
            conteudo += '<p style="color:#e74c3c;">Nenhum histórico encontrado.</p>';
        }
        exibirModal(conteudo);
    })
    .catch(() => {
        exibirModal('<p style="color:#e74c3c;">Erro ao buscar histórico.</p>');
    });
}

// Função para exibir modal simples
function exibirModal(html) {
    let modal = document.getElementById('modal-historico');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'modal-historico';
        modal.style = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;z-index:9999;';
        modal.innerHTML = `<div style='background:#fff;padding:2rem 1.5rem;border-radius:16px;max-width:420px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.18);text-align:left;position:relative;'>
            <button onclick="document.getElementById('modal-historico').remove()" style="position:absolute;top:10px;right:10px;background:none;border:none;font-size:1.3rem;cursor:pointer;color:#888;">&times;</button>
            <div id='modal-historico-content'></div>
        </div>`;
        document.body.appendChild(modal);
    }
    document.getElementById('modal-historico-content').innerHTML = html;
}
