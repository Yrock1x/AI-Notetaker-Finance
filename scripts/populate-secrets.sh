#!/usr/bin/env bash
###############################################################################
# CogniSuite – Populate Secrets Manager
#
# After `terraform apply`, run this script to populate runtime secrets.
#
# Usage:
#   ./scripts/populate-secrets.sh <env> [--from-file <file>] [--dry-run]
#
#   env:              dev | staging | prod
#   --from-file FILE: read KEY=VALUE pairs from a dotenv-style file
#                     (keys listed below). Prompts interactively for any
#                     missing values.
#   --dry-run:        print the `aws secretsmanager put-secret-value` commands
#                     but do not execute them.
#
# The token_encryption_key Fernet value is auto-generated if not provided —
# other secrets must come from the env file or interactive prompt.
###############################################################################
set -euo pipefail

ENV="${1:-}"
if [[ -z "${ENV}" ]]; then
  echo "usage: $0 <dev|staging|prod> [--from-file FILE] [--dry-run]" >&2
  exit 2
fi
shift

if [[ "${ENV}" != "dev" && "${ENV}" != "staging" && "${ENV}" != "prod" ]]; then
  echo "error: env must be dev|staging|prod (got '${ENV}')" >&2
  exit 2
fi

FROM_FILE=""
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-file)   FROM_FILE="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    *)             echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

REGION="${AWS_REGION:-us-east-1}"
TF_DIR="infrastructure/terraform/environments/${ENV}"

if [[ "${ENV}" == "prod" && "${DRY_RUN}" -eq 0 && "${CONFIRM_PROD:-}" != "yes" ]]; then
  echo "refusing to write to prod secrets without CONFIRM_PROD=yes" >&2
  exit 3
fi

# --- helpers ----------------------------------------------------------------

declare -A VALUES

load_from_file() {
  local file="$1"
  [[ -f "$file" ]] || { echo "env file not found: $file" >&2; exit 2; }
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$key" ]] && continue
    value="${value%\"}"; value="${value#\"}"
    VALUES["$key"]="$value"
  done < <(grep -v '^\s*$' "$file")
}

get_value() {
  # $1 = key, $2 = prompt, $3 = optional default
  local key="$1" prompt="$2" default="${3:-}"
  if [[ -n "${VALUES[$key]:-}" ]]; then
    echo "${VALUES[$key]}"
    return
  fi
  if [[ -n "$default" ]]; then
    echo "$default"
    return
  fi
  # Interactive prompt (stderr so captured via $()) returns clean
  local value
  read -r -s -p "  $prompt: " value >&2
  echo >&2
  echo "$value"
}

put_secret() {
  # $1 = secret-id suffix, $2 = value
  local suffix="$1" value="$2"
  local full_id="cognisuite/${ENV}/${suffix}"
  if [[ -z "$value" ]]; then
    echo "  [skip] $full_id (empty)"
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] aws secretsmanager put-secret-value --secret-id ${full_id} --secret-string '<redacted>' --region ${REGION}"
    return
  fi
  aws secretsmanager put-secret-value \
    --secret-id "$full_id" \
    --secret-string "$value" \
    --region "$REGION" \
    --output text --query VersionId > /dev/null
  echo "  [ok] $full_id"
}

# --- load from file if provided ---------------------------------------------

if [[ -n "$FROM_FILE" ]]; then
  load_from_file "$FROM_FILE"
  echo "loaded $(wc -l < "$FROM_FILE" | tr -d ' ') lines from $FROM_FILE"
fi

echo "=== CogniSuite – Populating secrets (${ENV}) ==="

# --- generated secrets ------------------------------------------------------

if [[ -z "${VALUES[TOKEN_ENCRYPTION_KEY]:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    FERNET_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
    VALUES[TOKEN_ENCRYPTION_KEY]="$FERNET_KEY"
    echo "generated new Fernet token_encryption_key"
  else
    echo "python3 not available — provide TOKEN_ENCRYPTION_KEY in the env file" >&2
    exit 4
  fi
fi

if [[ -z "${VALUES[APP_SECRET_KEY]:-}" ]]; then
  VALUES[APP_SECRET_KEY]=$(openssl rand -hex 32)
  echo "generated new APP_SECRET_KEY"
fi

# --- core runtime -----------------------------------------------------------

RDS_ENDPOINT=$(cd "${TF_DIR}" 2>/dev/null && terraform output -raw rds_endpoint 2>/dev/null || echo "")
REDIS_ENDPOINT=$(cd "${TF_DIR}" 2>/dev/null && terraform output -raw elasticache_endpoint 2>/dev/null || echo "")

put_secret "app-secret-key"       "${VALUES[APP_SECRET_KEY]}"
put_secret "token-encryption-key" "${VALUES[TOKEN_ENCRYPTION_KEY]}"

DATABASE_URL=$(get_value DATABASE_URL "DATABASE_URL (e.g. postgresql+asyncpg://user:pw@${RDS_ENDPOINT:-HOST}:5432/cognisuite)" "")
put_secret "database-url" "$DATABASE_URL"

REDIS_URL=$(get_value REDIS_URL "REDIS_URL (e.g. rediss://:AUTH@${REDIS_ENDPOINT:-HOST}:6379/0)" "")
put_secret "redis-url" "$REDIS_URL"

# --- third-party API keys ---------------------------------------------------

put_secret "anthropic-api-key"  "$(get_value ANTHROPIC_API_KEY  'ANTHROPIC_API_KEY (sk-ant-...)')"
put_secret "openai-api-key"     "$(get_value OPENAI_API_KEY     'OPENAI_API_KEY (sk-...)')"
put_secret "google-api-key"     "$(get_value GOOGLE_API_KEY     'GOOGLE_API_KEY (Gemini)')"
put_secret "deepgram-api-key"   "$(get_value DEEPGRAM_API_KEY   'DEEPGRAM_API_KEY')"
put_secret "recall-api-key"     "$(get_value RECALL_API_KEY     'RECALL_API_KEY')"
put_secret "supabase-jwt-secret" "$(get_value SUPABASE_JWT_SECRET 'SUPABASE_JWT_SECRET (blank if not using)' '')"
put_secret "assemblyai-api-key" "$(get_value ASSEMBLYAI_API_KEY 'ASSEMBLYAI_API_KEY (legacy — blank if unused)' '')"

# --- OAuth clients (JSON-encoded) -------------------------------------------

put_oauth() {
  local platform="$1"
  local cid_key="$2" csecret_key="$3"
  local cid csecret
  cid=$(get_value "$cid_key" "${platform} OAuth client_id" "")
  csecret=$(get_value "$csecret_key" "${platform} OAuth client_secret" "")
  if [[ -z "$cid" && -z "$csecret" ]]; then
    put_secret "${platform,,}-oauth" ""
    return
  fi
  local json
  json=$(python3 -c "import json,sys; print(json.dumps({'client_id':sys.argv[1],'client_secret':sys.argv[2]}))" "$cid" "$csecret")
  put_secret "${platform,,}-oauth" "$json"
}

put_oauth "Zoom"    ZOOM_CLIENT_ID    ZOOM_CLIENT_SECRET
put_oauth "Teams"   TEAMS_CLIENT_ID   TEAMS_CLIENT_SECRET
put_oauth "Slack"   SLACK_CLIENT_ID   SLACK_CLIENT_SECRET
put_oauth "Outlook" OUTLOOK_CLIENT_ID OUTLOOK_CLIENT_SECRET

# --- webhook secrets (JSON-encoded) -----------------------------------------

ZOOM_WH=$(get_value ZOOM_WEBHOOK_SECRET_TOKEN 'ZOOM_WEBHOOK_SECRET_TOKEN' '')
SLACK_WH=$(get_value SLACK_SIGNING_SECRET 'SLACK_SIGNING_SECRET' '')
TEAMS_WH=$(get_value TEAMS_WEBHOOK_SECRET 'TEAMS_WEBHOOK_SECRET' '')
WEBHOOK_JSON=$(python3 -c "import json,sys; print(json.dumps({'zoom_webhook_secret_token':sys.argv[1],'slack_signing_secret':sys.argv[2],'teams_webhook_secret':sys.argv[3]}))" "$ZOOM_WH" "$SLACK_WH" "$TEAMS_WH")
put_secret "webhook-secrets" "$WEBHOOK_JSON"

echo "=== Done ==="
