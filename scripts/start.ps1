param([switch]$SyntheticTest, [ValidateRange(1024,65535)][int]$Port=8765)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $env:CASH_API_KEY) { throw 'Set CASH_API_KEY in this process. Permanent keys require explicit approval.' }
$taskPython=Join-Path $PWD '.venv-patched\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Patched isolated runtime missing; do not fall back to the historical environment.' }
$taskArguments=@('scripts/serve.py','--port',[string]$Port)
if ($SyntheticTest) { $taskArguments+='--synthetic-test' }
# One maintained Python entrypoint owns offline settings, loopback binding and
# both generated MOV whitelist entries. No persistent environment is changed.
& $taskPython @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Local service exited unsuccessfully.' }
