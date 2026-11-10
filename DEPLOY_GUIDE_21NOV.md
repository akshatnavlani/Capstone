# Deploying the app before 21 Nov 2026: website on Vercel, backend on Azure

Checked on 10 Nov 2026: `next build` passes (9 pages); the backend Docker image (`backend/Dockerfile`, build context =
repo root) builds and `/health` returns `{"status":"ok","db_connected":true}`. No code change is needed; only accounts
and three settings. Steps that need a login are Shimona's (Claude must not sign in or type passwords).

## What needs Shimona (about 30 minutes in total)
1. Azure: confirm the Azure for Students credit (portal.azure.com -> "Education" or "Subscriptions"). The database
   already runs there, so the same subscription is used.
2. Vercel: sign in at vercel.com with GitHub. The repo is `akshatnavlani/Capstone`: if Vercel cannot see it, the repo
   owner (Akshat) must grant the Vercel GitHub app access, or deploy from a fork.

## 1. Backend on Azure Container Apps (free monthly allowance covers a demo)
In a terminal on the laptop, from the repo root (Azure CLI: `winget install Microsoft.AzureCLI`, then `az login`):

```
az group create -n capstone-rg -l centralindia
az acr create -n capstoneacr011 -g capstone-rg --sku Basic --admin-enabled true
az acr build -r capstoneacr011 -t capstone-backend:21nov -f backend/Dockerfile .
az containerapp up -n capstone-backend -g capstone-rg --image capstoneacr011.azurecr.io/capstone-backend:21nov --registry-server capstoneacr011.azurecr.io --target-port 8000 --ingress external
```
(`capstoneacr011` must be unique across Azure; if it is taken, pick another name and use it in every line.)
Then set the two settings (the database address is the one in `.env`; type it yourself, never paste it in chat):
```
az containerapp secret set -n capstone-backend -g capstone-rg --secrets db-url="<DATABASE_URL from .env>"
az containerapp update -n capstone-backend -g capstone-rg --set-env-vars DATABASE_URL=secretref:db-url CORS_ALLOW_ORIGINS=https://<your-app>.vercel.app --min-replicas 1
```
- Database networking: Azure portal -> the PostgreSQL server -> Networking -> tick "Allow public access from any Azure
  service within Azure to this server" (otherwise the container cannot reach the database).
- Check: open `https://<backend-url>/health` -> `{"status":"ok","db_connected":true}`.
- `--min-replicas 1` avoids a slow first load on the event day; set it back to 0 after 21 Nov to save credit.

## 2. Website on Vercel
vercel.com -> Add New -> Project -> import `Capstone`:
- Root Directory: `frontend`; Framework: Next.js (auto).
- Environment variable: `NEXT_PUBLIC_API_BASE_URL` = `https://<backend-url>` (no slash at the end).
- Settings -> Git -> Production Branch: `review2-shimona-temporal` (the branch to demo from).
- Deploy; then put the Vercel address into `CORS_ALLOW_ORIGINS` on the backend (step 1) if it differs.

## 3. Final check (Claude can do this once the two addresses exist)
Every page loads, `/recommendations` answers, the graph and the Analysis tab show data, no CORS errors in the browser console.
