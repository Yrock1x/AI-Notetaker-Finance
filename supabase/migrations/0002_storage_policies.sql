-- Storage RLS policies.
--
-- We have three private buckets — the frontend signs PUT URLs via the
-- worker but needs direct read access for downloads (and deliverables).
-- RLS on storage.objects is how Supabase enforces per-user access inside
-- the Storage service.
--
-- Path convention: every object key starts with the deal_id as its first
-- path segment, e.g. `{deal_id}/{uuid}.docx`. We decode that with
-- ``split_part(name, '/', 1)`` and check that the deal is org-visible.

-- storage.objects already has RLS enabled by default on hosted Supabase —
-- the platform owns the table so we can't `alter table` it anyway.

-- Helper: set of deal UUIDs visible to the current JWT user, via their
-- org memberships. Mirrors public.user_org_ids() in 0001_initial.sql.
create or replace function public.user_deal_ids()
returns setof uuid language sql stable security definer set search_path = public as $$
    select id from public.deals
    where org_id in (select public.user_org_ids())
      and deleted_at is null
$$;

-- Create buckets (idempotent).
insert into storage.buckets (id, name, public)
values
    ('meeting-recordings', 'meeting-recordings', false),
    ('deliverables', 'deliverables', false),
    ('deal-documents', 'deal-documents', false)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- meeting-recordings bucket
-- ---------------------------------------------------------------------------
-- Read: any deal member can stream their deal's recordings.
create policy "meeting-recordings: select by deal membership"
    on storage.objects for select
    using (
        bucket_id = 'meeting-recordings'
        and split_part(name, '/', 1)::uuid in (select public.user_deal_ids())
    );
-- Insert/update/delete are performed by the worker via the service role,
-- so no user policy is needed. (Service-role bypasses RLS.)

-- ---------------------------------------------------------------------------
-- deliverables bucket
-- ---------------------------------------------------------------------------
create policy "deliverables: select by deal membership"
    on storage.objects for select
    using (
        bucket_id = 'deliverables'
        and split_part(name, '/', 1)::uuid in (select public.user_deal_ids())
    );

-- ---------------------------------------------------------------------------
-- deal-documents bucket — users upload directly from the browser (see
-- frontend/src/hooks/use-documents.ts). They also read back for inline preview.
-- ---------------------------------------------------------------------------
create policy "deal-documents: select by deal membership"
    on storage.objects for select
    using (
        bucket_id = 'deal-documents'
        and split_part(name, '/', 1)::uuid in (select public.user_deal_ids())
    );

create policy "deal-documents: insert by deal membership"
    on storage.objects for insert
    with check (
        bucket_id = 'deal-documents'
        and split_part(name, '/', 1)::uuid in (select public.user_deal_ids())
    );

create policy "deal-documents: delete by deal membership"
    on storage.objects for delete
    using (
        bucket_id = 'deal-documents'
        and split_part(name, '/', 1)::uuid in (select public.user_deal_ids())
    );
