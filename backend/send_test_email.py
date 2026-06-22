import sys
import logging
import smtplib
from email.message import EmailMessage
import config


def send_email(to_address, subject, body, html_body=None):
    if not getattr(config, 'SMTP_HOST', ''):
        print('SMTP não está configurado em config.py (MEDSOFT_SMTP_HOST).')
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
        return True
    except Exception:
        logging.exception('Falha ao enviar e-mail')
        return False


def main():
    if len(sys.argv) > 1:
        to_addr = sys.argv[1]
    else:
        to_addr = input('Destinatário (e-mail) para teste: ').strip()
    if not to_addr:
        print('Destinatário obrigatório.')
        return
    subject = 'Teste de envio MedSoft'
    body = 'Este é um e-mail de teste enviado pelo script send_test_email.py'
    html = '<p>Este é um <strong>teste</strong> enviado pelo script <code>send_test_email.py</code>.</p>'
    ok = send_email(to_addr, subject, body, html_body=html)
    if ok:
        print('E-mail enviado com sucesso para', to_addr)
    else:
        print('Falha ao enviar e-mail. Confira as variáveis de ambiente e os logs.')


if __name__ == '__main__':
    main()
