# Restaure explicitement une sauvegarde choisie; cette opération remplace les données courantes.
param([Parameter(Mandatory=$true)][string]$BackupFile)
$ErrorActionPreference = "Stop"
$ResolvedBackup = Resolve-Path -LiteralPath $BackupFile
$ExpectedRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "backups"))
if (-not $ResolvedBackup.Path.StartsWith($ExpectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "La sauvegarde doit se trouver dans $ExpectedRoot" }
Get-Content -LiteralPath $ResolvedBackup.Path | docker compose --env-file (Join-Path $PSScriptRoot "..\docker\.env") -f (Join-Path $PSScriptRoot "..\docker\docker-compose.yml") exec -T database psql -U soremed -d soremed
Write-Host "Restauration terminée depuis : $($ResolvedBackup.Path)"
