param([switch]$SyntheticTest, [int]$Port=8765)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $env:CASH_API_KEY) { throw 'Set CASH_API_KEY in this process. Permanent keys require explicit approval.' }
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; $env:HF_HUB_DISABLE_TELEMETRY='1'
$env:TEMP=Join-Path $PWD '.private\tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory $env:TEMP -Force | Out-Null
if ($SyntheticTest) {
    $env:CASH_MODE='synthetic_test'
    & '.venv\Scripts\python.exe' scripts/synthetic.py
    $env:CASH_TEST_HASHES=(& '.venv\Scripts\python.exe' -c "import hashlib,pathlib; print(hashlib.file_digest(pathlib.Path('.private/synthetic/safe.mov').open('rb'),'sha256').hexdigest())")
} else {
    $env:CASH_MODE='model'
    if (-not (Test-Path 'models\qwen3-vl-2b\model.safetensors')) { throw 'Local model missing. Run download_model.py before serving.' }
}
& '.venv\Scripts\python.exe' -m uvicorn cashreview.api:create_app --factory --host 127.0.0.1 --port $Port --no-access-log --log-level warning
