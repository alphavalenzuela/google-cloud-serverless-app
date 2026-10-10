<#
.SYNOPSIS
    Deploy the Serverless Document Processing Pipeline to Google Cloud using PowerShell.
.PARAMETER ProjectId
    The Google Cloud Project ID.
.PARAMETER Region
    The Google Cloud Region (default: us-central1).
.PARAMETER BucketName
    The globally unique Cloud Storage bucket name.
#>
param(
    [string]$ProjectId = $env:PROJECT_ID,
    [string]$Region = "us-central1",
    [string]$BucketName = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) {
    Write-Error "ProjectId is required. Example usage: .\scripts\deploy.ps1 -ProjectId 'serverless-application-511208'"
}

if (-not $BucketName) {
    $BucketName = "$ProjectId-raw-documents"
}

$ImageName = "gcr.io/$ProjectId/doc-processor:latest"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Deploying Document Processing Pipeline" -ForegroundColor Cyan
Write-Host " Project:  $ProjectId" -ForegroundColor Green
Write-Host " Region:   $Region" -ForegroundColor Green
Write-Host " Bucket:   $BucketName" -ForegroundColor Green
Write-Host " Image:    $ImageName" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify prerequisite CLI tools
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "`n[-] 'gcloud' CLI is not detected in your PATH." -ForegroundColor Yellow
    Write-Host "    Install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    Write-Host "    Or run this deployment directly inside Google Cloud Shell (cloud.google.com) where all tools are pre-installed." -ForegroundColor Yellow
    exit 1
}

if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
    Write-Host "`n[-] 'terraform' CLI is not detected in your PATH." -ForegroundColor Yellow
    Write-Host "    Install Terraform: https://developer.hashicorp.com/terraform/install" -ForegroundColor Yellow
    exit 1
}

# 2. Enable Required GCP APIs
Write-Host "[+] Enabling required GCP service APIs..." -ForegroundColor Cyan
gcloud services enable `
    run.googleapis.com `
    pubsub.googleapis.com `
    storage.googleapis.com `
    bigquery.googleapis.com `
    cloudbuild.googleapis.com `
    --project=$ProjectId

# 3. Build container with Cloud Build
Write-Host "[+] Building container image via Google Cloud Build..." -ForegroundColor Cyan
gcloud builds submit --tag $ImageName --project=$ProjectId .

# 4. Terraform Provisioning
Write-Host "[+] Provisioning infrastructure via Terraform..." -ForegroundColor Cyan
Push-Location terraform
try {
    terraform init
    terraform apply -auto-approve `
        -var="project_id=$ProjectId" `
        -var="region=$Region" `
        -var="bucket_name=$BucketName" `
        -var="container_image=$ImageName"
}
finally {
    Pop-Location
}

Write-Host "`n[+] Deployment finished successfully!" -ForegroundColor Green
