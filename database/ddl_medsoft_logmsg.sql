CREATE TABLE IF NOT EXISTS public.medsoft_logmsg (
    codigo INTEGER NOT NULL,
    datahoraenvio TIMESTAMP NULL,
    tipo VARCHAR(50) NULL,
    destino VARCHAR(255) NULL,
    mensagem INTEGER NULL,
    codclin INTEGER NULL
);

ALTER TABLE public.medsoft_logmsg
    ALTER COLUMN destino TYPE VARCHAR(255);

ALTER TABLE public.medsoft_logmsg
    ADD COLUMN IF NOT EXISTS codclin INTEGER NULL;

CREATE SEQUENCE IF NOT EXISTS public.medsoft_logmsg_codigo_seq;

SELECT setval(
    'public.medsoft_logmsg_codigo_seq',
    COALESCE((SELECT MAX(codigo) FROM public.medsoft_logmsg), 0) + 1,
    FALSE
);

ALTER TABLE public.medsoft_logmsg
    ALTER COLUMN codigo SET DEFAULT nextval('public.medsoft_logmsg_codigo_seq');

ALTER SEQUENCE public.medsoft_logmsg_codigo_seq
    OWNED BY public.medsoft_logmsg.codigo;

CREATE UNIQUE INDEX IF NOT EXISTS medsoft_logmsg_codigo_uidx
    ON public.medsoft_logmsg (codigo);

CREATE INDEX IF NOT EXISTS medsoft_logmsg_codclin_data_idx
    ON public.medsoft_logmsg (codclin, datahoraenvio DESC);

GRANT SELECT, INSERT ON TABLE public.medsoft_logmsg TO medsoft_master;
GRANT USAGE, SELECT ON SEQUENCE public.medsoft_logmsg_codigo_seq TO medsoft_master;

COMMENT ON TABLE public.medsoft_logmsg IS
    'Histórico das mensagens entregues ao provedor de e-mail ou WhatsApp.';
