# EcoByte one-command start (Windows PowerShell). First run installs everything and seeds demo data.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python -m pip install -q -r requirements.txt
.\.venv\Scripts\python -m app.seed
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Set-Location "$root\backend"
Write-Host "`nEcoByte running at http://localhost:8000  (admin@ecobyte.app / Admin@123, student@ecobyte.app / Student@123)`n"
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
