# Deploy Stock Analysis API to Google Cloud Run (PowerShell)
# Run from project root after completing one-time setup (see DEPLOYMENT_GCP.md)

$ErrorActionPreference = "Stop"

$projectId = $env:GOOGLE_CLOUD_PROJECT
if (-not $projectId) {
    $projectId = gcloud config get-value project 2>$null
}
if (-not $projectId) {
    $projectId = "stock-analysis-20250219"
    Write-Host "Using default project: stock-analysis-20250219"
    & gcloud config set project $projectId 2>$null
}

Write-Host "Deploying to project: $projectId"
Write-Host "Building and pushing..."
gcloud builds submit --config=cloudbuild.yaml . --project=$projectId

Write-Host ""
Write-Host "Deployment complete! Your app URL:"
gcloud run services describe stock-analysis-api --region=us-central1 --project=$projectId --format="value(status.url)" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Run: gcloud run services describe stock-analysis-api --region=us-central1" }
