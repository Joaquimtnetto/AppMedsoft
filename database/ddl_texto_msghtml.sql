ALTER TABLE public.texto
    ADD COLUMN IF NOT EXISTS msghtml BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE public.texto
SET msghtml = TRUE
WHERE codclin = 2
  AND codigo = 2;

COMMENT ON COLUMN public.texto.msghtml IS
    'Indica que o conteúdo do campo texto deve ser enviado como HTML.';
