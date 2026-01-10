#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# ContractIQ — GCP Cloud Run deployment (Cloud Shell friendly)
# - Uploads SQLite DB to GCS
# - Stores API keys in Secret Manager
# - Builds container in Cloud Build (WAITs for success)
# - Deploys to Cloud Run with env vars + secrets
# -------------------------------------------------------------------

# ----------------------------
# USER CONFIG (edit or export)
# ----------------------------
PROJECT_ID="${PROJECT_ID:-gen-lang-client-0168615668}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-contractiq}"
AR_REPO="${AR_REPO:-contractiq}"
IMAGE_NAME="${IMAGE_NAME:-contractiq}"
LOCAL_EMBEDDING_MODEL="/app/models/all-MiniLM-L6-v2"
# Local path to your populated sqlite db (relative to repo root in Cloud Shell)
DB_LOCAL_PATH="${DB_LOCAL_PATH:-data/contractrag.db}"

# Where to store the DB in GCS
BUCKET="${BUCKET:-${PROJECT_ID}-contractiq-data}"
DB_OBJECT="${DB_OBJECT:-db/contractrag.db}"

# Runtime path inside Cloud Run
SQLITE_PATH="${SQLITE_PATH:-/tmp/contractrag.db}"

# Optional: explicitly set account if gcloud config is weird
GCLOUD_ACCOUNT="${GCLOUD_ACCOUNT:-}"

# ----------------------------
# REQUIRED SECRETS (do NOT hardcode)
# Provide as env vars before running:
#   export PINECONE_API_KEY="..."
#   export GEMINI_API_KEY="..."
# ----------------------------
: "${PINECONE_API_KEY:?Must export PINECONE_API_KEY before running}"
: "${GEMINI_API_KEY:?Must export GEMINI_API_KEY before running}"

# ----------------------------
# Helpers
# ----------------------------
say() { printf "\n\033[1m%s\033[0m\n" "$*"; }

ensure_gcloud_healthy() {
  # gcloud has been crashing for you; this makes the script fail fast with a clear message.
  if ! gcloud version >/dev/null 2>&1; then
    echo "ERROR: gcloud is not healthy in this session (gcloud version failed)."
    echo "Fix: in Cloud Shell, restart the session OR reset config:"
    echo "  mv ~/.config/gcloud ~/.config/gcloud.bak.\$(date +%s)"
    echo "  gcloud auth login"
    exit 1
  fi
}

create_or_update_secret () {
  local secret_name="$1"
  local secret_value="$2"
  local service_account_email="$3"

  if ! gcloud secrets describe "${secret_name}" >/dev/null 2>&1; then
    say "Creating secret: ${secret_name}"
    printf "%s" "${secret_value}" | gcloud secrets create "${secret_name}" --data-file=- >/dev/null
  else
    say "Updating secret (new version): ${secret_name}"
    printf "%s" "${secret_value}" | gcloud secrets versions add "${secret_name}" --data-file=- >/dev/null
  fi

  say "Granting Secret Manager access to ${service_account_email} for ${secret_name}"
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --member="serviceAccount:${service_account_email}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
}

# ----------------------------
# Start
# ----------------------------
say "ContractIQ deploy starting..."

echo "Using:"
echo "  PROJECT_ID=${PROJECT_ID}"
echo "  REGION=${REGION}"
echo "  SERVICE_NAME=${SERVICE_NAME}"
echo "  AR_REPO=${AR_REPO}"
echo "  IMAGE_NAME=${IMAGE_NAME}"
echo "  BUCKET=${BUCKET}"
echo "  DB_LOCAL_PATH=${DB_LOCAL_PATH}"
echo "  DB_OBJECT=${DB_OBJECT}"
echo "  SQLITE_PATH=${SQLITE_PATH}"
echo

ensure_gcloud_healthy

# If user provided an account, pin it (helps if core.account is unset)
if [[ -n "${GCLOUD_ACCOUNT}" ]]; then
  say "Setting active gcloud account: ${GCLOUD_ACCOUNT}"
  gcloud config set account "${GCLOUD_ACCOUNT}" >/dev/null || true
fi

# Set project/region
say "Setting gcloud project + region..."
gcloud config set project "${PROJECT_ID}" >/dev/null
gcloud config set run/region "${REGION}" >/dev/null

say "Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
DEFAULT_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "Project number: ${PROJECT_NUMBER}"
echo "Default service account: ${DEFAULT_SA}"
echo

# ----------------------------
# Create bucket (if needed) + upload DB
# ----------------------------
say "Ensuring GCS bucket exists: gs://${BUCKET}"
if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --location="${REGION}"
fi

say "Checking local DB exists: ${DB_LOCAL_PATH}"
if [[ ! -f "${DB_LOCAL_PATH}" ]]; then
  echo "ERROR: DB file not found at ${DB_LOCAL_PATH}"
  echo "If you're in Cloud Shell, upload your contractrag.db into the repo at that path."
  exit 1
fi

say "Uploading DB to GCS: gs://${BUCKET}/${DB_OBJECT}"
gcloud storage cp "${DB_LOCAL_PATH}" "gs://${BUCKET}/${DB_OBJECT}"

say "Granting storage.objectViewer to ${DEFAULT_SA} on bucket..."
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${DEFAULT_SA}" \
  --role="roles/storage.objectViewer" >/dev/null

# ----------------------------
# Secrets (create/update) + grant Cloud Run SA access
# ----------------------------
create_or_update_secret "PINECONE_API_KEY" "${PINECONE_API_KEY}" "${DEFAULT_SA}"
create_or_update_secret "GEMINI_API_KEY" "${GEMINI_API_KEY}" "${DEFAULT_SA}"

# ----------------------------
# Artifact Registry repo + build (WAIT for build)
# ----------------------------
say "Ensuring Artifact Registry repo exists: ${AR_REPO}"
if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" >/dev/null
fi

say "Configuring Docker auth for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" >/dev/null

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest"
say "Building and pushing image with Cloud Build (wait for success): ${IMAGE}"

# IMPORTANT CHANGE:
# Capture build id and wait, so we never deploy while build is QUEUED/WORKING.
BUILD_ID="$(gcloud builds submit --tag "${IMAGE}" --format='value(id)')"
echo "Build ID: ${BUILD_ID}"
say "Waiting for Cloud Build to finish..."
gcloud builds wait "${BUILD_ID}"
say "✅ Cloud Build finished."

# ----------------------------
# Deploy Cloud Run
# ----------------------------
say "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --allow-unauthenticated \
  --region "${REGION}" \
  --set-env-vars "SQLITE_PATH=${SQLITE_PATH},GCS_DB_BUCKET=${BUCKET},GCS_DB_OBJECT=${DB_OBJECT}" \
  --update-secrets "PINECONE_API_KEY=PINECONE_API_KEY:latest" \
  --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300

URL="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)')"

echo
say "✅ Deployed!"
echo "URL: ${URL}"
echo "Health: ${URL}/healthz"
