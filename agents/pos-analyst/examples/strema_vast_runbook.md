# Strema -> Vast runbook

This runbook deploys the POS analyst to a Vast VM, then submits the Strema synthetic daily financial portfolio dataset.

## 1. Set required secrets

PowerShell:

```powershell
$env:VAST_API_KEY = "<your-vast-api-key>"
$env:MINIMAX_API_KEY = "<your-minimax-api-key>"
$env:POS_API_KEY = "<choose-a-shared-api-key>"
```

## 2. Scout a VM

```powershell
cd D:\downloads\Strema\stream-hacka\pos-analyst\scripts
python .\deploy_vast.py scout
```

The deployment is VM-based by design because the service needs Docker on the remote host for sibling sandbox containers.

## 3. Rent and deploy

```powershell
python .\deploy_vast.py up `
  --pos-api-key "$env:POS_API_KEY" `
  --disk-gb 80 `
  --workers 2
```

If you want to pin a specific offer:

```powershell
python .\deploy_vast.py up `
  --offer-id <offer_id> `
  --pos-api-key "$env:POS_API_KEY" `
  --disk-gb 80 `
  --workers 2
```

Save the printed values:

- `instance_id`
- `ssh` command
- API URL, typically `http://<vm-host>:8080`

## 4. Health check

```powershell
curl.exe -s "http://<vm-host>:8080/health"
```

## 5. Submit the Strema dataset

```powershell
cd D:\downloads\Strema\stream-hacka\pos-analyst\examples
.\submit_strema_job.ps1 -BaseUrl "http://<vm-host>:8080" -ApiKey "$env:POS_API_KEY"
```

That uploads:

- `merchants.csv`
- `sales_daily.csv`
- `payments_daily.csv`
- `bank_daily.csv`
- `obligations.csv`

from `D:\downloads\Strema\generated_dataset_v2`.

## 6. Poll the job

```powershell
curl.exe -s -H "X-API-Key: $env:POS_API_KEY" "http://<vm-host>:8080/jobs/<job_id>"
curl.exe -s -H "X-API-Key: $env:POS_API_KEY" "http://<vm-host>:8080/jobs/<job_id>/findings"
curl.exe -s -H "X-API-Key: $env:POS_API_KEY" "http://<vm-host>:8080/jobs/<job_id>/report"
```

## 7. Destroy the VM when done

```powershell
cd D:\downloads\Strema\stream-hacka\pos-analyst\scripts
python .\deploy_vast.py down --instance-id <instance_id>
```
