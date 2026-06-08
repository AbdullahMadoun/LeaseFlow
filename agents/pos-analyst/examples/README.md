# Example job: Strema simulated portfolio

This folder prepares the generated Strema dataset for the POS analyst service.

Files:

- `strema_portfolio_context.md`
  - Business brief for the analyst. Orients it toward portfolio, underwriting, and liquidity-risk analysis.
- `submit_strema_job.ps1`
  - PowerShell helper that uploads the five exported schema files to a running POS analyst API.
- `strema_vast_runbook.md`
  - Exact scout -> deploy -> submit -> poll -> destroy sequence for Vast.

Default dataset location:

- `D:\downloads\Strema\generated_dataset_v2`

Usage from PowerShell:

```powershell
$env:POS_API_KEY = "<your-pos-api-key>"
.\submit_strema_job.ps1 -BaseUrl "http://<vm-host>:8080"
```

Override dataset or context paths if needed:

```powershell
.\submit_strema_job.ps1 `
  -BaseUrl "http://<vm-host>:8080" `
  -DatasetDir "D:\downloads\Strema\generated_dataset_v2" `
  -ContextPath "D:\downloads\Strema\stream-hacka\pos-analyst\examples\strema_portfolio_context.md"
```
