# check-ports.ps1 — verify the host ports ForecastGPT's compose stack wants
# are actually free.
#
# Ports checked (read from .env, all overridable in the environment):
#   REDIS_PORT       (default 6380)  - REQUIRED: the job queue.
#   API_PORT         (default 8000)  - REQUIRED: the compose api service.
#   MYSQL_HOST_PORT  (default 3306)  - WARNING ONLY: needed solely when the
#                                      optional `--profile mysql` service is
#                                      used; a busy 3306 does not stop the
#                                      app (SQLite fallback / remote DB).
#
# If a required port is bound, the script reports WHICH container/process
# holds it and says to bump the matching var in .env. It NEVER suggests
# stopping, restarting, or reusing a container it does not recognize.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/check-ports.ps1

$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Load port vars from .env if not already in the environment
if (Test-Path "$scriptDir\..\.env") {
    foreach ($var in @("REDIS_PORT", "API_PORT", "MYSQL_HOST_PORT")) {
        if (-not (Get-Variable -Name $var -ValueOnly -ErrorAction SilentlyContinue)) {
            $m = Select-String -Path "$scriptDir\..\.env" -Pattern ("^\s*" + $var + "\s*=\s*(\d+)") |
                Select-Object -Last 1
            if ($m) { Set-Variable -Name $var -Value $m.Matches[0].Groups[1].Value }
        }
    }
}

$fail = $false

function Test-Port {
    param([string]$Name, [string]$Var, [string]$Port, [string]$Mode)

    Write-Host ("  {0} (port {1}): " -f $Name, $Port) -NoNewline
    $conns = Get-NetTCPConnection -LocalPort ([int]$Port) -State Listen
    if (-not $conns) {
        Write-Host "free"
        return
    }

    Write-Host "IN USE by:"
    # Prefer docker's own view: any container publishing this host port?
    $holder = docker ps --filter "publish=$Port" --format "{{.Names}} ({{.Image}}, {{.Ports}})" |
        Select-Object -First 3
    if ($holder) {
        $holder | ForEach-Object { Write-Host "      docker container: $_" }
    }
    else {
        $owningPid = ($conns | Select-Object -First 1).OwningProcess
        $proc = Get-Process -Id $owningPid
        Write-Host "      non-docker process '$($proc.ProcessName)' (pid $owningPid)"
    }

    if ($Mode -eq "required") {
        Write-Host "    ACTION: bump $Var in .env to any free port and keep dependent"
        Write-Host "            settings (e.g. REDIS_URL) in sync."
        Write-Host "    NOTE: do not stop or reuse the existing container/process - it may"
        Write-Host "          belong to another project on this machine."
        $script:fail = $true
    }
    else {
        Write-Host "    WARNING: only matters if you run 'docker compose --profile mysql'."
        Write-Host "             If you do, bump $Var in .env first. Not stopping the app."
    }
}

Write-Host "Checking host port(s) for ForecastGPT dependencies..."
# NB: no '??' operator — Windows ships PowerShell 5.1 by default.
$redisPort = $env:REDIS_PORT;      if (-not $redisPort)      { $redisPort = "6380" }
$apiPort = $env:API_PORT;          if (-not $apiPort)        { $apiPort = "8000" }
$mysqlPort = $env:MYSQL_HOST_PORT; if (-not $mysqlPort)      { $mysqlPort = "3306" }

# Duplicate configured host ports: compose cannot bind two services to one
# host port; catch it here, before the socket checks (a duplicated-but-
# unbound port would otherwise report as "free" for both checks).
$claimed = @{}
foreach ($spec in @(
    @{ Var = "REDIS_PORT";      Port = $redisPort; Mode = "required" },
    @{ Var = "API_PORT";        Port = $apiPort;   Mode = "required" },
    @{ Var = "MYSQL_HOST_PORT"; Port = $mysqlPort; Mode = "optional" })) {
    $port = $spec.Port
    if ($claimed.ContainsKey($port)) {
        $other = $claimed[$port]
        if ($spec.Mode -eq "required") {
            Write-Host "  [FAIL] $($spec.Var) and $other are BOTH set to host port $port -"
            Write-Host "         compose cannot bind two services to one port."
            Write-Host "         Change one of them in .env."
            $script:fail = $true
        }
        else {
            Write-Host "  [WARN] $($spec.Var) ($port) collides with $other - harmless for the app,"
            Write-Host "         but 'docker compose --profile mysql' would fail to bind."
        }
    }
    $claimed[$port] = $spec.Var
}

Test-Port -Name "Redis (job queue)"   -Var "REDIS_PORT"      -Port $redisPort -Mode "required"
Test-Port -Name "API service"         -Var "API_PORT"        -Port $apiPort   -Mode "required"
Test-Port -Name "MySQL (opt profile)" -Var "MYSQL_HOST_PORT" -Port $mysqlPort -Mode "optional"

Write-Host ""
if ($fail) {
    Write-Host "FAILED - resolve the conflict(s) above (change OUR port, not theirs)."
    exit 1
}
Write-Host "OK - all required ForecastGPT dependency ports are free."
exit 0
