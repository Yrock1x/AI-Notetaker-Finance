-- 0002_oauth_platforms.sql
--
-- Expand the integration_credentials.platform check constraint to cover the
-- unified Microsoft OAuth row (Teams + Outlook + Calendar) and the new
-- Google OAuth row (Calendar + Meet).
--
-- We keep 'teams' and 'outlook' as legal values so old rows (if any) still
-- validate; new connections will be written as 'microsoft'.

alter table public.integration_credentials
    drop constraint if exists integration_credentials_platform_check;

alter table public.integration_credentials
    add constraint integration_credentials_platform_check
    check (
        platform in (
            'zoom',
            'microsoft',
            'google',
            'slack',
            -- legacy values, retained so existing rows don't break migrations
            'teams',
            'outlook'
        )
    );
