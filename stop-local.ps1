# Arrête uniquement les processus enregistrés par start-local.ps1.
$ErrorActionPreference = "Stop"
$RuntimeRoot = Join-Path $PSScriptRoot ".runtime"
foreach ($Name in @("backend", "frontend")) {
    $PidFile = Join-Path $RuntimeRoot "$Name.pid"
    if (Test-Path -LiteralPath $PidFile) {
        $ProcessId = [int](Get-Content -LiteralPath $PidFile)
        $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($Process) { Stop-Process -Id $ProcessId -Force; Write-Host "$Name arrêté (PID $ProcessId)." }
        Remove-Item -LiteralPath $PidFile -Force
    }
}
