UPDATE public.texto
SET atalho = 'X'
WHERE atalho = 'E';

COMMENT ON COLUMN public.texto.atalho IS
    'Tipo: R receita, X exame, P procedimento, A anamnese, E mensagem de e-mail, Z mensagem de WhatsApp.';
