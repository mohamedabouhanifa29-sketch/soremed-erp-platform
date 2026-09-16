# Lance FastAPI et Vite en arrière-plan sur Windows, sans Docker.
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$RuntimeRoot = Join-Path $ProjectRoot ".runtime"
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
$PythonCandidates = @((Join-Path $BackendRoot "venv\Scripts\python.exe"), (Join-Path $ProjectRoot ".venv\Scripts\python.exe"))
$PythonExe = $PythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $PythonExe) { throw "Environnement Python absent. Créez backend\venv puis installez backend\requirements.txt." }
if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) { throw "Dépendances frontend absentes. Lancez npm.cmd install dans frontend." }
$BackendProcess = Start-Process -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" -WorkingDirectory $BackendRoot -WindowStyle Hidden -PassThru
$FrontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev", "--", "--host", "0.0.0.0" -WorkingDirectory $FrontendRoot -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $RuntimeRoot "backend.pid") -Value $BackendProcess.Id
Set-Content -LiteralPath (Join-Path $RuntimeRoot "frontend.pid") -Value $FrontendProcess.Id
Start-Sleep -Seconds 3
Write-Host "SOREMED démarré. Interface : http://localhost:5173 - API : http://localhost:8000/api/docs"
Write-Host "Depuis le LAN, utilisez http://ADRESSE_IP_DU_SERVEUR:5173"
