# Démarre ou met à jour les trois services de la plateforme.
$ErrorActionPreference = "Stop"
$ComposeFile = Join-Path $PSScriptRoot "docker-compose.yml"
$EnvFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "Copiez docker/.env.example vers docker/.env et remplacez les secrets avant le démarrage." }
docker compose --env-file $EnvFile -f $ComposeFile up -d --build
docker compose --env-file $EnvFile -f $ComposeFile ps
