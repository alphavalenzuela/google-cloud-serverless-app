"""Unit tests for the dashboard web applications."""

import pytest
from dashboard.flask_app import app as flask_app
from dashboard.app import get_mock_data


def test_flask_dashboard_index():
    client = flask_app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Serverless Document Processing Dashboard" in html
    assert "Filename" in html
    assert "Upload Date" in html
    assert "Tags" in html
    assert "Word Count" in html


def test_flask_dashboard_tag_filter():
    client = flask_app.test_client()
    response = client.get("/?tag=finance")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "vendor_invoice_109.pdf" in html
    # Documents without finance tag should not be present in the filtered view
    assert "senior_cloud_architect_resume.pdf" not in html


def test_streamlit_mock_dataframe():
    df = get_mock_data()
    assert not df.empty
    expected_cols = {"document_id", "filename", "upload_date", "tags", "word_count", "status"}
    assert expected_cols.issubset(set(df.columns))

    # Test filtering by tag
    finance_docs = df[df["tags"].apply(lambda t: "finance" in t)]
    assert len(finance_docs) >= 1
