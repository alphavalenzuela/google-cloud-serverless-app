# Serverless Event-Driven Document Processing Pipeline on Google Cloud

A production-grade, event-driven serverless pipeline on Google Cloud that automatically ingests files uploaded to Cloud Storage, extracts text and semantic metadata via OCR, and streams structured records idempotently into Google BigQuery.

---

## 🏗️ Architecture

```
                                  +---------------------------------------+
                                  |         Google Cloud Platform         |
                                  +---------------------------------------+
 [User / System]
        |
        v
+------------------+     OBJECT_FINALIZE     +--------------------+
|   Cloud Storage  | ----------------------> |   Pub/Sub Topic    |
| (raw-documents)  |                         | (doc-upload-events)|
+------------------+                         +--------------------+
                                                       |
                                            Push with OIDC Bearer Token
                                            (Exponential Backoff, Max 5 Retries)
                                                       |
                             +-------------------------+-------------------------+
                             |                                                   |
                             v (Success path)                                    v (Poison Pill / DLQ)
                 +-----------------------+                          +--------------------------+
                 |    Cloud Run Service  |                          |     Dead Letter Topic    |
                 |    (doc-processor)    |                          |     (doc-upload-dlq)     |
                 +-----------------------+                          +--------------------------+
                   |         |         |                                         |
            Stream |     OCR |  Insert |                                         v
            Bytes  |  Engine |    Rows |                          +--------------------------+
                   v         v         v                          |  Operator Audit / Alerts |
             +-----+   +-----+   +-------------+                  +--------------------------+
             | GCS |   | OCR |   |  BigQuery   |
             |     |   |     |   | (Partitioned|
             +-----+   +-----+   | & Clustered)|
                                 +-------------+
```

### Core Architecture Components
1. **Ingestion Layer (Cloud Storage)**: Users upload documents (`.pdf`, `.png`, `.jpg`, `.txt`, `.tiff`) to a Cloud Storage bucket. GCS emits `OBJECT_FINALIZE` event notifications.
2. **Trigger Layer (Cloud Pub/Sub)**: An event notification topic pushes messages to Cloud Run via an authenticated HTTPS push subscription signed with an OIDC service account token.
3. **Resilience & Poison Pills (Dead Letter Queue)**: If a corrupt or poison-pill message fails processing 5 consecutive times, Pub/Sub routes it to `doc-upload-dlq` to prevent infinite compute billing loops.
4. **Compute Layer (Cloud Run v2)**: Containerized FastAPI Python application. Gracefully categorizes unsupported extensions, downloads blob bytes, executes simulated OCR (or Cloud Vision API), and extracts word counts and domain tags.
5. **Storage Layer (Google BigQuery)**: Streams metadata into day-partitioned (`processed_at`) and clustered (`status`, `bucket`) BigQuery tables using composite idempotency keys (`{bucket}/{name}#{generation}`).

---

## 📁 Repository Structure

```
├── src/
│   ├── app.py                 # FastAPI application with POST /process-event & GET /health
│   ├── config.py              # Application settings (Pydantic Settings)
│   ├── models.py              # Pydantic schemas for Pub/Sub events & BigQuery records
│   ├── services/
│   │   ├── gcs_service.py     # Cloud Storage streaming client with mock fallback
│   │   ├── ocr_engine.py      # Extensible OCR layer (Simulated & Vision API adapters)
│   │   └── bq_service.py      # BigQuery idempotent insertion & schema manager
│   └── utils/
│       └── logger.py          # Structured JSON logging (GCP Cloud Logging compatible)
├── dashboard/
│   ├── app.py                 # Streamlit web dashboard with live BigQuery query & tag filter
│   ├── flask_app.py           # Alternative lightweight Flask web app
│   └── templates/
│       └── index.html         # Responsive Bootstrap UI for Flask app
├── terraform/
│   ├── main.tf                # Provider setup & project data sources
│   ├── variables.tf           # Configurable infrastructure variables
│   ├── storage.tf             # GCS bucket & OBJECT_FINALIZE notification
│   ├── pubsub.tf              # Primary topic, push subscription, and Dead Letter Queue
│   ├── cloud_run.tf           # Cloud Run v2 service definition & health probes
│   ├── bigquery.tf            # Dataset & partitioned table definition
│   ├── iam.tf                 # Least-privilege IAM bindings & service accounts
│   ├── outputs.tf             # Deployed resource identifiers and URLs
│   └── terraform.tfvars.example
├── tests/
│   ├── conftest.py            # Pytest fixtures & sample event payloads
│   ├── test_app.py            # FastAPI integration tests (push events, auth, skipping)
│   ├── test_models.py         # Schema validation & BigQuery row serialization
│   ├── test_ocr.py            # Simulated OCR engine keyword classification tests
│   ├── test_bq.py             # BigQuery deduplication & service tests
│   └── test_gcs.py            # GCS service mock download tests
├── scripts/
│   ├── test_pipeline.sh       # Live end-to-end verification script against real GCP resources
│   ├── simulate_event.py      # Local CLI to test the pipeline with synthetic events
│   └── deploy.sh              # Cloud Build & Terraform deployment automation script
├── Dockerfile                 # Multi-stage non-root Python 3.11 container
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development & test dependencies
└── README.md
```

---

## 🚀 Quickstart: Local Development & Testing

The project includes an **offline mock mode** so you can develop, run tests, and simulate document ingestion locally without active GCP credentials.

### 1. Prerequisites
- Python 3.11+
- Virtual environment tool (`venv`)

### 2. Setup Virtual Environment
```bash
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

### 3. Run Test Suite
Execute the unit and integration tests:
```bash
pytest tests/ -v
```

Run test coverage report:
```bash
coverage run -m pytest tests/
coverage report -m
```

### 4. Run Local Server & Simulate Ingestion
Start the FastAPI server locally:
```bash
uvicorn src.app:app --host 127.0.0.1 --port 8080 --reload
```

In a separate terminal, simulate document upload events:
```bash
# 1. Simulate an invoice upload (auto-detects 'finance', 'invoice' tags)
python scripts/simulate_event.py --file "invoices/2026/vendor_invoice_109.pdf"

# 2. Simulate a legal contract upload (auto-detects 'legal', 'contract' tags)
python scripts/simulate_event.py --file "contracts/2026/master_service_agreement.pdf"

# 3. Simulate an unsupported file (gracefully acknowledged and skipped)
python scripts/simulate_event.py --file "archive/backup_dump.zip" --content-type "application/zip"
```

### 5. Launch the Web Dashboard (Streamlit / Flask)

You can view and filter all processed documents stored in BigQuery in real time.

**Option A: Streamlit (Recommended — Interactive Data Dashboard)**
```bash
streamlit run dashboard/app.py
```
*(Opens automatically at `http://localhost:8501` with KPI metrics, tag multi-select, and full OCR text inspector)*.

**Option B: Flask (Lightweight Bootstrap Web App)**
```bash
python dashboard/flask_app.py
```
*(Opens at `http://localhost:8501`)*.

---

## 🔒 Security & IAM Least-Privilege Matrix

| Principal | Role | Resource | Purpose |
| :--- | :--- | :--- | :--- |
| **GCS Service Agent** | `roles/pubsub.publisher` | `doc-upload-events` Topic | Publish notifications on document upload |
| **Pub/Sub Invoker SA** (`sa-pubsub-invoker`) | `roles/run.invoker` | `doc-processor` Service | Invokes Cloud Run endpoint with OIDC bearer token |
| **Cloud Run SA** (`sa-doc-processor`) | `roles/storage.objectViewer` | GCS Bucket (`raw-documents`) | Reads document streams |
| **Cloud Run SA** (`sa-doc-processor`) | `roles/bigquery.dataEditor` | BigQuery Dataset | Streams metadata records into table |
| **Cloud Run SA** (`sa-doc-processor`) | `roles/logging.logWriter` | GCP Project | Emits structured JSON logs |
| **Pub/Sub Service Agent** | `roles/pubsub.publisher` | `doc-upload-dlq` Topic | Routes dead-letter messages after 5 retries |

---

## ☁️ Deployment to Google Cloud

### Method A: Automated Deployment Script
Ensure `gcloud` is logged in and configured with your project:
```bash
chmod +x scripts/deploy.sh
PROJECT_ID="your-gcp-project-id" REGION="us-central1" BUCKET_NAME="my-unique-doc-bucket-2026" ./scripts/deploy.sh
```

### Method B: Manual Step-by-Step Deployment

#### 1. Enable Required GCP APIs
```bash
gcloud services enable \
  run.googleapis.com \
  pubsub.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  cloudbuild.googleapis.com \
  --project="your-gcp-project-id"
```

#### 2. Build and Push Container Image
```bash
gcloud builds submit --tag "gcr.io/your-gcp-project-id/doc-processor:latest" .
```

#### 3. Provision Infrastructure with Terraform
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID, bucket name, and container image

terraform init
terraform plan
terraform apply
```

#### 4. Verify End-to-End Ingestion
Upload a sample file directly to your newly created Cloud Storage bucket:
```bash
gsutil cp sample.pdf gs://your-unique-doc-bucket-2026/invoices/2026/sample.pdf
```
Query your BigQuery table to inspect the extracted metadata:
```sql
SELECT
  document_id,
  filename,
  word_count,
  tags,
  text_snippet,
  status,
  processed_at
FROM
  `your-gcp-project-id.doc_analytics.processed_documents`
ORDER BY
  processed_at DESC
LIMIT 10;
```
