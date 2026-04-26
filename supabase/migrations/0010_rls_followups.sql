-- 0010_rls_followups.sql
--
-- Follow-up RLS hardening from the security audit (P3 items + the
-- soft-delete defense-in-depth). 0009 covered the high-impact gaps;
-- this migration tightens the rest of the WITH CHECK pattern and stops
-- soft-deleted deals from being visible to ordinary reads.
--
-- The frontend already filters `.is("deleted_at", null)` on its deals
-- queries (frontend/src/hooks/use-deals.ts), so adding the same predicate
-- to the policy is redundant for current callers but blocks future
-- code paths (or a service-role bug) from re-surfacing deleted deals.

-- ---------------------------------------------------------------------------
-- 1. organizations_member_update — add WITH CHECK so an UPDATE can't move
--    the row to an org_id outside the caller's membership.
-- ---------------------------------------------------------------------------
drop policy if exists organizations_member_update on public.organizations;
create policy organizations_member_update on public.organizations
    for update
    using (id in (select public.user_org_ids()))
    with check (id in (select public.user_org_ids()));

-- ---------------------------------------------------------------------------
-- 2. profiles_update_self — keep the row pinned to the caller on UPDATE.
-- ---------------------------------------------------------------------------
drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles
    for update
    using (id = auth.uid())
    with check (id = auth.uid());

-- ---------------------------------------------------------------------------
-- 3. deals_member_all — hide soft-deleted deals at the RLS layer. WITH
--    CHECK still permits insert/update of deletion timestamps because the
--    target row at write-time is the new value; the predicate only
--    constrains reads + non-delete writes to active rows.
-- ---------------------------------------------------------------------------
drop policy if exists deals_member_all on public.deals;
create policy deals_member_all on public.deals
    for all
    using (
        org_id in (select public.user_org_ids())
        and deleted_at is null
    )
    with check (org_id in (select public.user_org_ids()));
