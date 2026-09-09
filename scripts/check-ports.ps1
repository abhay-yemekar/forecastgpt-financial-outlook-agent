# check-ports.ps1 — verify the host ports ForecastGPT wants are actually free.
#
# Reads REDIS_PORT from .env (default 6380 — this repo never assumes 6379).
# If a port is already bound, it reports WHICH container/process holds it and
# tells you to bump REDIS_PORT in .env. It NEVER suggests stopping, restarting,
# or reusing a container it does not recognize.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/check-ports.ps1

$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Load REDIS_PORT from .env if not already in the environment
$port = $env:REDIS_PORT
if (-not $port -and (Test-Path "$scriptDir\..\.env")) {
    $match = Select-String -Path "$scriptDir\..\.env" -Pattern '^\s*REDIS_PORT\s*=\s*(\d+)' |
        Select-Object -Last 1
    if ($match) { $port = $match.Matches[0].Groups[1].Value }
}
if (-not $port) { $port = "6380" }

Write-Host "Checking host port(s) for ForecastGPT dependencies..."
Write-Host "  REDIS_PORT = $port"

$fail = $false

$connections = Get-NetTCPConnection -LocalPort ([int]$port) -State Listen
if ($connections) {
    $fail = $true
    Write-Host ""
    Write-Host "  PORT $port IS ALREADY IN USE by:"

    # Prefer docker's own view: any container publishing this host port?
    $holder = docker ps --filter "publish=$port" --format "{{.Names}} ({{.Image}}, {{.Ports}})" |
        Select-Object -First 3
    if ($holder) {
        $holder | ForEach-Object { Write-Host "    docker container: $_" }
    }
    else {
        # Fall back to the owning process (best effort)
        $pid = ($connections | Select-Object -First 1).OwningProcess
        $proc = Get-Process -Id $pid
        Write-Host "    non-docker process '$($proc.ProcessName)' (pid $pid)"
    }

    $next = [int]$port + 1
    Write-Host ""
    Write-Host "  ACTION: bump REDIS_PORT in .env to any free port (e.g. $next)"
    Write-Host "          and keep REDIS_URL in sync (redis://localhost:<port>/0)."
    Write-Host "  NOTE: do not stop or reuse the existing container/process - it may"
    Write-Host "        belong to another project on this machine."
}
else {
    Write-Host "  port ${port}: free"
}

Write-Host ""
if ($fail) {
    Write-Host "FAILED - resolve the conflict(s) above (change OUR port, not theirs)."
    exit 1
}
Write-Host "OK - all ForecastGPT dependency ports are free."
exit 0
