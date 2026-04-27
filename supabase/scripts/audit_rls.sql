-- audit_rls.sql
--
-- Continuous RLS hygiene check — recommended by the security audit's
-- "Continuous checks to add" section. Run periodically (CI cron, daily
-- manual sweep, pre-deploy step) to catch regressions where a new public
-- table ships without RLS or a policy is missing WITH CHECK.
--
-- Usage:
--   supabase db execute -f supabase/scripts/audit_rls.sql
-- Or against a connection string:
--   psql "$SUPABASE_DB_URL" -f supabase/scripts/audit_rls.sql
--
-- What it flags:
--   1. Tables in `public` with RLS disabled.
--   2. Tables in `public` with RLS enabled but zero policies (silently
--      denies all access — usually a bug).
--   3. Policies that have a USING expression but no WITH CHECK on
--      INSERT/UPDATE/ALL — the gap that 0009 and 0010 closed and that
--      the audit identified as a multi-tenant write hazard.
--
-- The script is read-only — every query is a SELECT against pg_catalog.
-- Empty result sets mean "no issues in that category".

\echo
\echo === Tables in public.* with RLS disabled ===
\echo (any row here is a hole — every public table that holds tenant data
\echo  must have RLS enabled and at least one policy.)
\echo
select
    n.nspname as schema,
    c.relname as table_name,
    c.relrowsecurity as rls_enabled
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r'
  and n.nspname = 'public'
  and c.relrowsecurity is false
order by c.relname;

\echo
\echo === Tables with RLS enabled but zero policies ===
\echo (RLS-enabled tables with no policies silently deny everything; almost
\echo  always a misconfiguration unless the table is service-role-only.)
\echo
select
    c.relname as table_name
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r'
  and n.nspname = 'public'
  and c.relrowsecurity is true
  and not exists (
      select 1 from pg_policy p where p.polrelid = c.oid
  )
order by c.relname;

\echo
\echo === Policies that allow writes without WITH CHECK ===
\echo (policies covering INSERT/UPDATE/ALL must declare with_check, otherwise
\echo  a user with visibility on a row can stamp arbitrary new column values
\echo  on it — the cross-org write hazard the audit flagged.)
\echo
select
    c.relname as table_name,
    p.polname as policy_name,
    case p.polcmd
        when 'r' then 'SELECT'
        when 'a' then 'INSERT'
        when 'w' then 'UPDATE'
        when 'd' then 'DELETE'
        when '*' then 'ALL'
        else p.polcmd::text
    end as command
from pg_policy p
join pg_class c on c.oid = p.polrelid
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and p.polcmd in ('a', 'w', '*')
  and p.polwithcheck is null
order by c.relname, p.polname;

\echo
\echo === RLS audit complete ===
\echo (a clean run prints three empty result sets above this line.)
