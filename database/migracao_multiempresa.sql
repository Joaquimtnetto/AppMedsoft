-- Execute no banco operacional antes de publicar a versão multiempresa.
-- Linhas antigas permanecem com CODCLIN nulo até serem atribuídas corretamente.

BEGIN;

ALTER TABLE IF EXISTS public.agenda ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.pacient ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.pacient ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE IF EXISTS public.consulta ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.plano ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.nomed ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.senha ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.texto ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.prefere ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.medsoft_configuracao ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.exame ADD COLUMN IF NOT EXISTS codclin INTEGER;
ALTER TABLE IF EXISTS public.exame ADD COLUMN IF NOT EXISTS idexame BIGSERIAL;
ALTER TABLE IF EXISTS public.exame ADD COLUMN IF NOT EXISTS observacao VARCHAR(300);

CREATE INDEX IF NOT EXISTS agenda_codclin_idx ON public.agenda (codclin);
CREATE INDEX IF NOT EXISTS pacient_codclin_idx ON public.pacient (codclin);
CREATE INDEX IF NOT EXISTS consulta_codclin_idx ON public.consulta (codclin);
CREATE INDEX IF NOT EXISTS plano_codclin_idx ON public.plano (codclin);
CREATE INDEX IF NOT EXISTS nomed_codclin_idx ON public.nomed (codclin);
CREATE INDEX IF NOT EXISTS senha_codclin_idx ON public.senha (codclin);
CREATE INDEX IF NOT EXISTS texto_codclin_idx ON public.texto (codclin);
CREATE INDEX IF NOT EXISTS prefere_codclin_idx ON public.prefere (codclin);
CREATE INDEX IF NOT EXISTS exame_codclin_codpac_idx ON public.exame (codclin, codpac);
CREATE UNIQUE INDEX IF NOT EXISTS medsoft_configuracao_codclin_uidx
    ON public.medsoft_configuracao (codclin) WHERE codclin IS NOT NULL;

-- A configuração antiga limitava a tabela a uma linha (id = 1).
DO $$
DECLARE
    constraint_row RECORD;
BEGIN
    IF to_regclass('public.medsoft_configuracao') IS NULL THEN
        RETURN;
    END IF;
    FOR constraint_row IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.medsoft_configuracao'::regclass
          AND (contype = 'p' OR (contype = 'c' AND pg_get_constraintdef(oid) ILIKE '%id%=%1%'))
    LOOP
        EXECUTE format(
            'ALTER TABLE public.medsoft_configuracao DROP CONSTRAINT %I',
            constraint_row.conname
        );
    END LOOP;
    ALTER TABLE public.medsoft_configuracao ALTER COLUMN id DROP NOT NULL;
END $$;

-- A chave antiga de EXAME era apenas NOME, impedindo nomes repetidos entre
-- pacientes e empresas. IDEXAME passa a identificar cada registro.
DO $$
DECLARE
    constraint_row RECORD;
BEGIN
    IF to_regclass('public.exame') IS NULL THEN
        RETURN;
    END IF;
    FOR constraint_row IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.exame'::regclass AND contype = 'p'
          AND NOT EXISTS (
              SELECT 1
              FROM unnest(conkey) key_number
              JOIN pg_attribute attribute
                ON attribute.attrelid = conrelid AND attribute.attnum = key_number
              WHERE attribute.attname = 'idexame'
          )
    LOOP
        EXECUTE format('ALTER TABLE public.exame DROP CONSTRAINT %I', constraint_row.conname);
    END LOOP;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.exame'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE public.exame ALTER COLUMN idexame SET NOT NULL;
        ALTER TABLE public.exame ADD CONSTRAINT exame_pkey PRIMARY KEY (idexame);
    END IF;
END $$;

COMMIT;

-- Após atribuir CODCLIN às linhas antigas, recomenda-se aplicar NOT NULL em cada tabela.
