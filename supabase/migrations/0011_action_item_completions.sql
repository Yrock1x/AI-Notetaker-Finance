-- 0011_action_item_completions.sql
--
-- Persists completion state for AI-extracted action items. The items
-- themselves live inside `analyses.structured_output` as a JSON array, so
-- they don't have stable database rows — but the analysis row does, and the
-- frontend already builds a deterministic key from `${analysis_id}-act-${i}`.
-- We store one row per (deal_id, action_key) so toggling = upsert / delete.
--
-- Cascade-deletes when the parent analysis is removed so we don't accumulate
-- orphaned completion rows after a re-run.

create table public.action_item_completions (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    deal_id uuid not null references public.deals(id) on delete cascade,
    analysis_id uuid not null references public.analyses(id) on delete cascade,
    action_key text not null,
    action_text text,
    completed_by uuid not null references auth.users(id),
    completed_at timestamptz not null default now(),
    unique (deal_id, action_key)
);

create index idx_action_item_completions_deal
    on public.action_item_completions(deal_id);

alter table public.action_item_completions enable row level security;

create policy action_item_completions_member_all
    on public.action_item_completions
    for all
    using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));
