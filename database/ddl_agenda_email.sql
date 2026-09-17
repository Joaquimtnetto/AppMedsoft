ALTER TABLE public.agenda
    ADD COLUMN IF NOT EXISTS email VARCHAR(120);

COMMENT ON COLUMN public.agenda.email IS
    'E-mail de contato informado no agendamento.';
