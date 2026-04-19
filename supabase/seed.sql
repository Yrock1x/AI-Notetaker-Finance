-- Local-dev seed data. Not run in cloud Supabase.
--
-- Creates a demo org + a test deal + a membership for a dev user. The dev
-- user must be created first via the Supabase Auth API (email+password or
-- OAuth) because `auth.users` is owned by the platform and seeded rows
-- there break migrations.
--
-- Run after `supabase start` + creating a user with email
-- dev@cognisuite.local via `supabase auth`.

do $$
declare
    dev_user uuid;
    org_id uuid;
    deal_id uuid;
begin
    select id into dev_user from auth.users where email = 'dev@cognisuite.local';
    if dev_user is null then
        raise notice 'dev user not found — sign up dev@cognisuite.local first, then re-run seed';
        return;
    end if;

    insert into public.organizations (name, slug)
    values ('Meridian Capital Partners', 'meridian-capital')
    on conflict (slug) do update set name = excluded.name
    returning id into org_id;

    insert into public.org_memberships (org_id, user_id, role)
    values (org_id, dev_user, 'owner')
    on conflict (org_id, user_id) do nothing;

    insert into public.deals (org_id, name, target_company, deal_type, stage, created_by)
    values (org_id, 'Acme Co. Acquisition', 'Acme Co.', 'pe', 'diligence', dev_user)
    returning id into deal_id;

    insert into public.deal_memberships (deal_id, user_id, org_id, role, added_by)
    values (deal_id, dev_user, org_id, 'lead', dev_user)
    on conflict (deal_id, user_id) do nothing;

    raise notice 'Seeded org %, deal %', org_id, deal_id;
end
$$;
