"""Streamlit Web Application for Google Cloud BigQuery Document Analytics."""

import os
from datetime import datetime, timezone
from typing import List, Tuple
import pandas as pd
import streamlit as st

# Configure Streamlit page
st.set_page_config(
    page_title="Document Pipeline Analytics",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Configuration defaults
DEFAULT_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "serverless-application-511208")
DEFAULT_DATASET_ID = os.getenv("BIGQUERY_DATASET_ID", "doc_analytics")
DEFAULT_TABLE_ID = os.getenv("BIGQUERY_TABLE_ID", "processed_documents")


def get_mock_data() -> pd.DataFrame:
    """Returns sample mock data for local testing when BigQuery credentials are not available."""
    data = [
        {
            "document_id": "serverless-application-511208-raw-documents/invoices/vendor_invoice_109.pdf#1",
            "filename": "invoices/vendor_invoice_109.pdf",
            "upload_date": "2026-10-10 08:58:27 UTC",
            "tags": ["finance", "invoice", "billing"],
            "word_count": 482,
            "status": "SUCCESS",
            "processing_time_ms": 240,
            "text_snippet": "INVOICE #INV-2026-109\nDate: 2026-10-10\nVendor: Global Tech Logistics\nTotal: $14,250.00\nPayment Terms: Net 30 days.",
            "size_bytes": 34200,
        },
        {
            "document_id": "serverless-application-511208-raw-documents/contracts/master_services_agreement.pdf#1",
            "filename": "contracts/master_services_agreement.pdf",
            "upload_date": "2026-10-10 09:12:05 UTC",
            "tags": ["legal", "contract", "agreement"],
            "word_count": 3120,
            "status": "SUCCESS",
            "processing_time_ms": 890,
            "text_snippet": "MASTER SERVICES AGREEMENT\nThis Agreement is entered into by and between Acme Corp and Client Inc. Confidentiality, liability limitations, and governing law.",
            "size_bytes": 128400,
        },
        {
            "document_id": "serverless-application-511208-raw-documents/receipts/office_supplies_receipt.pdf#1",
            "filename": "receipts/office_supplies_receipt.pdf",
            "upload_date": "2026-10-10 09:30:11 UTC",
            "tags": ["finance", "receipt", "expense"],
            "word_count": 145,
            "status": "SUCCESS",
            "processing_time_ms": 190,
            "text_snippet": "OFFICE DEPOT RECEIPT\nDate: 2026-10-09\nItems: Printer paper, toner cartridges, pens.\nSubtotal: $184.50\nTax: $14.76\nTotal Paid: $199.26",
            "size_bytes": 18500,
        },
        {
            "document_id": "serverless-application-511208-raw-documents/hr/senior_cloud_architect_resume.pdf#1",
            "filename": "hr/senior_cloud_architect_resume.pdf",
            "upload_date": "2026-10-10 09:45:00 UTC",
            "tags": ["hr", "resume", "recruitment"],
            "word_count": 920,
            "status": "SUCCESS",
            "processing_time_ms": 410,
            "text_snippet": "Jane Doe - Senior Cloud Solutions Architect\nExperience: 8+ years designing event-driven serverless architectures on GCP, Terraform, Python, BigQuery.",
            "size_bytes": 54200,
        },
        {
            "document_id": "serverless-application-511208-raw-documents/archives/backup_logs.zip#1",
            "filename": "archives/backup_logs.zip",
            "upload_date": "2026-10-10 09:50:30 UTC",
            "tags": ["skipped", "unsupported-extension"],
            "word_count": 0,
            "status": "SKIPPED",
            "processing_time_ms": 15,
            "text_snippet": "Skipped processing: Unsupported extension .zip",
            "size_bytes": 1048576,
        },
    ]
    return pd.DataFrame(data)


@st.cache_data(ttl=30, show_spinner=False)
def fetch_bigquery_documents(project_id: str, dataset_id: str, table_id: str) -> Tuple[pd.DataFrame, bool, str]:
    """Queries BigQuery table for processed document records.

    Returns: (DataFrame, is_live_connection, error_or_info_message)
    """
    table_ref = f"`{project_id}.{dataset_id}.{table_id}`"
    query = f"""
        SELECT
            document_id,
            filename,
            bucket,
            content_type,
            size_bytes,
            created_at AS upload_date,
            processed_at,
            word_count,
            tags,
            text_snippet,
            ocr_engine,
            processing_time_ms,
            status
        FROM {table_ref}
        ORDER BY processed_at DESC
        LIMIT 500
    """

    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=project_id)
        query_job = client.query(query)
        results = query_job.result()

        rows = []
        for row in results:
            # Format tags properly into list of strings
            raw_tags = row.get("tags")
            if isinstance(raw_tags, list):
                tags_list = raw_tags
            elif isinstance(raw_tags, str):
                tags_list = [t.strip() for t in raw_tags.strip("[]").replace("'", "").replace('"', "").split(",") if t.strip()]
            else:
                tags_list = []

            # Format upload_date
            upload_dt = row.get("upload_date")
            upload_date_str = (
                upload_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                if hasattr(upload_dt, "strftime")
                else str(upload_dt or "")
            )

            rows.append({
                "document_id": row.get("document_id"),
                "filename": row.get("filename"),
                "upload_date": upload_date_str,
                "tags": tags_list,
                "word_count": int(row.get("word_count") or 0),
                "status": row.get("status") or "UNKNOWN",
                "processing_time_ms": int(row.get("processing_time_ms") or 0),
                "text_snippet": row.get("text_snippet") or "",
                "size_bytes": int(row.get("size_bytes") or 0),
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df, True, f"Connected to BigQuery ({table_ref}), but table is currently empty."
        return df, True, f"Successfully loaded {len(df)} live records from BigQuery table {table_ref}."

    except Exception as e:
        # Fall back gracefully to mock data with a warning banner
        df_mock = get_mock_data()
        msg = f"Notice: Could not connect to live BigQuery table ({e}). Showing demo data preview."
        return df_mock, False, msg


# -------------------------------------------------------------
# Sidebar Controls & Settings
# -------------------------------------------------------------
st.sidebar.title("⚙️ Pipeline Settings")

project_id = st.sidebar.text_input("GCP Project ID", value=DEFAULT_PROJECT_ID)
dataset_id = st.sidebar.text_input("BigQuery Dataset", value=DEFAULT_DATASET_ID)
table_id = st.sidebar.text_input("BigQuery Table", value=DEFAULT_TABLE_ID)

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# Fetch Data
df_raw, is_live, status_msg = fetch_bigquery_documents(project_id, dataset_id, table_id)

# Connection Status Badge
if is_live:
    st.sidebar.success(status_msg)
else:
    st.sidebar.warning(status_msg)

# -------------------------------------------------------------
# Filters
# -------------------------------------------------------------
st.sidebar.subheader("🔍 Filters")

# Collect all unique tags across records
all_tags = set()
if not df_raw.empty:
    for tags_list in df_raw["tags"]:
        if isinstance(tags_list, list):
            for t in tags_list:
                all_tags.add(t)
sorted_tags = sorted(list(all_tags))

# Tag multi-select filter
selected_tags = st.sidebar.multiselect(
    "Filter by Tag:",
    options=sorted_tags,
    default=[],
    help="Select one or more tags to filter documents. Leave empty to show all tags.",
)

# Status filter
status_options = ["ALL"] + sorted(list(df_raw["status"].unique())) if not df_raw.empty else ["ALL"]
selected_status = st.sidebar.selectbox("Filter by Status:", options=status_options, index=0)

# Filename search
search_term = st.sidebar.text_input("Search filename:", value="").strip().lower()

# Apply Filters
df_filtered = df_raw.copy()

if selected_tags:
    df_filtered = df_filtered[
        df_filtered["tags"].apply(
            lambda tags: any(tag in tags for tag in selected_tags) if isinstance(tags, list) else False
        )
    ]

if selected_status != "ALL":
    df_filtered = df_filtered[df_filtered["status"] == selected_status]

if search_term:
    df_filtered = df_filtered[
        df_filtered["filename"].str.lower().str.contains(search_term, na=False)
    ]

# -------------------------------------------------------------
# Main Dashboard UI
# -------------------------------------------------------------
st.title("📄 Serverless Document Processing Dashboard")
st.caption(f"Google Cloud Platform · Project: `{project_id}` · Dataset: `{dataset_id}.{table_id}`")

# KPI Summary Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Documents", len(df_filtered), delta=f"{len(df_filtered) - len(df_raw)}" if len(df_filtered) != len(df_raw) else None)
with col2:
    total_words = int(df_filtered["word_count"].sum()) if not df_filtered.empty else 0
    st.metric("Total Words Extracted", f"{total_words:,}")
with col3:
    st.metric("Unique Tags Found", len(sorted_tags))
with col4:
    avg_latency = int(df_filtered["processing_time_ms"].mean()) if not df_filtered.empty else 0
    st.metric("Avg Latency", f"{avg_latency} ms")

st.markdown("---")

# -------------------------------------------------------------
# Processed Documents Table
# -------------------------------------------------------------
st.subheader("📋 Processed Documents")

if df_filtered.empty:
    st.info("No documents match the selected filters.")
else:
    # Prepare display DataFrame
    display_df = df_filtered.copy()
    display_df["tags"] = display_df["tags"].apply(lambda t: ", ".join(t) if isinstance(t, list) else str(t))

    st.dataframe(
        display_df[["filename", "upload_date", "tags", "word_count", "status", "processing_time_ms"]],
        column_config={
            "filename": st.column_config.TextColumn("Filename", width="medium"),
            "upload_date": st.column_config.TextColumn("Upload Date", width="small"),
            "tags": st.column_config.TextColumn("Tags", width="medium"),
            "word_count": st.column_config.NumberColumn("Word Count", format="%d"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "processing_time_ms": st.column_config.NumberColumn("Processing Time (ms)", format="%d ms"),
        },
        use_container_width=True,
        hide_index=True,
    )

st.markdown("---")

# -------------------------------------------------------------
# Document Detail & OCR Snippet Inspector
# -------------------------------------------------------------
st.subheader("🔎 Document Inspector")

if not df_filtered.empty:
    file_list = df_filtered["filename"].tolist()
    selected_file = st.selectbox("Select document to inspect:", options=file_list)

    if selected_file:
        doc_row = df_filtered[df_filtered["filename"] == selected_file].iloc[0]

        detail_col1, detail_col2 = st.columns([1, 2])
        with detail_col1:
            st.markdown(f"**Document ID:** `{doc_row['document_id']}`")
            st.markdown(f"**Upload Date:** {doc_row['upload_date']}")
            st.markdown(f"**File Size:** `{doc_row['size_bytes']:,} bytes`")
            st.markdown(f"**Status:** `{doc_row['status']}`")
            st.markdown(f"**Tags:** `{', '.join(doc_row['tags']) if isinstance(doc_row['tags'], list) else doc_row['tags']}`")
            st.markdown(f"**Word Count:** `{doc_row['word_count']:,} words`")

        with detail_col2:
            st.markdown("**Extracted OCR Text Preview:**")
            st.text_area(
                label="Extracted Text Snippet",
                value=doc_row["text_snippet"] or "(No text extracted)",
                height=150,
                disabled=True,
            )
