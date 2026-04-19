-- 0003_calendar_sync.sql
--
-- Support calendar-synced meetings:
--   * Track the external event ID so re-sync upserts instead of duplicating.
--   * Make deal_id nullable (an unassigned synced event has no deal yet).
--   * Extend the source check constraint to cover the 'outlook' value so
--     Outlook-only events (that aren't Teams meetings) still have a home.

alter table public.meetings
    add column if not exists external_event_id text,
    add column if not exists external_provider text;

create unique index if not exists meetings_external_event_unique
    on public.meetings (org_id, external_provider, external_event_id)
    where external_event_id is not null;

-- deal_id was NOT NULL; relax it so unassigned synced events can live here.
alter table public.meetings alter column deal_id drop not null;

-- Extend the source check (current values: upload, zoom, teams, meet).
alter table public.meetings drop constraint if exists meetings_source_check;
alter table public.meetings add constraint meetings_source_check
    check (source in ('upload', 'zoom', 'teams', 'meet', 'outlook'));

-- RLS: the existing meetings policy is org-scoped by org_id which already
-- handles rows with deal_id IS NULL. No policy change required.

-- Helpful index for calendar views (upcoming meetings per org).
create index if not exists meetings_org_date
    on public.meetings (org_id, meeting_date);
