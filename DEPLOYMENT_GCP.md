# Deploy Stock Analysis API to Google Cloud

This guide walks you through deploying the Stock Analysis Pipeline to **Google Cloud Run**—a serverless platform that automatically scales your app and charges only when it runs.

---

## What You Need Before Starting

1. **A Google account** (Gmail)
2. **A credit card** (Google Cloud free tier: ~$300 credit for 90 days; Cloud Run free tier: 2M requests/month)
3. **About 15–20 minutes** for one-time setup

---

## Part 1: One-Time Setup

### Step 1: Install Google Cloud CLI

1. Go to: **https://cloud.google.com/sdk/docs/install**
2. Download the installer for your OS:
   - **Windows**: Run the `.exe` installer
   - **Mac**: Run: `brew install google-cloud-sdk` or use the installer
   - **Linux**: Run the `install.sh` script from the page
3. Open a new terminal/PowerShell and run:
   ```bash
   gcloud init
   ```
4. Log in with your Google account when prompted.
5. Choose or create a project. If creating new, pick a name like `stock-analysis-demo`.

### Step 2: Enable Required APIs

Run these in your terminal (one at a time):

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### Step 3: Set Your Project

```bash
gcloud config set project YOUR_PROJECT_ID
```

Replace `YOUR_PROJECT_ID` with your actual project ID (e.g. `stock-analysis-demo-123456`).

---

## Part 2: Deploy the Application

### Option A: One-Command Deploy (Recommended)

From the project root directory:

**Windows (PowerShell):**
```powershell
.\deploy.ps1
```

**Mac/Linux:**
```bash
chmod +x deploy.sh
./deploy.sh
```

### Option B: Manual Deploy

```bash
gcloud builds submit --config=cloudbuild.yaml .
```

This will:
- Build a Docker image
- Push it to Google Container Registry
- Deploy it to Cloud Run
- Return your live URL when finished (usually within 5–10 minutes)

---

## Part 3: Use Your Live Application

1. After deployment, copy the **Service URL** from the output, e.g.:
   ```
   https://stock-analysis-api-xxxxx-uc.a.run.app
   ```
2. Open that URL in your browser.
3. You should see the Stock Analysis Pipeline UI. You can run analysis as usual.

---

## Part 4: Maintenance & Updates

### Redeploy After Code Changes

Run the same deploy command again:

```powershell
.\deploy.ps1
```

or

```bash
./deploy.sh
```

### View Logs

```bash
gcloud run services logs read stock-analysis-api --region=us-central1
```

### View Service Status

```bash
gcloud run services describe stock-analysis-api --region=us-central1
```

### Stop/Delete the Service (No More Charges)

```bash
gcloud run services delete stock-analysis-api --region=us-central1
```

---

## Important Notes

### Data Persistence (Ephemeral Storage)

- Data (SQLite DB, CSVs, reports) is stored in **ephemeral storage**.
- When the app scales to zero (no traffic), data is lost.
- For persistent data, you would add Cloud Storage integration (requires code changes).

### Costs (Typical Usage)

- **Cloud Run**: Free tier covers ~2 million requests/month; after that, ~$0.00002400 per request.
- **Cloud Build**: Free tier covers ~120 build-minutes/day.
- For light use, you often stay within the free tier.

### Pipeline Runtime

- Long analysis runs (e.g. 30+ minutes) may hit Cloud Run’s default timeout.
- The deployment is configured for a 1-hour timeout and 2GB memory.
- If runs exceed that, consider increasing memory or timeout in `cloudbuild.yaml`.

### Changing Region

To deploy in a different region (e.g. `us-east1`), edit `cloudbuild.yaml` and change:

```yaml
- '--region'
- 'us-east1'   # was us-central1
```

---

## Troubleshooting

### "Permission denied" or "API not enabled"

- Ensure all required APIs are enabled (Part 1, Step 2).
- Check that billing is enabled: **https://console.cloud.google.com/billing**

### Build Fails

- Check you’re in the project root (where `cloudbuild.yaml` and `Dockerfile` are).
- Run: `gcloud builds list` to see recent builds and their status.

### App Returns 502 or 503

- Inspect logs: `gcloud run services logs read stock-analysis-api --region=us-central1`
- Ensure the app listens on `PORT` (Cloud Run sets this; the code already supports it).

### Need Help?

- Google Cloud docs: **https://cloud.google.com/run/docs**
- Cloud Run pricing: **https://cloud.google.com/run/pricing**
