-- 0008_fix_membership_recursion.sql
--
-- The org_memberships_admin_write policy from 0001_initial referenced
-- org_memberships in its own USING clause, which Postgres evaluates as
-- a recursive policy check on SELECT. Any query against org_memberships
-- hits the wall with "infinite recursion detected in policy".
--
-- Fix: mirror the user_org_ids() pattern with a SECURITY DEFINER helper
-- that bypasses RLS when computing the caller's admin orgs, then scope
-- the policy to write operations only so SELECTs fall through to the
-- safe org_memberships_member_select policy.

create or replace function public.user_admin_org_ids()
returns setof uuid language sql stable security definer set search_path = public as $$
    select org_id from public.org_memberships
    where user_id = auth.uid() and role in ('owner', 'admin');
$$;

drop policy if exists org_memberships_admin_write on public.org_memberships;

create policy org_memberships_admin_insert on public.org_memberships
    for insert with check (org_id in (select public.user_admin_org_ids()));

create policy org_memberships_admin_update on public.org_memberships
    for update
    using (org_id in (select public.user_admin_org_ids()))
    with check (org_id in (select public.user_admin_org_ids()));

create policy org_memberships_admin_delete on public.org_memberships
    for delete using (org_id in (select public.user_admin_org_ids()));
