CREATE TABLE IF NOT EXISTS public.medsoft_configuracao (
    id SMALLINT,
    codclin INTEGER NOT NULL UNIQUE,
    smtp_host VARCHAR(255) NOT NULL DEFAULT '',
    smtp_porta INTEGER NOT NULL DEFAULT 0 CHECK (smtp_porta BETWEEN 0 AND 65535),
    smtp_usuario VARCHAR(255) NOT NULL DEFAULT '',
    smtp_senha TEXT NOT NULL DEFAULT '',
    smtp_remetente VARCHAR(255) NOT NULL DEFAULT '',
    smtp_tls BOOLEAN NOT NULL DEFAULT TRUE,
    smtp_ssl BOOLEAN NOT NULL DEFAULT FALSE,
    whatsapp_remetente VARCHAR(15) NOT NULL DEFAULT '5521986496127',
    whatsapp_phone_number_id VARCHAR(80) NOT NULL DEFAULT '',
    whatsapp_token TEXT NOT NULL DEFAULT '',
    whatsapp_api_version VARCHAR(20) NOT NULL DEFAULT '',
    whatsapp_template VARCHAR(120) NOT NULL DEFAULT '',
    whatsapp_idioma VARCHAR(10) NOT NULL DEFAULT 'pt_BR',
    WhatzapSimplificado VARCHAR(1) NOT NULL DEFAULT 'N'
        CHECK (WhatzapSimplificado IN ('S', 'N')),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por VARCHAR(120) NOT NULL DEFAULT '',
    CONSTRAINT medsoft_configuracao_smtp_seguranca_chk CHECK (NOT (smtp_tls AND smtp_ssl))
);

ALTER TABLE public.medsoft_configuracao
    ADD COLUMN IF NOT EXISTS WhatzapSimplificado VARCHAR(1) NOT NULL DEFAULT 'N';

COMMENT ON TABLE public.medsoft_configuracao IS
    'Configurações de integração para notificações da MedSoft.';
COMMENT ON COLUMN public.medsoft_configuracao.smtp_senha IS
    'Segredo: restringir acesso direto à tabela.';
COMMENT ON COLUMN public.medsoft_configuracao.whatsapp_token IS
    'Segredo: restringir acesso direto à tabela.';

REVOKE ALL ON TABLE public.medsoft_configuracao FROM PUBLIC;
