-- Extend handle_new_auth_user so first-time sign-ins land on a usable
-- dashboard instead of an empty one with no org. Creates a personal org
-- named from the user's email (local-part) and marks them owner.
--
-- Idempotent: if the profile + org + membership already exist (re-runs
-- or profile backfill), the inserts silently no-op.

create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    profile_id uuid := new.id;
    derived_name text := coalesce(
        new.raw_user_meta_data ->> 'full_name',
        new.raw_user_meta_data ->> 'name',
        split_part(coalesce(new.email, ''), '@', 1)
    );
    org_name text := coalesce(derived_name, 'My') || '''s Workspace';
    base_slug text := regexp_replace(lower(coalesce(derived_name, 'user')), '[^a-z0-9]+', '-', 'g');
    final_slug text := base_slug;
    new_org_id uuid;
begin
    -- 1) Profile row
    insert into public.profiles (id, email, full_name, avatar_url)
    values (
        profile_id,
        coalesce(new.email, ''),
        coalesce(derived_name, ''),
        new.raw_user_meta_data ->> 'avatar_url'
    )
    on conflict (id) do nothing;

    -- 2) Skip org creation if the user already belongs to one (invite flow).
    if exists (select 1 from public.org_memberships where user_id = profile_id) then
        return new;
    end if;

    -- 3) Generate a unique slug. Collisions are rare; bail after 5 tries.
    for i in 1..5 loop
        exit when not exists (select 1 from public.organizations where slug = final_slug);
        final_slug := base_slug || '-' || substr(md5(random()::text), 1, 6);
    end loop;

    -- 4) Create org + owner membership.
    insert into public.organizations (name, slug)
    values (org_name, final_slug)
    returning id into new_org_id;

    insert into public.org_memberships (org_id, user_id, role)
    values (new_org_id, profile_id, 'owner');

    return new;
end
$$;
