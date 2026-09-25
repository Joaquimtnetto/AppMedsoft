-- Executar no banco da clínica com o proprietário da tabela consulta.
ALTER TABLE public.consulta
    ADD COLUMN IF NOT EXISTS ativo VARCHAR(5);
