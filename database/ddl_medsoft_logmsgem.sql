CREATE TABLE IF NOT EXISTS public.medsoft_logmsgem (
    codigo INTEGER NOT NULL PRIMARY KEY,
    datahoraenvio TIMESTAMP NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'),
    tipo VARCHAR(50) NULL,
    destino VARCHAR(255) NULL,
    mensagem INTEGER NULL,
    codclin INTEGER NULL,
    codagend INTEGER NULL,
    enviado VARCHAR(5) NULL DEFAULT 'Sim',
    motivoerro VARCHAR(100) NULL,
    messageid VARCHAR(255) NULL,
    conteudo TEXT NULL
);

ALTER TABLE public.medsoft_logmsgem
    ALTER COLUMN destino TYPE VARCHAR(255);

ALTER TABLE public.medsoft_logmsgem
    ADD COLUMN IF NOT EXISTS codclin INTEGER NULL;

ALTER TABLE public.medsoft_logmsgem
    ADD COLUMN IF NOT EXISTS codagend INTEGER NULL;

ALTER TABLE public.medsoft_logmsgem
    ADD COLUMN IF NOT EXISTS enviado VARCHAR(5) NULL DEFAULT 'Sim';

ALTER TABLE public.medsoft_logmsgem
    ADD COLUMN IF NOT EXISTS motivoerro VARCHAR(100) NULL;

ALTER TABLE public.medsoft_logmsgem
    ADD COLUMN IF NOT EXISTS messageid VARCHAR(255) NULL;

ALTER TABLE public.medsoft_logmsgem
    ADD COLUMN IF NOT EXISTS conteudo TEXT NULL;

CREATE INDEX IF NOT EXISTS medsoft_logmsgem_messageid_idx
    ON public.medsoft_logmsgem (messageid)
    WHERE messageid IS NOT NULL;

UPDATE public.medsoft_logmsgem
SET enviado = 'Sim'
WHERE enviado IS NULL;

ALTER TABLE public.medsoft_logmsgem
    ALTER COLUMN enviado SET DEFAULT 'Sim';

ALTER TABLE public.medsoft_logmsgem
    ALTER COLUMN datahoraenvio SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo');

CREATE SEQUENCE IF NOT EXISTS public.medsoft_logmsgem_codigo_seq;

SELECT setval(
    'public.medsoft_logmsgem_codigo_seq',
    COALESCE((SELECT MAX(codigo) FROM public.medsoft_logmsgem), 0) + 1,
    FALSE
);

ALTER TABLE public.medsoft_logmsgem
    ALTER COLUMN codigo SET DEFAULT nextval('public.medsoft_logmsgem_codigo_seq');

ALTER SEQUENCE public.medsoft_logmsgem_codigo_seq
    OWNED BY public.medsoft_logmsgem.codigo;

CREATE UNIQUE INDEX IF NOT EXISTS medsoft_logmsgem_codigo_uidx
    ON public.medsoft_logmsgem (codigo);

CREATE INDEX IF NOT EXISTS medsoft_logmsgem_codclin_data_idx
    ON public.medsoft_logmsgem (codclin, datahoraenvio DESC);

DROP INDEX IF EXISTS public.medsoft_logmsgem_auto_agenda_uidx;

CREATE UNIQUE INDEX medsoft_logmsgem_auto_agenda_uidx
    ON public.medsoft_logmsgem (codclin, codagend, mensagem)
    WHERE tipo = 'Email Auto'
      AND codagend IS NOT NULL
      AND enviado = 'Sim';

COMMENT ON TABLE public.medsoft_logmsgem IS
    'Histórico das tentativas de envio por e-mail ou WhatsApp.';
