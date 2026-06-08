param(
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [string]$ApiKey = $env:POS_API_KEY,
    [string]$DatasetDir = "",
    [string]$ContextPath = "",
    [int]$TargetMinutes = 5,
    [int]$HardCapMinutes = 30
)

$ErrorActionPreference = "Stop"

if (-not $DatasetDir) {
    $DatasetDir = Join-Path $PSScriptRoot "..\..\..\generated_dataset_v2"
}
if (-not $ContextPath) {
    $ContextPath = Join-Path $PSScriptRoot "strema_portfolio_context.md"
}

$datasetDirResolved = (Resolve-Path $DatasetDir).Path
$contextResolved = (Resolve-Path $ContextPath).Path

$requiredFiles = @(
    "merchants.csv",
    "sales_daily.csv",
    "payments_daily.csv",
    "bank_daily.csv",
    "obligations.csv"
)

foreach ($name in $requiredFiles) {
    $full = Join-Path $datasetDirResolved $name
    if (-not (Test-Path $full)) {
        throw "Missing required dataset file: $full"
    }
}

$meta = [ordered]@{
    dataset_kind = "daily_financial_portfolio"
    currency = "SAR"
    synthetic = $true
}
if ($TargetMinutes -gt 0) {
    $meta.analysis_time_target_minutes = $TargetMinutes
}
if ($HardCapMinutes -gt 0) {
    $meta.analysis_time_hard_cap_minutes = $HardCapMinutes
}
$metaJson = $meta | ConvertTo-Json -Compress

$curlArgs = @(
    "-sS",
    "-X", "POST",
    "$BaseUrl/jobs",
    "-F", "context_file=@$contextResolved",
    "-F", "meta=$metaJson"
)

if ($ApiKey) {
    $curlArgs += @("-H", "X-API-Key: $ApiKey")
}

foreach ($name in $requiredFiles) {
    $full = Join-Path $datasetDirResolved $name
    $curlArgs += @("-F", "files=@$full")
}

Write-Host "Submitting dataset from $datasetDirResolved to $BaseUrl/jobs"
curl.exe @curlArgs
