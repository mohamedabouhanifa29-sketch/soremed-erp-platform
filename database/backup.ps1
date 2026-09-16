# Produit une sauvegarde PostgreSQL horodatée depuis le conteneur Docker.
$ErrorActionPreference = "Stop"
$BackupDirectory = Join-Path $PSScriptRoot "backups"
New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Target = Join-Path $BackupDirectory "soremed-$Stamp.sql"
docker compose --env-file (Join-Path $PSScriptRoot "..\docker\.env") -f (Join-Path $PSScriptRoot "..\docker\docker-compose.yml") exec -T database pg_dump -U soremed soremed | Set-Content -Encoding UTF8 $Target
Write-Host "Sauvegarde créée : $Target"
