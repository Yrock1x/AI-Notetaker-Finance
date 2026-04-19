-- 0004_bot_capture.sql
--
-- Extend meeting_participants with a Recall.ai participant id so we can
-- upsert on participant_events, and add a new meeting_chat_messages table
-- for in-meeting chat captured by Recall.ai.

alter table public.meeting_participants
    add column if not exists recall_participant_id text,
    add column if not exists email_address text,
    add column if not exists joined_at timestamptz,
    add column if not exists left_at timestamptz;

create unique index if not exists meeting_participants_recall_unique
    on public.meeting_participants (meeting_id, recall_participant_id)
    where recall_participant_id is not null;

-- ---------------------------------------------------------------------------
-- meeting_chat_messages
-- ---------------------------------------------------------------------------
create table if not exists public.meeting_chat_messages (
    id uuid primary key default gen_random_uuid(),
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    org_id uuid not null references public.organizations(id) on delete cascade,
    sender_name text,
    sender_email text,
    text text not null,
    sent_at timestamptz not null,
    recall_message_id text unique,
    created_at timestamptz not null default now()
);
create index if not exists meeting_chat_messages_meeting
    on public.meeting_chat_messages (meeting_id, sent_at);

alter table public.meeting_chat_messages enable row level security;

create policy meeting_chat_messages_via_meeting
    on public.meeting_chat_messages
    for all using (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    );

-- Keep updated_at triggered for participants rows that previously lacked it.
-- (The generic set_updated_at trigger was installed at 0001; new columns
-- inherit it automatically.)
