BEGIN;

LOCK TABLE public.medsoft_configuracao IN ACCESS EXCLUSIVE MODE;

ALTER TABLE public.medsoft_configuracao
    DROP CONSTRAINT IF EXISTS medsoft_configuracao_id_check;

CREATE SEQUENCE IF NOT EXISTS public.medsoft_configuracao_id_seq AS smallint;

SELECT setval(
    'public.medsoft_configuracao_id_seq',
    GREATEST(COALESCE(MAX(id), 0), 1),
    true
)
FROM public.medsoft_configuracao;

ALTER TABLE public.medsoft_configuracao
    ALTER COLUMN id SET DEFAULT nextval('public.medsoft_configuracao_id_seq'::regclass);

ALTER SEQUENCE public.medsoft_configuracao_id_seq
    OWNED BY public.medsoft_configuracao.id;

CREATE UNIQUE INDEX IF NOT EXISTS medsoft_configuracao_codclin_uidx
    ON public.medsoft_configuracao (codclin)
    WHERE codclin IS NOT NULL;

COMMIT;
