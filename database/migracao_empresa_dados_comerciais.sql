ALTER TABLE public.ic_empresa_geral
    ADD COLUMN IF NOT EXISTS email VARCHAR(120),
    ADD COLUMN IF NOT EXISTS telefone VARCHAR(20),
    ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(20),
    ADD COLUMN IF NOT EXISTS idplano INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS datainicio DATE,
    ADD COLUMN IF NOT EXISTS pago VARCHAR(1) NOT NULL DEFAULT 'N',
    ADD COLUMN IF NOT EXISTS titulo1 VARCHAR(120),
    ADD COLUMN IF NOT EXISTS titulo2 VARCHAR(120);

ALTER TABLE public.ic_empresa_geral
    DROP CONSTRAINT IF EXISTS ic_empresa_geral_pago_check;

ALTER TABLE public.ic_empresa_geral
    ADD CONSTRAINT ic_empresa_geral_pago_check CHECK (pago IN ('S', 'N'));
