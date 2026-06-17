-- AUTO-GENERATED from the live backend schema (alembic upgrade head).
-- The Go worker must match the Python worker's SQLite schema exactly so it
-- can take over the same /data/app.db. Idempotent (IF NOT EXISTS) so it is a
-- no-op on the existing prod DB and builds a fresh dev/staging DB from zero.

CREATE TABLE IF NOT EXISTS action_item_completions (
	org_id VARCHAR NOT NULL, 
	deal_id VARCHAR NOT NULL, 
	analysis_id VARCHAR NOT NULL, 
	action_key VARCHAR NOT NULL, 
	action_text TEXT, 
	completed_by VARCHAR NOT NULL, 
	completed_at VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT action_item_completions_unique UNIQUE (deal_id, action_key), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(analysis_id) REFERENCES analyses (id) ON DELETE CASCADE, 
	FOREIGN KEY(completed_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS analyses (
	org_id VARCHAR NOT NULL, 
	meeting_id VARCHAR NOT NULL, 
	call_type VARCHAR NOT NULL, 
	structured_output JSON, 
	model_used VARCHAR NOT NULL, 
	prompt_version VARCHAR NOT NULL, 
	grounding_score FLOAT, 
	status VARCHAR NOT NULL, 
	error_message TEXT, 
	requested_by VARCHAR, 
	version INTEGER NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT analyses_status_chk CHECK (status in ('queued','running','completed','failed','partial')), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
	org_id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	deal_id VARCHAR, 
	action VARCHAR NOT NULL, 
	resource_type VARCHAR NOT NULL, 
	resource_id VARCHAR, 
	details JSON, 
	ip_address VARCHAR, 
	user_agent VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS deal_memberships (
	deal_id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	org_id VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	added_by VARCHAR, 
	added_at VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT deal_memberships_role_chk CHECK (role in ('lead','admin','analyst','viewer')), 
	CONSTRAINT deal_memberships_unique UNIQUE (deal_id, user_id), 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(added_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS deal_vdr_connections (
	deal_id VARCHAR NOT NULL, 
	org_id VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	vdr_id VARCHAR NOT NULL, 
	vdr_name VARCHAR, 
	status VARCHAR NOT NULL, 
	share_scopes JSON NOT NULL, 
	connected_by VARCHAR NOT NULL, 
	access_token_encrypted TEXT, 
	refresh_token_encrypted TEXT, 
	token_expires_at VARCHAR, 
	connected_at VARCHAR NOT NULL, 
	revoked_at VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT deal_vdr_connections_deal_unique UNIQUE (deal_id), 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(connected_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS deals (
	org_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	description TEXT, 
	target_company VARCHAR, 
	deal_type VARCHAR NOT NULL, 
	stage VARCHAR, 
	status VARCHAR NOT NULL, 
	created_by VARCHAR NOT NULL, 
	deleted_at VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS documents (
	org_id VARCHAR NOT NULL, 
	deal_id VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	document_type VARCHAR NOT NULL, 
	file_key VARCHAR NOT NULL, 
	file_size BIGINT NOT NULL, 
	extracted_text TEXT, 
	uploaded_by VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploaded_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS embeddings (
	org_id VARCHAR NOT NULL, 
	deal_id VARCHAR NOT NULL, 
	source_type VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	chunk_text TEXT NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	metadata JSON NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT embeddings_source_type_chk CHECK (source_type in ('transcript_segment','document_chunk')), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS graph_subscriptions (
	id VARCHAR NOT NULL, 
	org_id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	resource VARCHAR NOT NULL, 
	client_state VARCHAR NOT NULL, 
	notification_url VARCHAR NOT NULL, 
	expiration VARCHAR NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS integration_credentials (
	org_id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	platform VARCHAR NOT NULL, 
	access_token_encrypted TEXT NOT NULL, 
	refresh_token_encrypted TEXT, 
	token_expires_at VARCHAR, 
	scopes TEXT, 
	is_active BOOLEAN NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT integration_credentials_platform_chk CHECK (platform in ('zoom','microsoft','google','slack','teams','outlook')), 
	CONSTRAINT integration_credentials_unique UNIQUE (org_id, user_id, platform), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meeting_bot_sessions (
	org_id VARCHAR NOT NULL, 
	deal_id VARCHAR NOT NULL, 
	meeting_id VARCHAR, 
	platform VARCHAR NOT NULL, 
	meeting_url VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	scheduled_start VARCHAR, 
	actual_start VARCHAR, 
	actual_end VARCHAR, 
	recording_file_key VARCHAR, 
	recall_bot_id VARCHAR, 
	live_transcript_channel VARCHAR, 
	consent_obtained BOOLEAN NOT NULL, 
	created_by VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bot_sessions_platform_chk CHECK (platform in ('zoom','teams','google_meet')), 
	CONSTRAINT bot_sessions_status_chk CHECK (status in ('scheduled','joining','recording','completed','failed','cancelled')), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS meeting_chat_messages (
	meeting_id VARCHAR NOT NULL, 
	org_id VARCHAR NOT NULL, 
	sender_name VARCHAR, 
	sender_email VARCHAR, 
	text TEXT NOT NULL, 
	sent_at VARCHAR NOT NULL, 
	recall_message_id VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT meeting_chat_messages_recall_unique UNIQUE (recall_message_id), 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meeting_participants (
	meeting_id VARCHAR NOT NULL, 
	speaker_label VARCHAR NOT NULL, 
	speaker_name VARCHAR, 
	user_id VARCHAR, 
	recall_participant_id VARCHAR, 
	email_address VARCHAR, 
	joined_at VARCHAR, 
	left_at VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS meetings (
	org_id VARCHAR NOT NULL, 
	deal_id VARCHAR, 
	title VARCHAR NOT NULL, 
	meeting_date VARCHAR, 
	duration_seconds INTEGER, 
	source VARCHAR NOT NULL, 
	source_url VARCHAR, 
	file_key VARCHAR, 
	status VARCHAR NOT NULL, 
	error_message TEXT, 
	bot_enabled BOOLEAN NOT NULL, 
	external_event_id VARCHAR, 
	external_provider VARCHAR, 
	created_by VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES profiles (id)
);

CREATE TABLE IF NOT EXISTS org_memberships (
	org_id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	joined_at VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT org_memberships_role_chk CHECK (role in ('owner','admin','member')), 
	CONSTRAINT org_memberships_unique UNIQUE (org_id, user_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organizations (
	name VARCHAR NOT NULL, 
	slug VARCHAR NOT NULL, 
	domain VARCHAR, 
	settings JSON NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT organizations_slug_key UNIQUE (slug)
);

CREATE TABLE IF NOT EXISTS partner_api_keys (
	org_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	key_hash VARCHAR NOT NULL, 
	scopes JSON NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	last_used_at VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT partner_api_keys_hash_unique UNIQUE (key_hash), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profiles (
	email VARCHAR NOT NULL, 
	full_name VARCHAR NOT NULL, 
	avatar_url VARCHAR, 
	is_active BOOLEAN NOT NULL, 
	password_hash VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS qa_interactions (
	org_id VARCHAR NOT NULL, 
	deal_id VARCHAR NOT NULL, 
	meeting_id VARCHAR, 
	user_id VARCHAR NOT NULL, 
	question TEXT NOT NULL, 
	answer TEXT NOT NULL, 
	citations JSON NOT NULL, 
	grounding_score FLOAT, 
	model_used VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcript_segments (
	transcript_id VARCHAR, 
	meeting_id VARCHAR NOT NULL, 
	speaker_label VARCHAR NOT NULL, 
	speaker_name VARCHAR, 
	text TEXT NOT NULL, 
	start_time FLOAT NOT NULL, 
	end_time FLOAT NOT NULL, 
	confidence FLOAT, 
	segment_index INTEGER NOT NULL, 
	is_partial BOOLEAN NOT NULL, 
	recall_segment_id VARCHAR, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(transcript_id) REFERENCES transcripts (id) ON DELETE CASCADE, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcripts (
	org_id VARCHAR NOT NULL, 
	meeting_id VARCHAR NOT NULL, 
	full_text TEXT NOT NULL, 
	language VARCHAR NOT NULL, 
	deepgram_response JSON, 
	word_count INTEGER NOT NULL, 
	confidence_score FLOAT, 
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT transcripts_meeting_unique UNIQUE (meeting_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
    embedding_id TEXT PRIMARY KEY,
    deal_id TEXT PARTITION KEY,
    embedding FLOAT[768] distance_metric=cosine
);

CREATE INDEX IF NOT EXISTS action_item_completions_deal ON action_item_completions (deal_id);

CREATE INDEX IF NOT EXISTS analyses_meeting ON analyses (meeting_id);

CREATE INDEX IF NOT EXISTS analyses_org ON analyses (org_id);

CREATE INDEX IF NOT EXISTS audit_logs_org_created ON audit_logs (org_id, created_at);

CREATE INDEX IF NOT EXISTS audit_logs_resource ON audit_logs (resource_type, resource_id);

CREATE INDEX IF NOT EXISTS audit_logs_user ON audit_logs (user_id, created_at);

CREATE INDEX IF NOT EXISTS deal_memberships_user ON deal_memberships (user_id);

CREATE INDEX IF NOT EXISTS deal_vdr_connections_org_status ON deal_vdr_connections (org_id, status);

CREATE INDEX IF NOT EXISTS deals_org ON deals (org_id);

CREATE INDEX IF NOT EXISTS deals_org_created ON deals (org_id, created_at);

CREATE INDEX IF NOT EXISTS documents_deal ON documents (deal_id);

CREATE INDEX IF NOT EXISTS documents_org ON documents (org_id);

CREATE INDEX IF NOT EXISTS embeddings_deal ON embeddings (deal_id);

CREATE INDEX IF NOT EXISTS embeddings_source ON embeddings (source_type, source_id);

CREATE INDEX IF NOT EXISTS graph_subscriptions_expiry ON graph_subscriptions (expiration) WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS graph_subscriptions_user ON graph_subscriptions (user_id);

CREATE INDEX IF NOT EXISTS meeting_bot_sessions_deal ON meeting_bot_sessions (deal_id);

CREATE INDEX IF NOT EXISTS meeting_bot_sessions_status ON meeting_bot_sessions (org_id, status);

CREATE INDEX IF NOT EXISTS meeting_chat_messages_meeting ON meeting_chat_messages (meeting_id, sent_at);

CREATE INDEX IF NOT EXISTS meeting_participants_meeting ON meeting_participants (meeting_id);

CREATE UNIQUE INDEX IF NOT EXISTS meeting_participants_recall_unique ON meeting_participants (meeting_id, recall_participant_id) WHERE recall_participant_id is not null;

CREATE INDEX IF NOT EXISTS meetings_deal ON meetings (deal_id);

CREATE UNIQUE INDEX IF NOT EXISTS meetings_external_event_unique ON meetings (org_id, external_provider, external_event_id) WHERE external_event_id is not null;

CREATE INDEX IF NOT EXISTS meetings_org_date ON meetings (org_id, meeting_date);

CREATE INDEX IF NOT EXISTS meetings_org_status ON meetings (org_id, status);

CREATE INDEX IF NOT EXISTS org_memberships_user ON org_memberships (user_id);

CREATE INDEX IF NOT EXISTS partner_api_keys_org ON partner_api_keys (org_id);

CREATE UNIQUE INDEX IF NOT EXISTS profiles_email_key ON profiles (lower(email));

CREATE INDEX IF NOT EXISTS qa_interactions_deal ON qa_interactions (deal_id, created_at);

CREATE INDEX IF NOT EXISTS transcript_segments_meeting ON transcript_segments (meeting_id);

CREATE INDEX IF NOT EXISTS transcript_segments_order ON transcript_segments (meeting_id, start_time);

CREATE UNIQUE INDEX IF NOT EXISTS transcript_segments_recall_key ON transcript_segments (recall_segment_id) WHERE recall_segment_id is not null;

CREATE INDEX IF NOT EXISTS transcripts_org ON transcripts (org_id);
