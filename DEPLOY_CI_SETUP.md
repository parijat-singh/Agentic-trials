# GitHub → Cloud Run CI/CD Setup

One-time setup to enable automatic deploy on push to `main`. All deployments use the **stock-analysis** GCP project.

---

## 0. Project: stock-analysis-20250219

This project uses GCP project ID **stock-analysis-20250219** (created for this repo; `stock-analysis` was already taken globally).

1. **Link billing** (required): [Cloud Console → Billing](https://console.cloud.google.com/billing) → Link a billing account to project `stock-analysis-20250219`
2. Set locally: `gcloud config set project stock-analysis-20250219`

---

## 1. Create a GCP Service Account for GitHub Actions

1. In [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts) (with **stock-analysis** selected), create a service account:
   - Name: `github-actions-deploy`
   - Roles: **Cloud Build Editor**, **Cloud Run Admin**, **Service Account User**, **Storage Admin**

2. Create a JSON key for the service account and download it.

---

## 2. Add GitHub Secrets

In your repo: **Settings → Secrets and variables → Actions**, add:

| Secret        | Value                                  |
|---------------|----------------------------------------|
| `GCP_SA_KEY`  | Entire contents of the JSON key file   |
| `GCP_PROJECT_ID` | `stock-analysis-20250219` (this project's GCP project) |

---

## 3. Workflow Behavior

On **push to main**:
1. **Test**: Full pytest suite with coverage (min 25%)
2. **Security**: `pip-audit` vulnerability scan
3. **Deploy**: Build and deploy to Cloud Run (only if 1 and 2 pass)

On **pull request**:

- Same tests and security scan (no deploy)

---

## 4. Local Check Before Pushing

```powershell
pytest tests/ -v --tb=short --cov=. --cov-fail-under=25
pip-audit
```
