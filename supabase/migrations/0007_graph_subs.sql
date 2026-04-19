-- 0005_graph_subs.sql
--
-- Track Microsoft Graph change-notification subscriptions so a background
-- job can renew them before the ~2.9 day expiry.

create table if not exists public.graph_subscriptions (
    id text primary key,                     -- Graph's own subscription id
    org_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    resource text not null,                  -- e.g. 'communications/callRecords'
    client_state text not null,              -- echoed back as validation on every notification
    notification_url text not null,
    expiration timestamptz not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists graph_subscriptions_user
    on public.graph_subscriptions (user_id);
create index if not exists graph_subscriptions_expiration
    on public.graph_subscriptions (expiration)
    where is_active = true;

alter table public.graph_subscriptions enable row level security;
create policy graph_subscriptions_member_all
    on public.graph_subscriptions
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));
