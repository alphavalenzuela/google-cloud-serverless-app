#!/usr/bin/env bash
# ==============================================================================
# Deployment Script for Serverless GCP Document Processing Pipeline
# ==============================================================================
set -euo pipefail

# 1. Configuration check
if [ -z "${PROJECT_ID:-}" ]; then
  echo "Error: PROJECT_ID environment variable is not set."
  echo "Usage: PROJECT_ID=my-gcp-project REGION=us-central1 BUCKET_NAME=my-unique-bucket ./scripts/deploy.sh"
  exit 1
fi

REGION="${REGION:-us-central1}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-raw-documents}"
REPO_NAME="doc-pipeline"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/doc-processor:latest"

echo "=========================================================="
echo " Deploying Document Processing Pipeline"
echo " Project: ${PROJECT_ID}"
echo " Region:  ${REGION}"
echo " Bucket:  ${BUCKET_NAME}"
echo " Image:   ${IMAGE_NAME}"
echo "=========================================================="

# 2. Enable Required GCP APIs
echo "[+] Enabling required GCP service APIs..."
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  run.googleapis.com \
  pubsub.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="${PROJECT_ID}"

# 3. Ensure Artifact Registry repository exists
echo "[+] Creating or verifying Artifact Registry repository '${REPO_NAME}'..."
gcloud artifacts repositories create "${REPO_NAME}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="Docker repository for document processing pipeline" \
  --project="${PROJECT_ID}" 2>/dev/null || true

# 4. Build & Push container image
echo "[+] Building and pushing container image with Cloud Build..."
gcloud builds submit --tag "${IMAGE_NAME}" --project="${PROJECT_ID}" .

# 5. Terraform Provisioning
echo "[+] Running Terraform to provision infrastructure..."
cd terraform

terraform init

terraform apply -auto-approve \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="bucket_name=${BUCKET_NAME}" \
  -var="container_image=${IMAGE_NAME}"

echo "=========================================================="
echo "[+] Deployment completed successfully!"
echo "=========================================================="
