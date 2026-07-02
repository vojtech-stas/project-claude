<#
.SYNOPSIS
  tools/dashboard-up.ps1 - idempotent "ensure dashboard up + fresh" (slice #1053).

.DESCRIPTION
  The dashboard server dies whenever the Claude session that spawned it exits
  (child process) because the SessionStart autostart hook only fires on fresh
  sessions, not resumed ones. This script gives a standalone, PowerShell-native
  way to detect + relaunch the dashboard DETACHED from any parent shell, so it
  survives session exit. It also detects staleness (#726 class): a listener
  answering on the target port but serving an old sha gets killed + relaunched.

  Steps:
    1. Resolve PORT (env DASH_PORT, default 8766) and TARGET worktree dir
       (the 'live-dashboard' worktree if it exists under .claude/worktrees,
       else the repo root).
    2. If something LISTENS on PORT: query /api/meta (short timeout).
       - Responds AND sha == git -C <target> rev-parse origin/develop → fresh;
         print "already up + fresh" and exit 0.
       - Otherwise (stale or unresponsive) → kill that PID, then continue to
         the update + relaunch steps below.
    3. Update target: only when TARGET is the live-dashboard worktree, run
       git fetch + git reset --hard origin/develop. NEVER reset the repo root.
    4. Launch DETACHED via Start-Process -WindowStyle Hidden with DASH_PORT
       set in the environment. Poll /api/meta up to ~20s; print sha + stale.

.PARAMETER CheckOnly
  Run ONLY the detection logic (step 2's LISTEN + /api/meta + sha comparison)
  and print the decision it WOULD take, WITHOUT killing or launching anything.
  Exists so the logic is testable without a real server lifecycle (slice #1053
  test-first requirement). Exit 0 always in -CheckOnly mode (informational).

.NOTES
  PowerShell 5.1-compatible (no pwsh-only syntax). No writes to .claude/logs/
  (R-FIXTURE). No promote.sh / main interaction.
#>

param(
    [switch]$CheckOnly
)

# --- Config -----------------------------------------------------------------
$PORT = if ($env:DASH_PORT) { [int]$env:DASH_PORT } else { 8766 }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir

$LiveDashboardWorktree = Join-Path $RepoRoot ".claude\worktrees\live-dashboard"
if (Test-Path $LiveDashboardWorktree) {
    $TARGET = $LiveDashboardWorktree
} else {
    $TARGET = $RepoRoot
}

$IsLiveDashboardTarget = ($TARGET -eq $LiveDashboardWorktree)

function Write-Info($msg) {
    Write-Host "[dashboard-up] $msg"
}

# --- Step 2: detect what's on PORT ------------------------------------------
function Get-ListeningPid([int]$port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        if ($conns) {
            return ($conns | Select-Object -First 1 -ExpandProperty OwningProcess)
        }
    } catch {
        # Get-NetTCPConnection unavailable or no match - fall back to netstat.
        $lines = netstat -ano 2>$null | Select-String -Pattern (":$port\s.*LISTENING")
        foreach ($line in $lines) {
            $parts = ($line.ToString().Trim() -split '\s+')
            if ($parts.Length -ge 5) {
                return [int]$parts[-1]
            }
        }
    }
    return $null
}

function Get-ApiMetaSha([int]$port) {
    $uri = "http://127.0.0.1:$port/api/meta"
    try {
        $resp = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        $json = $resp.Content | ConvertFrom-Json
        return $json.sha
    } catch {
        return $null
    }
}

function Get-TargetDevelopSha([string]$targetDir) {
    try {
        $sha = git -C "$targetDir" rev-parse origin/develop 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $sha.Trim()
        }
    } catch { }
    return $null
}

$existingPid = Get-ListeningPid -port $PORT
$developSha = Get-TargetDevelopSha -targetDir $TARGET

$decision = $null   # "already-fresh" | "stale-relaunch" | "would-launch"
$serverSha = $null

if ($existingPid) {
    $serverSha = Get-ApiMetaSha -port $PORT
    if ($serverSha -and $developSha -and ($serverSha -eq $developSha)) {
        $decision = "already-fresh"
    } else {
        $decision = "stale-relaunch"
    }
} else {
    $decision = "would-launch"
}

# --- CheckOnly mode: report decision, touch nothing -------------------------
if ($CheckOnly) {
    Write-Info "target=$TARGET"
    Write-Info "port=$PORT"
    Write-Info "developSha=$developSha"
    if ($existingPid) {
        Write-Info "listeningPid=$existingPid serverSha=$serverSha"
    } else {
        Write-Info "listeningPid=none"
    }
    switch ($decision) {
        "already-fresh"  { Write-Info "decision: already up + fresh" }
        "stale-relaunch" { Write-Info "decision: stale or unresponsive - would kill pid $existingPid and relaunch" }
        "would-launch"   { Write-Info "decision: nothing listening - would launch" }
    }
    exit 0
}

# --- Non-CheckOnly: act on the decision -------------------------------------
if ($decision -eq "already-fresh") {
    Write-Info "already up + fresh (pid=$existingPid sha=$serverSha)"
    exit 0
}

if ($decision -eq "stale-relaunch") {
    Write-Info "stale or unresponsive (pid=$existingPid serverSha=$serverSha developSha=$developSha) - killing..."
    try {
        Stop-Process -Id $existingPid -Force -ErrorAction Stop
        Start-Sleep -Seconds 1
    } catch {
        Write-Info "WARNING: failed to kill pid $existingPid : $_"
    }
}

# --- Step 3: update target (ONLY the live-dashboard worktree) ---------------
if ($IsLiveDashboardTarget) {
    Write-Info "updating live-dashboard worktree to origin/develop..."
    git -C "$TARGET" fetch origin develop 2>&1 | ForEach-Object { Write-Info "  $_" }
    git -C "$TARGET" reset --hard origin/develop 2>&1 | ForEach-Object { Write-Info "  $_" }
} else {
    Write-Info "target is repo root - skipping reset, serving as-is"
}

# --- Step 4: launch DETACHED --------------------------------------------------
$serverScript = Join-Path $TARGET "dashboard\server.py"
if (-not (Test-Path $serverScript)) {
    Write-Info "ERROR: dashboard/server.py not found at $serverScript"
    exit 1
}

Write-Info "launching detached: python $serverScript (DASH_PORT=$PORT)..."

$env:DASH_PORT = "$PORT"
Start-Process -FilePath "python" -ArgumentList "`"$serverScript`"" -WindowStyle Hidden

# --- Poll /api/meta up to ~20s -----------------------------------------------
$deadline = (Get-Date).AddSeconds(20)
$upSha = $null
$upStale = $null
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/api/meta" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        $json = $resp.Content | ConvertFrom-Json
        $upSha = $json.sha
        $upStale = $json.stale
        break
    } catch {
        continue
    }
}

if ($upSha) {
    Write-Info "up: sha=$upSha stale=$upStale"
    exit 0
} else {
    Write-Info "ERROR: server did not respond on /api/meta within 20s"
    exit 1
}
