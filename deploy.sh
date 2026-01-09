#!/usr/bin/env bash
set -euo pipefail

# ----------------------------
# USER CONFIG (edit these)
# ----------------------------
PROJECT_ID="${PROJECT_ID:-gen-lang-client-0168615668}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-contractiq}"
AR_REPO="${AR_REPO:-contractiq}"
IMAGE_NAME="${IMAGE_NAME:-contractiq}"

# Local path to your populated sqlite db (relative to repo root in Cloud Shell)
DB_LOCAL_PATH="${DB_LOCAL_PATH:-data/contractrag.db}"

# Where to store the DB in GCS
BUCKET="${BUCKET:-${PROJECT_ID}-contractiq-data}"
DB_OBJECT="${DB_OBJECT:-db/contractrag.db}"

# Runtime path inside Cloud Run (downloaded at startup)
SQLITE_PATH="${SQLITE_PATH:-/tmp/contractrag.db}"

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
echo "Using:"
echo "  PROJECT_ID=${PROJECT_ID}"
echo "  REGION=${REGION}"
echo "  SERVICE_NAME=${SERVICE_NAME}"
echo "  AR_REPO=${AR_REPO}"
echo "  BUCKET=${BUCKET}"
echo "  DB_LOCAL_PATH=${DB_LOCAL_PATH}"
echo

gcloud config set project "${PROJECT_ID}" >/dev/null
gcloud config set run/region "${REGION}" >/dev/null

echo "Enabling required APIs..."
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
echo "Ensuring GCS bucket exists: gs://${BUCKET}"
if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --location="${REGION}"
fi

echo "Checking local DB exists: ${DB_LOCAL_PATH}"
if [ ! -f "${DB_LOCAL_PATH}" ]; then
  echo "ERROR: DB file not found at ${DB_LOCAL_PATH}"
  echo "If you're in Cloud Shell, upload your contractrag.db into the repo at that path."
  exit 1
fi

echo "Uploading DB to GCS: gs://${BUCKET}/${DB_OBJECT}"
gcloud storage cp "${DB_LOCAL_PATH}" "gs://${BUCKET}/${DB_OBJECT}"

# Allow Cloud Run runtime identity to read objects in the bucket
echo "Granting storage.objectViewer to ${DEFAULT_SA} on bucket..."
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${DEFAULT_SA}" \
  --role="roles/storage.objectViewer" >/dev/null

# ----------------------------
# Secrets (create if missing; then add a new version)
# ----------------------------
create_or_update_secret () {
  local secret_name="$1"
  local secret_value="$2"

  if ! gcloud secrets describe "${secret_name}" >/dev/null 2>&1; then
    echo "Creating secret: ${secret_name}"
    printf "%s" "${secret_value}" | gcloud secrets create "${secret_name}" --data-file=- >/dev/null
  else
    echo "Updating secret (new version): ${secret_name}"
    printf "%s" "${secret_value}" | gcloud secrets versions add "${secret_name}" --data-file=- >/dev/null
  fi

  echo "Granting Secret Manager access to ${DEFAULT_SA} for ${secret_name}"
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --member="serviceAccount:${DEFAULT_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
}

create_or_update_secret "PINECONE_API_KEY" "${PINECONE_API_KEY}"
create_or_update_secret "GEMINI_API_KEY" "${GEMINI_API_KEY}"

# ----------------------------
# Artifact Registry repo + build
# ----------------------------
echo "Ensuring Artifact Registry repo exists: ${AR_REPO}"
if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" >/dev/null
fi

echo "Configuring Docker auth for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" >/dev/null

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest"
echo "Building and pushing image with Cloud Build: ${IMAGE}"
gcloud builds submit --tag "${IMAGE}"

# ----------------------------
# Deploy Cloud Run
# ----------------------------
echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --allow-unauthenticated \
  --region "${REGION}" \
  --set-env-vars "SQLITE_PATH=${SQLITE_PATH},GCS_DB_BUCKET=${BUCKET},GCS_DB_OBJECT=${DB_OBJECT}" \
  --update-secrets "PINECONE_API_KEY=PINECONE_API_KEY:latest" \
  --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300

URL="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)')"
echo
echo "✅ Deployed!"
echo "URL: ${URL}"
echo "Health: ${URL}/healthz"
