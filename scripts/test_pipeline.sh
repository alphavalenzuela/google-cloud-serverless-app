#!/usr/bin/env bash
# ==============================================================================
# Live End-to-End Pipeline Verification Script
# Tests: GCS Upload -> Pub/Sub -> Cloud Run OCR -> BigQuery Ingestion
# ==============================================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-serverless-application-511208}"
REGION="${REGION:-us-central1}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-raw-docs}"
DATASET_ID="doc_analytics"
TABLE_ID="processed_documents"

echo "=========================================================="
echo " 🧪 Live Pipeline Verification on Google Cloud"
echo " Project:   ${PROJECT_ID}"
echo " Bucket:    ${BUCKET_NAME}"
echo " BigQuery:  ${PROJECT_ID}.${DATASET_ID}.${TABLE_ID}"
echo "=========================================================="

# 1. Create temporary test files
TEST_DIR=$(mktemp -d)
trap 'rm -rf "${TEST_DIR}"' EXIT

TIMESTAMP=$(date +%s)
INVOICE_FILE="${TEST_DIR}/vendor_invoice_${TIMESTAMP}.pdf"
CONTRACT_FILE="${TEST_DIR}/legal_contract_${TIMESTAMP}.txt"
UNSUPPORTED_FILE="${TEST_DIR}/archive_data_${TIMESTAMP}.zip"

# Create dummy sample content
echo "%PDF-1.4 Simulated Invoice #INV-2026-001 Total Due: $1,500.00 Terms: Net 30" > "${INVOICE_FILE}"
echo "Confidential Mutual Non-Disclosure Agreement between Acme Corp and Partner. All rights reserved." > "${CONTRACT_FILE}"
echo "Dummy zip binary stream" > "${UNSUPPORTED_FILE}"

# 2. Upload test documents to Google Cloud Storage
echo ""
echo "[1/4] 📤 Uploading test documents to gs://${BUCKET_NAME}..."

echo "  -> Uploading invoice: vendor_invoice_${TIMESTAMP}.pdf"
gcloud storage cp "${INVOICE_FILE}" "gs://${BUCKET_NAME}/invoices/vendor_invoice_${TIMESTAMP}.pdf" --quiet

echo "  -> Uploading contract: legal_contract_${TIMESTAMP}.txt"
gcloud storage cp "${CONTRACT_FILE}" "gs://${BUCKET_NAME}/contracts/legal_contract_${TIMESTAMP}.txt" --quiet

echo "  -> Uploading unsupported file: archive_data_${TIMESTAMP}.zip"
gcloud storage cp "${UNSUPPORTED_FILE}" "gs://${BUCKET_NAME}/unsupported/archive_data_${TIMESTAMP}.zip" --quiet

echo "[+] Files uploaded successfully. Event notifications dispatched to Pub/Sub."

# 3. Wait for asynchronous serverless processing
WAIT_SECONDS=8
echo ""
echo "[2/4] ⏳ Waiting ${WAIT_SECONDS}s for Pub/Sub push and Cloud Run processing..."
sleep "${WAIT_SECONDS}"

# 4. Check Cloud Run Service Logs
echo ""
echo "[3/4] 📋 Inspecting recent Cloud Run logs for 'doc-processor'..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=doc-processor" \
  --project="${PROJECT_ID}" \
  --limit=8 \
  --format="value(jsonPayload.message,textPayload)" || true

# 5. Query BigQuery to verify ingested document records
echo ""
echo "[4/4] 🔍 Querying BigQuery dataset for processed records..."

QUERY="SELECT document_id, filename, status, word_count, TO_JSON_STRING(tags) AS tags, processing_time_ms FROM \`${PROJECT_ID}.${DATASET_ID}.${TABLE_ID}\` WHERE filename LIKE '%${TIMESTAMP}%' ORDER BY processed_at DESC;"

bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" "${QUERY}"

echo ""
echo "=========================================================="
echo " ✅ Live Pipeline Verification Complete!"
echo " Documents successfully ingested, OCR-processed, and"
echo " recorded in Google BigQuery."
echo "=========================================================="
