-- CogniSuite — initial schema
--
-- 16 tables, RLS on every user-facing table, Realtime enabled on the
-- transcript_segments table so the Live transcription panel can subscribe.
--
-- Key design notes:
-- • Users come from Supabase Auth (auth.users). We mirror into public.profiles
--   via an on-signup trigger; every FK that used to point at users(id) now
--   points at profiles(id) (same UUID, FK on delete cascades through auth).
-- • Multi-tenancy is enforced by RLS using a helper `public.user_org_ids()`
--   that returns the set of org UUIDs the current user is a member of.
-- • Embeddings are 768-dim (Fireworks nomic-embed-text-v1.5).
-- • transcript_segments has `is_partial` + `recall_segment_id` for live
--   streaming support; an UPSERT on recall_segment_id replaces partials
--   with finalized text in place, preserving Realtime subscription order.

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists "vector";

-- ---------------------------------------------------------------------------
-- profiles (mirror of auth.users)
-- ---------------------------------------------------------------------------
create table public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    full_name text not null default '',
    avatar_url text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index profiles_email_key on public.profiles (lower(email));

-- Auto-create a profile row when a Supabase Auth user is created.
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    insert into public.profiles (id, email, full_name, avatar_url)
    values (
        new.id,
        coalesce(new.email, ''),
        coalesce(new.raw_user_meta_data ->> 'full_name',
                 new.raw_user_meta_data ->> 'name',
                 split_part(new.email, '@', 1)),
        new.raw_user_meta_data ->> 'avatar_url'
    )
    on conflict (id) do nothing;
    return new;
end
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_auth_user();

-- ---------------------------------------------------------------------------
-- organizations + memberships
-- ---------------------------------------------------------------------------
create table public.organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text not null,
    domain text,
    settings jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index organizations_slug_key on public.organizations (slug);

create table public.org_memberships (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    role text not null default 'member' check (role in ('owner','admin','member')),
    joined_at timestamptz not null default now()
);
create unique index org_memberships_unique on public.org_memberships (org_id, user_id);
create index org_memberships_user on public.org_memberships (user_id);

-- ---------------------------------------------------------------------------
-- Helper: set of org UUIDs the current JWT user belongs to.
-- Used by every RLS policy so we don't repeat the subquery everywhere.
-- ---------------------------------------------------------------------------
create or replace function public.user_org_ids()
returns setof uuid language sql stable security definer set search_path = public as $$
    select org_id from public.org_memberships where user_id = auth.uid();
$$;

-- ---------------------------------------------------------------------------
-- deals + deal_memberships
-- ---------------------------------------------------------------------------
create table public.deals (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    name text not null,
    description text,
    target_company text,
    deal_type text not null default 'general',
    stage text,
    status text not null default 'active',
    created_by uuid not null references public.profiles(id),
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index deals_org on public.deals (org_id);
create index deals_org_created on public.deals (org_id, created_at desc);

create table public.deal_memberships (
    id uuid primary key default gen_random_uuid(),
    deal_id uuid not null references public.deals(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    org_id uuid not null references public.organizations(id) on delete cascade,
    role text not null default 'analyst' check (role in ('lead','admin','analyst','viewer')),
    added_by uuid references public.profiles(id),
    added_at timestamptz not null default now()
);
create unique index deal_memberships_unique on public.deal_memberships (deal_id, user_id);
create index deal_memberships_user on public.deal_memberships (user_id);

-- ---------------------------------------------------------------------------
-- meetings + participants + bot sessions
-- ---------------------------------------------------------------------------
create table public.meetings (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    deal_id uuid not null references public.deals(id) on delete cascade,
    title text not null,
    meeting_date timestamptz,
    duration_seconds integer,
    source text not null default 'upload',
    source_url text,
    file_key text,
    status text not null default 'uploading',
    error_message text,
    bot_enabled boolean not null default true,
    created_by uuid not null references public.profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index meetings_deal on public.meetings (deal_id);
create index meetings_org_status on public.meetings (org_id, status);

create table public.meeting_participants (
    id uuid primary key default gen_random_uuid(),
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    speaker_label text not null,
    speaker_name text,
    user_id uuid references public.profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index meeting_participants_meeting on public.meeting_participants (meeting_id);

create table public.meeting_bot_sessions (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    deal_id uuid not null references public.deals(id) on delete cascade,
    meeting_id uuid references public.meetings(id) on delete cascade,
    platform text not null check (platform in ('zoom','teams','google_meet')),
    meeting_url text not null,
    status text not null default 'scheduled'
        check (status in ('scheduled','joining','recording','completed','failed','cancelled')),
    scheduled_start timestamptz,
    actual_start timestamptz,
    actual_end timestamptz,
    recording_file_key text,
    recall_bot_id text,
    -- Denormalized Realtime channel name so the Live panel knows where to
    -- subscribe without having to compute it client-side.
    live_transcript_channel text,
    consent_obtained boolean not null default false,
    created_by uuid not null references public.profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index meeting_bot_sessions_deal on public.meeting_bot_sessions (deal_id);
create index meeting_bot_sessions_status on public.meeting_bot_sessions (org_id, status);

-- ---------------------------------------------------------------------------
-- transcripts + segments (+ live streaming columns)
-- ---------------------------------------------------------------------------
create table public.transcripts (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    meeting_id uuid not null unique references public.meetings(id) on delete cascade,
    full_text text not null default '',
    language text not null default 'en',
    deepgram_response jsonb,
    word_count integer not null default 0,
    confidence_score real,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index transcripts_org on public.transcripts (org_id);

create table public.transcript_segments (
    id uuid primary key default gen_random_uuid(),
    transcript_id uuid references public.transcripts(id) on delete cascade,
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    speaker_label text not null,
    speaker_name text,
    text text not null,
    start_time real not null,
    end_time real not null,
    confidence real,
    segment_index integer not null,

    -- Live-streaming fields (Phase 5.5).
    -- is_partial=true marks a segment that may still be updated; an UPSERT
    -- keyed on recall_segment_id replaces it with the finalized text.
    is_partial boolean not null default false,
    recall_segment_id text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index transcript_segments_recall_key
    on public.transcript_segments (recall_segment_id)
    where recall_segment_id is not null;
create index transcript_segments_meeting on public.transcript_segments (meeting_id);
create index transcript_segments_order
    on public.transcript_segments (meeting_id, start_time);

-- ---------------------------------------------------------------------------
-- documents (files uploaded against a deal)
-- ---------------------------------------------------------------------------
create table public.documents (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    deal_id uuid not null references public.deals(id) on delete cascade,
    title text not null,
    document_type text not null,
    file_key text not null,
    file_size bigint not null default 0,
    extracted_text text,
    uploaded_by uuid not null references public.profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index documents_deal on public.documents (deal_id);
create index documents_org on public.documents (org_id);

-- ---------------------------------------------------------------------------
-- analyses (LLM-driven meeting analyses)
-- ---------------------------------------------------------------------------
create table public.analyses (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    call_type text not null,
    structured_output jsonb,
    model_used text not null,
    prompt_version text not null default 'v1',
    grounding_score real,
    status text not null default 'running'
        check (status in ('queued','running','completed','failed')),
    error_message text,
    requested_by uuid references public.profiles(id),
    version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index analyses_meeting on public.analyses (meeting_id);
create index analyses_org on public.analyses (org_id);

-- ---------------------------------------------------------------------------
-- embeddings (pgvector, 768-dim for Fireworks nomic-embed-text-v1.5)
-- ---------------------------------------------------------------------------
create table public.embeddings (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    deal_id uuid not null references public.deals(id) on delete cascade,
    source_type text not null check (source_type in ('transcript_segment','document_chunk')),
    source_id uuid not null,
    chunk_text text not null,
    chunk_index integer not null default 0,
    embedding vector(768),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index embeddings_deal on public.embeddings (deal_id);
create index embeddings_source on public.embeddings (source_type, source_id);
-- Approximate NN index for semantic search.
create index embeddings_vector_idx
    on public.embeddings using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- qa_interactions
-- ---------------------------------------------------------------------------
create table public.qa_interactions (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    deal_id uuid not null references public.deals(id) on delete cascade,
    meeting_id uuid references public.meetings(id) on delete set null,
    user_id uuid not null references public.profiles(id) on delete cascade,
    question text not null,
    answer text not null,
    citations jsonb not null default '[]'::jsonb,
    grounding_score real,
    model_used text not null,
    created_at timestamptz not null default now()
);
create index qa_interactions_deal on public.qa_interactions (deal_id, created_at desc);

-- ---------------------------------------------------------------------------
-- integration_credentials (OAuth tokens, Fernet-encrypted)
-- ---------------------------------------------------------------------------
create table public.integration_credentials (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    platform text not null check (platform in ('zoom','teams','slack','outlook')),
    access_token_encrypted text not null,
    refresh_token_encrypted text,
    token_expires_at timestamptz,
    scopes text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index integration_credentials_unique
    on public.integration_credentials (org_id, user_id, platform);

-- ---------------------------------------------------------------------------
-- audit_logs
-- ---------------------------------------------------------------------------
create table public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid references public.profiles(id) on delete set null,
    deal_id uuid references public.deals(id) on delete set null,
    action text not null,
    resource_type text not null,
    resource_id uuid,
    details jsonb,
    ip_address text,
    user_agent text,
    created_at timestamptz not null default now()
);
create index audit_logs_org_created on public.audit_logs (org_id, created_at desc);
create index audit_logs_user on public.audit_logs (user_id, created_at desc);
create index audit_logs_resource on public.audit_logs (resource_type, resource_id);

-- ---------------------------------------------------------------------------
-- Generic updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end
$$;

do $$
declare t text;
begin
    for t in
        select table_name from information_schema.columns
        where table_schema = 'public' and column_name = 'updated_at'
    loop
        execute format(
            'create trigger set_updated_at
             before update on public.%I
             for each row execute function public.set_updated_at()',
             t
        );
    end loop;
end
$$;

-- ---------------------------------------------------------------------------
-- Row-level security
-- Pattern: any row whose org_id is in public.user_org_ids() is visible.
-- Writes are allowed to members; deal-level RBAC is checked in app code
-- for now (can be moved into policies later with a deal_access view).
-- ---------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.org_memberships enable row level security;
alter table public.deals enable row level security;
alter table public.deal_memberships enable row level security;
alter table public.meetings enable row level security;
alter table public.meeting_participants enable row level security;
alter table public.meeting_bot_sessions enable row level security;
alter table public.transcripts enable row level security;
alter table public.transcript_segments enable row level security;
alter table public.documents enable row level security;
alter table public.analyses enable row level security;
alter table public.embeddings enable row level security;
alter table public.qa_interactions enable row level security;
alter table public.integration_credentials enable row level security;
alter table public.audit_logs enable row level security;

-- profiles: a user can read any profile that shares an org; can update own.
create policy profiles_read_same_org on public.profiles
    for select using (
        id = auth.uid()
        or exists (
            select 1 from public.org_memberships m1
            join public.org_memberships m2 on m2.org_id = m1.org_id
            where m1.user_id = auth.uid() and m2.user_id = profiles.id
        )
    );
create policy profiles_update_self on public.profiles
    for update using (id = auth.uid());

-- organizations: visible to members; updates need owner/admin (app-enforced).
create policy organizations_member_select on public.organizations
    for select using (id in (select public.user_org_ids()));
create policy organizations_member_update on public.organizations
    for update using (id in (select public.user_org_ids()));

-- org_memberships: visible to co-members.
create policy org_memberships_member_select on public.org_memberships
    for select using (org_id in (select public.user_org_ids()));
create policy org_memberships_admin_write on public.org_memberships
    for all using (
        org_id in (
            select org_id from public.org_memberships
            where user_id = auth.uid() and role in ('owner','admin')
        )
    )
    with check (
        org_id in (
            select org_id from public.org_memberships
            where user_id = auth.uid() and role in ('owner','admin')
        )
    );

-- Org-scoped tables — one policy per table, same shape.
-- Generated inline for clarity.
create policy deals_member_all on public.deals
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy deal_memberships_member_all on public.deal_memberships
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy meetings_member_all on public.meetings
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy meeting_participants_via_meeting on public.meeting_participants
    for all using (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    );

create policy meeting_bot_sessions_member_all on public.meeting_bot_sessions
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy transcripts_member_all on public.transcripts
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy transcript_segments_via_meeting on public.transcript_segments
    for all using (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    );

create policy documents_member_all on public.documents
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy analyses_member_all on public.analyses
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy embeddings_member_all on public.embeddings
    for all using (org_id in (select public.user_org_ids()));

create policy qa_interactions_member_all on public.qa_interactions
    for all using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

create policy integration_credentials_own_all on public.integration_credentials
    for all using (user_id = auth.uid());

create policy audit_logs_member_select on public.audit_logs
    for select using (org_id in (select public.user_org_ids()));

-- ---------------------------------------------------------------------------
-- RPC: vector search for QA
-- ---------------------------------------------------------------------------
-- Cosine-similarity search against the embeddings table, scoped to a deal.
-- Called from the worker's QAService; SECURITY INVOKER so caller's RLS
-- applies (service-role bypasses, user tokens are org-scoped).
create or replace function public.match_embeddings_for_deal(
    p_deal_id uuid,
    p_query vector(768),
    p_top_k integer default 15,
    p_min_similarity real default 0.3
)
returns table (
    id uuid,
    source_type text,
    source_id uuid,
    chunk_text text,
    similarity real,
    metadata jsonb
) language sql stable as $$
    select
        e.id,
        e.source_type,
        e.source_id,
        e.chunk_text,
        1 - (e.embedding <=> p_query) as similarity,
        e.metadata
    from public.embeddings e
    where e.deal_id = p_deal_id
      and e.embedding is not null
      and 1 - (e.embedding <=> p_query) >= p_min_similarity
    order by e.embedding <=> p_query
    limit p_top_k
$$;

-- ---------------------------------------------------------------------------
-- Realtime publication (for live transcript streaming)
-- ---------------------------------------------------------------------------
-- Supabase creates a publication called supabase_realtime on startup; we
-- just need to add the tables we want to broadcast. RLS policies apply to
-- the Realtime stream automatically.
alter publication supabase_realtime add table public.transcript_segments;
alter publication supabase_realtime add table public.meeting_bot_sessions;
alter publication supabase_realtime add table public.meetings;
