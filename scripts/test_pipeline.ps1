<#
.SYNOPSIS
    Live End-to-End Pipeline Verification Script in PowerShell.
#>
param(
    [string]$ProjectId = "serverless-application-511208",
    [string]$BucketName = "serverless-application-511208-raw-docs",
    [string]$DatasetId = "doc_analytics",
    [string]$TableId = "processed_documents"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 🧪 Live Pipeline Verification on Google Cloud" -ForegroundColor Cyan
Write-Host " Project:   $ProjectId" -ForegroundColor Green
Write-Host " Bucket:    $BucketName" -ForegroundColor Green
Write-Host " BigQuery:  $ProjectId.$DatasetId.$TableId" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

$Timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$TempDir = Join-Path $env:TEMP "gcp_test_$Timestamp"
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

$InvoicePath = Join-Path $TempDir "vendor_invoice_$Timestamp.pdf"
$ContractPath = Join-Path $TempDir "legal_contract_$Timestamp.txt"
$ZipPath = Join-Path $TempDir "archive_data_$Timestamp.zip"

"Simulated Invoice INV-2026-001 Total: $1500" | Set-Content $InvoicePath
"Mutual Non-Disclosure Agreement contract between Acme and Partner." | Set-Content $ContractPath
"Dummy zip payload" | Set-Content $ZipPath

try {
    Write-Host "`n[1/4] 📤 Uploading test documents to gs://$BucketName..." -ForegroundColor Cyan
    gcloud storage cp $InvoicePath "gs://$BucketName/invoices/vendor_invoice_$Timestamp.pdf" --quiet
    gcloud storage cp $ContractPath "gs://$BucketName/contracts/legal_contract_$Timestamp.txt" --quiet
    gcloud storage cp $ZipPath "gs://$BucketName/unsupported/archive_data_$Timestamp.zip" --quiet
    Write-Host "[+] Files uploaded successfully." -ForegroundColor Green

    Write-Host "`n[2/4] ⏳ Waiting 8s for Pub/Sub and Cloud Run processing..." -ForegroundColor Cyan
    Start-Sleep -Seconds 8

    Write-Host "`n[3/4] 📋 Inspecting recent Cloud Run logs..." -ForegroundColor Cyan
    gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=doc-processor" `
        --project=$ProjectId --limit=8 --format="value(jsonPayload.message,textPayload)"

    Write-Host "`n[4/4] 🔍 Querying BigQuery dataset..." -ForegroundColor Cyan
    $Query = "SELECT document_id, filename, status, word_count, TO_JSON_STRING(tags) AS tags, processing_time_ms FROM \`$ProjectId.$DatasetId.$TableId\` WHERE filename LIKE '%$Timestamp%' ORDER BY processed_at DESC;"
    bq query --use_legacy_sql=false --project_id=$ProjectId $Query

    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host " ✅ Live Pipeline Verification Complete!" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
}
finally {
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}
