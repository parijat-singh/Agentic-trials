#!/bin/bash
# Deploy Stock Analysis API to Google Cloud Run
# Run this from the project root after completing one-time setup (see DEPLOYMENT_GCP.md)

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
if [ -z "$PROJECT_ID" ]; then
  echo "Error: Set GOOGLE_CLOUD_PROJECT or run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "Deploying to project: $PROJECT_ID"
echo "Building and pushing..."

gcloud builds submit --config=cloudbuild.yaml .

echo ""
echo "Deployment complete! Your app URL:"
gcloud run services describe stock-analysis-api --region=us-central1 --format='value(status.url)' 2>/dev/null || echo "Run: gcloud run services describe stock-analysis-api --region=us-central1"
