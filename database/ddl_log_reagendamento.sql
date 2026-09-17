DROP INDEX IF EXISTS public.medsoft_logmsgem_auto_agenda_uidx;

CREATE INDEX IF NOT EXISTS medsoft_logmsgem_agenda_envio_idx
    ON public.medsoft_logmsgem (codclin, codagend, mensagem, datahoraenvio DESC)
    WHERE codagend IS NOT NULL;

COMMENT ON INDEX public.medsoft_logmsgem_agenda_envio_idx IS
    'Permite histórico de novos envios quando data ou horário da agenda forem alterados.';
