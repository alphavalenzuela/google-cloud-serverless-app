"""Flask Web Application for Google Cloud BigQuery Document Analytics."""

import os
from typing import Dict, List, Tuple
from flask import Flask, render_template, request

app = Flask(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "serverless-application-511208")
DATASET_ID = os.getenv("BIGQUERY_DATASET_ID", "doc_analytics")
TABLE_ID = os.getenv("BIGQUERY_TABLE_ID", "processed_documents")


def get_mock_documents() -> List[Dict]:
    """Fallback sample data when BigQuery is unreachable locally."""
    return [
        {
            "filename": "invoices/vendor_invoice_109.pdf",
            "upload_date": "2026-10-10 08:58:27 UTC",
            "tags": ["finance", "invoice", "billing"],
            "word_count": 482,
            "status": "SUCCESS",
            "processing_time_ms": 240,
        },
        {
            "filename": "contracts/master_services_agreement.pdf",
            "upload_date": "2026-10-10 09:12:05 UTC",
            "tags": ["legal", "contract", "agreement"],
            "word_count": 3120,
            "status": "SUCCESS",
            "processing_time_ms": 890,
        },
        {
            "filename": "receipts/office_supplies_receipt.pdf",
            "upload_date": "2026-10-10 09:30:11 UTC",
            "tags": ["finance", "receipt", "expense"],
            "word_count": 145,
            "status": "SUCCESS",
            "processing_time_ms": 190,
        },
        {
            "filename": "hr/senior_cloud_architect_resume.pdf",
            "upload_date": "2026-10-10 09:45:00 UTC",
            "tags": ["hr", "resume", "recruitment"],
            "word_count": 920,
            "status": "SUCCESS",
            "processing_time_ms": 410,
        },
        {
            "filename": "archives/backup_logs.zip",
            "upload_date": "2026-10-10 09:50:30 UTC",
            "tags": ["skipped", "unsupported-extension"],
            "word_count": 0,
            "status": "SKIPPED",
            "processing_time_ms": 15,
        },
    ]


def query_bigquery() -> Tuple[List[Dict], bool, str]:
    """Queries BigQuery dataset or falls back to mock data."""
    table_ref = f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
    query = f"""
        SELECT
            filename,
            created_at AS upload_date,
            tags,
            word_count,
            status,
            processing_time_ms
        FROM {table_ref}
        ORDER BY processed_at DESC
        LIMIT 500
    """
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=PROJECT_ID)
        results = client.query(query).result()

        docs = []
        for row in results:
            raw_tags = row.get("tags")
            if isinstance(raw_tags, list):
                tags_list = raw_tags
            elif isinstance(raw_tags, str):
                tags_list = [t.strip() for t in raw_tags.strip("[]").replace("'", "").replace('"', "").split(",") if t.strip()]
            else:
                tags_list = []

            upload_dt = row.get("upload_date")
            upload_date_str = (
                upload_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                if hasattr(upload_dt, "strftime")
                else str(upload_dt or "")
            )

            docs.append({
                "filename": row.get("filename"),
                "upload_date": upload_date_str,
                "tags": tags_list,
                "word_count": int(row.get("word_count") or 0),
                "status": row.get("status") or "UNKNOWN",
                "processing_time_ms": int(row.get("processing_time_ms") or 0),
            })
        return docs, True, f"Connected to live BigQuery table: {table_ref}"
    except Exception as e:
        return get_mock_documents(), False, f"Notice: Could not connect to BigQuery ({e}). Displaying mock preview."


@app.route("/")
def index():
    selected_tag = request.args.get("tag", "").strip()
    docs, is_live, status_msg = query_bigquery()

    # Collect all unique tags for filter dropdown
    all_tags = set()
    for doc in docs:
        for t in doc.get("tags", []):
            all_tags.add(t)

    # Filter documents if tag is specified
    if selected_tag:
        docs = [d for d in docs if selected_tag in d.get("tags", [])]

    total_words = sum(d["word_count"] for d in docs)
    avg_latency = int(sum(d["processing_time_ms"] for d in docs) / len(docs)) if docs else 0

    return render_template(
        "index.html",
        documents=docs,
        all_tags=sorted(list(all_tags)),
        selected_tag=selected_tag,
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID,
        table_id=TABLE_ID,
        is_live=is_live,
        status_msg=status_msg,
        total_words=f"{total_words:,}",
        avg_latency=avg_latency,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8501))
    app.run(host="0.0.0.0", port=port, debug=True)
