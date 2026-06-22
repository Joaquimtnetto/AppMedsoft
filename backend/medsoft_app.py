
from medsoft_core import get_db_connection
from build_info import BUILD_DATETIME, BUILD_VERSION
import config
from config import SECRET_KEY
# Importa o Blueprint de consulta_paciente
from consulta_paciente import consulta_paciente_bp
from consultas_routes import consultas_bp
from agenda import agenda_bp
from agenda_api import agenda_api_bp
from paciente_api import paciente_api_bp

db_path_global = None
usuario_global = None
empresa_global = None

def get_user_empresa_db(login, senha):
    # A tabela atual é `ic_usuario_geral` e os campos de autenticação são `login` e `senha`.
    # Muitos esquemas não possuem a coluna `nome_medico`; para evitar erro, retornamos
    # um valor nulo para `nome_medico` quando a coluna não existir.
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("""
        SELECT ug.idusuario, ug.idempresa, ug.nome, eg.database, eg.nome as empresa, NULL::text as nome_medico
        FROM ic_usuario_geral ug
        JOIN ic_empresa_geral eg ON eg.idempresa = ug.idempresa AND eg.ativo
        WHERE ug.login=%s AND ug.senha=%s AND ug.ativo=TRUE
    """, (login, senha))
    user = cur.fetchone()
    con.close()
    if not user:
        return (None, None, None, None, None, None)
    idusuario, idempresa, nome, db_path, empresa_nome, nome_medico = user
    return idusuario, idempresa, nome, db_path, empresa_nome, nome_medico

import os
import sys

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import smtplib
from email.message import EmailMessage
import logging
from consultas_routes import consultas_bp
import traceback
import datetime


# Função para obter o caminho dos recursos (templates/static) para PyInstaller
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

from flask import send_from_directory


# No executável, os recursos são extraídos pelo PyInstaller em sys._MEIPASS.
template_folder = resource_path('templates')
static_folder = resource_path('static')



app = Flask(
    __name__,
    template_folder=template_folder,
    static_folder=static_folder
)
app.secret_key = SECRET_KEY

PUBLIC_ENDPOINTS = {
    'index',
    'login',
    'esqueci_senha_form',
    'esqueci_senha_post',
    'reset_password_form',
    'reset_password_post',
    'static',
}


@app.before_request
def require_authentication():
    if request.endpoint in PUBLIC_ENDPOINTS or session.get('usuario'):
        return None
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Sessão expirada. Faça login novamente.'}), 401
    return redirect(url_for('index'))

# Validar configuração inicial e falhar com mensagem clara se estiver incorreta
validation_errors = config.validate_config()
if validation_errors:
    for err in validation_errors:
        print('Configuration error:', err)
    print('Corrija as variáveis de ambiente conforme mensagens acima e reinicie a aplicação.')
    sys.exit(1)
app.register_blueprint(consultas_bp)
app.register_blueprint(consulta_paciente_bp)
app.register_blueprint(agenda_bp)
app.register_blueprint(agenda_api_bp)
app.register_blueprint(paciente_api_bp)

# Serializer para tokens de redefinição de senha
serializer = URLSafeTimedSerializer(app.secret_key)


def send_email(to_address, subject, body, html_body=None):
    """Envia um e-mail usando as configurações em `config`.
    Retorna True se enviado com sucesso, False caso contrário.
    """
    # Se SMTP não estiver configurado, não tenta enviar
    if not getattr(config, 'SMTP_HOST', ''):
        logging.info('SMTP não configurado; pulando envio de e-mail.')
        return False
    try:
        msg = EmailMessage()
        msg['From'] = config.SMTP_FROM
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype='html')

        if config.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
        server.ehlo()
        if config.SMTP_USE_TLS and not config.SMTP_USE_SSL:
            server.starttls()
            server.ehlo()
        if config.SMTP_USER and config.SMTP_PASS:
            server.login(config.SMTP_USER, config.SMTP_PASS)
        server.send_message(msg)
        server.quit()
        logging.info(f'E-mail enviado para {to_address}')
        return True
    except Exception as e:
        logging.exception('Falha ao enviar e-mail:')
        return False



# Rota para servir consultas_paciente.html
@app.route('/consultas_paciente.html')
def consultas_paciente_html():
    return render_template('consultas_paciente.html')


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    login = data.get('nome')
    senha = data.get('senha')
    if not login or not senha:
        return jsonify({'success': False, 'message': 'Nome e senha obrigatórios.'}), 400
    try:
        global db_path_global, usuario_global, empresa_global
        idusuario, idempresa, nome, db_path, empresa_nome, nome_medico = get_user_empresa_db(login, senha)
        if not idusuario or not db_path:
            return jsonify({'success': False, 'message': 'Nome ou senha inválidos ou empresa inativa.'}), 401
        # Define variáveis globais
        db_path_global = db_path
        usuario_global = nome
        empresa_global = empresa_nome
        # Testa conexão com banco do usuário
        try:
            con_user = get_db_connection(db_path)
            con_user.close()
        except Exception as e:
            session.clear()
            return jsonify({'success': False, 'message': f'Erro ao conectar ao banco da empresa: {str(e)}'}), 500
        session['db_path'] = db_path
        session['nome_medico'] = nome_medico
        session['usuario'] = nome
        return jsonify({
            'success': True,
            'message': 'Login realizado com sucesso.',
            'nome': nome,
            'idusuario': idusuario,
            'idempresa': idempresa,
            'db_path': db_path,
            'empresa_nome': empresa_nome,
            'nome_medico': nome_medico
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/change-password', methods=['POST'])
def change_password():
    data = request.json
    nome = data.get('nome')
    senha_atual = data.get('senhaAtual')
    nova_senha = data.get('novaSenha')
    if not nome or not senha_atual or not nova_senha:
        return jsonify({'success': False, 'message': 'Usuário, senha atual e nova senha obrigatórios.'}), 400
    try:
        con = get_db_connection()
        cur = con.cursor()
        # Verifica se a senha atual está correta na tabela ic_usuario_geral (campo login/senha)
        try:
            cur.execute("SELECT idusuario FROM ic_usuario_geral WHERE login=%s AND senha=%s AND ativo=TRUE", (nome, senha_atual))
            row = cur.fetchone()
        except Exception:
            con.close()
            return jsonify({'success': False, 'message': 'Erro ao verificar usuário no banco.'}), 500
        if not row:
            con.close()
            return jsonify({'success': False, 'message': 'Senha atual incorreta.'}), 401
        idusuario = row[0]
        # Atualiza a senha no ic_usuario_geral
        cur.execute("UPDATE ic_usuario_geral SET senha=%s WHERE idusuario=%s", (nova_senha, idusuario))
        con.commit()
        # Independente do rowcount, se não deu erro e passou pela verificação da senha, considera sucesso
        con.close()
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso!'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# --- Recuperação de senha ---
@app.route('/esqueci-senha', methods=['GET'])
def esqueci_senha_form():
    return render_template('esqueci_senha.html')


@app.route('/esqueci-senha', methods=['POST'])
def esqueci_senha_post():
    # Aceita form-urlencoded ou JSON
    email = request.form.get('email') if request.form else (request.json and request.json.get('email'))
    if not email:
        return jsonify({'success': False, 'message': 'E-mail obrigatório.'}), 400
    try:
        con = get_db_connection()
        cur = con.cursor()
        user = None
        # Tenta localizar por coluna email; se a consulta falhar (ex.: coluna não existe), faz rollback
        try:
            cur.execute("SELECT idusuario, login, nome, email FROM ic_usuario_geral WHERE email=%s AND ativo=TRUE", (email,))
            user = cur.fetchone()
        except Exception as e:
            # A consulta pode ter deixado a transação em estado abortado; desfaz antes da segunda tentativa
            try:
                con.rollback()
            except Exception:
                pass
            try:
                cur.execute("SELECT idusuario, login, nome FROM ic_usuario_geral WHERE login=%s AND ativo=TRUE", (email,))
                user = cur.fetchone()
            except Exception as e2:
                con.close()
                return jsonify({'success': False, 'message': f'Erro ao acessar o banco: {str(e2)}'}), 500
        con.close()
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao acessar o banco: {str(e)}'}), 500
    # Não revelar se o usuário existe; sempre retornar mensagem positiva
    if not user:
        print(f'[Password Reset] nenhum usuário encontrado para: {email}')
        return jsonify({'success': True, 'message': 'Se o e-mail estiver cadastrado, você receberá instruções para redefinir sua senha.'})
    idusuario = user[0]
    token = serializer.dumps({'idusuario': idusuario}, salt='password-reset-salt')
    reset_link = f"{request.url_root.rstrip('/')}/reset-password/{token}"
    subject = 'MedSoft - Redefinição de senha'
    body = f"Você solicitou a redefinição de senha. Acesse o link abaixo para criar uma nova senha (válido por 1 hora):\n\n{reset_link}\n\nSe você não solicitou, desconsidere este e-mail."
    html = f"<p>Você solicitou a redefinição de senha. Clique no link abaixo para criar uma nova senha (válido por 1 hora):</p><p><a href=\"{reset_link}\">Redefinir minha senha</a></p>"
    sent = send_email(email, subject, body, html_body=html)
    if not sent:
        # fallback: mostra link no console e retorna debug_link durante desenvolvimento
        print(f'[Password Reset] Link para {email}: {reset_link}')
        return jsonify({'success': True, 'message': 'Se o e-mail estiver cadastrado, você receberá instruções para redefinir sua senha.', 'debug_link': reset_link})
    return jsonify({'success': True, 'message': 'Se o e-mail estiver cadastrado, você receberá instruções para redefinir sua senha.'})


@app.route('/reset-password/<token>', methods=['GET'])
def reset_password_form(token):
    return render_template('reset_senha.html', token=token)


@app.route('/reset-password', methods=['POST'])
def reset_password_post():
    token = request.form.get('token') if request.form else (request.json and request.json.get('token'))
    nova_senha = request.form.get('nova_senha') if request.form else (request.json and request.json.get('nova_senha'))
    if not token or not nova_senha:
        return jsonify({'success': False, 'message': 'Token e nova senha obrigatórios.'}), 400
    try:
        data = serializer.loads(token, salt='password-reset-salt', max_age=3600)
        idusuario = data.get('idusuario')
    except SignatureExpired:
        return jsonify({'success': False, 'message': 'Token expirado.'}), 400
    except BadSignature:
        return jsonify({'success': False, 'message': 'Token inválido.'}), 400
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("UPDATE ic_usuario_geral SET senha=%s WHERE idusuario=%s", (nova_senha, idusuario))
        con.commit()
        con.close()
        return jsonify({'success': True, 'message': 'Senha redefinida com sucesso.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao atualizar a senha: {str(e)}'}), 500





# Rota para servir o login.html como página inicial
@app.route('/')
def index():
    return render_template(
        'login.html',
        build_datetime=BUILD_DATETIME,
        build_version=BUILD_VERSION,
    )

# Rota para servir arquivos HTML da pasta frontend


# Rotas para servir os outros templates diretamente
@app.route('/principal.html')
def principal():
    return render_template('principal.html')

@app.route('/menu.html')
def menu():
    db_path = session.get('db_path', '')
    nome_medico = session.get('nome_medico', '')
    return render_template(
        'menu.html',
        db_path=db_path,
        nome_medico=nome_medico,
        build_datetime=BUILD_DATETIME,
        build_version=BUILD_VERSION,
    )

@app.route('/consulta_paciente.html')
def consulta_paciente_html():

    return render_template('consulta_paciente.html')


# Import consulta_paciente to register /api/consulta-paciente endpoint
import consulta_paciente

if __name__ == '__main__':
    import threading
    import webbrowser

    threading.Timer(1.0, lambda: webbrowser.open('http://localhost:8072')).start()
    app.run(host='0.0.0.0', port=8072, debug=False, use_reloader=False)
