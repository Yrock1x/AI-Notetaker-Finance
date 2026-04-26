-- 0009_rls_with_check.sql
--
-- Defense-in-depth: add explicit `with check (...)` clauses to RLS policies
-- that previously only declared `using (...)`. Without WITH CHECK, an
-- INSERT/UPDATE only verifies the *visibility* predicate, not the values
-- being written — a user who belongs to multiple orgs can write rows
-- stamped with another org's id.
--
-- Worst case fixed here: meeting_chat_messages has its own org_id column
-- but the policy only checks the parent meeting is visible. A user in orgs
-- A and B could insert a chat row referencing an org-A meeting while
-- stamping org_id = B, corrupting any analytic that aggregates by org_id.
-- embeddings has the same shape and is fixed identically.
--
-- transcript_segments and meeting_participants don't yet have org_id
-- columns, but pattern-consistency prevents future regressions when those
-- columns are added (and matches how 0008 wrote org_memberships policies).

-- ---------------------------------------------------------------------------
-- 1. embeddings — table has org_id; was missing WITH CHECK entirely.
-- ---------------------------------------------------------------------------
drop policy if exists embeddings_member_all on public.embeddings;
create policy embeddings_member_all on public.embeddings
    for all
    using (org_id in (select public.user_org_ids()))
    with check (org_id in (select public.user_org_ids()));

-- ---------------------------------------------------------------------------
-- 2. meeting_chat_messages — table has org_id (added in 0006). The original
--    policy only checked the meeting_id parent, leaving the org_id field
--    free to be mis-stamped on insert.
-- ---------------------------------------------------------------------------
drop policy if exists meeting_chat_messages_via_meeting on public.meeting_chat_messages;
create policy meeting_chat_messages_via_meeting on public.meeting_chat_messages
    for all
    using (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    )
    with check (
        org_id in (select public.user_org_ids())
        and meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    );

-- ---------------------------------------------------------------------------
-- 3. transcript_segments — meeting-scoped (no org_id column).
-- ---------------------------------------------------------------------------
drop policy if exists transcript_segments_via_meeting on public.transcript_segments;
create policy transcript_segments_via_meeting on public.transcript_segments
    for all
    using (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    )
    with check (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    );

-- ---------------------------------------------------------------------------
-- 4. meeting_participants — meeting-scoped (no org_id column).
-- ---------------------------------------------------------------------------
drop policy if exists meeting_participants_via_meeting on public.meeting_participants;
create policy meeting_participants_via_meeting on public.meeting_participants
    for all
    using (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    )
    with check (
        meeting_id in (
            select id from public.meetings where org_id in (select public.user_org_ids())
        )
    );
