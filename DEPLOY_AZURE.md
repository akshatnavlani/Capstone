# Deploying the app on Azure (24 Nov 2026)

Everything runs in one cloud: the database is already Azure PostgreSQL; the backend (FastAPI + ML models) and the
frontend (Next.js) run as two **Azure Container Apps**, using the Docker images built from this repository.
Run every command in **PowerShell** from the repository folder `C:\Users\Shimona\Documents\casptone`.
Lines in `<angle brackets>` are yours to fill in. Never paste the database password into a file or a chat.

## Why Azure and not Vercel
Vercel hosts only websites. Our backend runs ML models (CLIP, BERT, GAIL, RoBERTa) that need about 4 GB of memory, and the
database is on Azure, so the backend, frontend and database sit in one cloud with a private, firewall-limited connection.

## Cost (check the Azure pricing calculator before you start)
- Container Apps bills per second of use and includes a monthly free amount (about 180,000 vCPU-seconds and 360,000 GiB-seconds).
  The backend uses 2 vCPU and 4 GiB, so the free amount covers roughly 25 hours of running per month.
- Keeping the backend on all the time (24 x 7) would cost roughly 150 USD a month, more than a student credit. So the commands
  below let it **scale to zero** when nobody uses it. The first visit after a pause waits about 1-2 minutes while it starts;
  open the site a few minutes before a demo.
- Azure Container Registry (Basic) costs about 5 USD a month.

## 0. One-time setup
```powershell
winget install --exact --id Microsoft.AzureCLI
```
Close and reopen PowerShell, then:
```powershell
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az postgres flexible-server list --query "[].{name:name, group:resourceGroup, region:location}" -o table
```
The last command shows your database's **name**, **resource group** and **region**. Use them below.

## 1. Names used in the commands
```powershell
$RG  = "<resource group of the database>"
$LOC = "<region of the database, e.g. centralindia>"
$ACR = "<a unique lowercase name, e.g. capstone011registry>"
$PG  = "<database server name>"
```

## 2. Image registry, and upload the backend image
```powershell
az acr create -g $RG -n $ACR --sku Basic --admin-enabled true
az acr login -n $ACR
docker tag capstone-backend-full "$ACR.azurecr.io/capstone-backend:v1"
docker push "$ACR.azurecr.io/capstone-backend:v1"
```
(The image is built locally first: `docker compose build backend`. The push uploads about 2 GB once.)

## 3. Let Azure services reach the database
```powershell
az postgres flexible-server firewall-rule create -g $RG -n $PG --rule-name allow-azure-services --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
```
(0.0.0.0 here is Azure's special rule for "services inside Azure", not the whole internet.)

## 4. Container Apps environment and the backend
```powershell
az containerapp env create -g $RG -n capstone-env -l $LOC
$DB = Read-Host "Paste DATABASE_URL (hidden from this file)"
az containerapp create -g $RG -n capstone-backend --environment capstone-env `
  --image "$ACR.azurecr.io/capstone-backend:v1" --registry-server "$ACR.azurecr.io" `
  --target-port 8000 --ingress external --cpu 2 --memory 4Gi --min-replicas 0 --max-replicas 1 `
  --secrets db-url=$DB --env-vars DATABASE_URL=secretref:db-url
Remove-Variable DB
$API = az containerapp show -g $RG -n capstone-backend --query properties.configuration.ingress.fqdn -o tsv
"Backend: https://$API/health"
```
Open the printed address; it should show `"status":"ok","db_connected":true` (wait 1-2 minutes on the first open).

## 5. Frontend (built with the backend's address inside it)
```powershell
docker build ./frontend --build-arg NEXT_PUBLIC_API_BASE_URL="https://$API" -t "$ACR.azurecr.io/capstone-frontend:v1"
docker push "$ACR.azurecr.io/capstone-frontend:v1"
az containerapp create -g $RG -n capstone-frontend --environment capstone-env `
  --image "$ACR.azurecr.io/capstone-frontend:v1" --registry-server "$ACR.azurecr.io" `
  --target-port 3000 --ingress external --cpu 0.5 --memory 1Gi --min-replicas 0 --max-replicas 1
$WEB = az containerapp show -g $RG -n capstone-frontend --query properties.configuration.ingress.fqdn -o tsv
"Website: https://$WEB"
```

## 6. Allow the website to call the backend (CORS)
```powershell
az containerapp update -g $RG -n capstone-backend --set-env-vars CORS_ALLOW_ORIGINS="https://$WEB"
```

## 7. Check
Open `https://$WEB`: New brief -> Find my creators (Live Match), Ranked creators, Creator Passport, Niche Map,
Campaign Simulator, Analysis. Scores should be real (for a protein brief, Sonal Kapoor about 80).

## Updating after code changes
Rebuild and push with a new tag (v2, v3 ...), then:
```powershell
az containerapp update -g $RG -n capstone-backend --image "$ACR.azurecr.io/capstone-backend:v2"
az containerapp update -g $RG -n capstone-frontend --image "$ACR.azurecr.io/capstone-frontend:v2"
```

## Stopping it (to save credit)
```powershell
az containerapp update -g $RG -n capstone-backend --min-replicas 0
```
With min-replicas 0 it already costs nothing while idle. To remove everything: delete the two container apps,
the environment and the registry in the Azure portal (the database is not touched).
