-- Execute este script como superuser (ex.: psql -U postgres -d medsoft_medmigra -f grant_privileges.sql)
-- Substitua `public` pelo schema correto, se necessário.

GRANT USAGE ON SCHEMA public TO medsoft_master;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO medsoft_master;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO medsoft_master;

-- Comandos individuais (se preferir conceder tabela a tabela):
-- GRANT SELECT ON TABLE public.ic_usuario_geral TO medsoft_master;
-- GRANT SELECT ON TABLE public.ic_empresa_geral TO medsoft_master;
-- GRANT SELECT ON TABLE public.pacient TO medsoft_master;
-- GRANT SELECT ON TABLE public.consulta TO medsoft_master;
-- GRANT SELECT ON TABLE public.clinica TO medsoft_master;
-- GRANT SELECT ON TABLE public.agenda TO medsoft_master;
-- GRANT SELECT ON TABLE public.nomed TO medsoft_master;
