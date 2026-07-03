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

function Write-Info($msg) {
    Write-Host "[dashboard-up] $msg"
}

# --- Target classification: git truth, not path heuristics ------------------
# #1059: the old classification compared $TARGET against a single hardcoded
# ".claude\worktrees\live-dashboard" path. That fails whenever dashboard-up.ps1
# is invoked FROM inside a worktree whose own path doesn't match that literal
# (e.g. $RepoRoot itself resolves to the worktree because the script lives in
# that worktree's own tools/ dir) -- the check silently falls through to
# treating the worktree as "repo root" and SKIPS the freshness reset.
#
# Ask git instead: a target is a WORKTREE iff `git rev-parse --git-dir` !=
# `git rev-parse --git-common-dir` (a real repo root has git-dir ==
# common-dir == ".git"; any linked worktree's git-dir lives under
# <common-dir>/worktrees/<name>, which is OUTSIDE the target). This is true
# regardless of what the worktree happens to be named or where it sits on
# disk.
function Resolve-GitPathAgainst([string]$baseDir, [string]$gitPath) {
    # `git rev-parse --git-dir` / `--git-common-dir` may print EITHER a
    # relative path (resolved against $baseDir) OR an absolute path
    # (typically when the repo lives on a different drive/mount than
    # $baseDir). PowerShell's own Join-Path does NOT collapse when the
    # second argument is already rooted (it naively concatenates), so use
    # [System.IO.Path]::Combine + GetFullPath, which correctly discards the
    # base when $gitPath is absolute -- matching POSIX/.NET semantics.
    $combined = [System.IO.Path]::Combine($baseDir, $gitPath)
    return [System.IO.Path]::GetFullPath($combined).TrimEnd('\', '/')
}

function Test-IsGitWorktree([string]$targetDir) {
    try {
        $gitDir = (git -C "$targetDir" rev-parse --git-dir 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $gitDir) {
            return $false
        }
        $commonDir = (git -C "$targetDir" rev-parse --git-common-dir 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $commonDir) {
            return $false
        }
        $gitDirFull = Resolve-GitPathAgainst -baseDir $targetDir -gitPath $gitDir.Trim()
        $commonDirFull = Resolve-GitPathAgainst -baseDir $targetDir -gitPath $commonDir.Trim()
        return ($gitDirFull -ne $commonDirFull)
    } catch {
        return $false
    }
}

$IsLiveDashboardTarget = Test-IsGitWorktree -targetDir $TARGET
$TargetClassification = if ($IsLiveDashboardTarget) { "worktree" } else { "root" }

# --- Step 2: detect what's on PORT ------------------------------------------
# Cross-platform ordered fallback chain (#1053 CI fix — GitHub Actions runs
# this test suite on ubuntu-latest via pwsh, where Get-NetTCPConnection and
# Windows-shaped netstat output do not exist):
#   (a) Get-NetTCPConnection (Windows; wrapped in try/catch)
#   (b) non-Windows only (guarded via Test-Path variable: for PS 5.1 parse
#       safety — $IsLinux/$IsMacOS are pwsh-only automatic variables and do
#       not exist in Windows PowerShell 5.1): lsof, then ss
#   (c) netstat, platform-appropriate regex (Windows LISTENING shape vs
#       Linux/macOS LISTEN shape)
function Get-ListeningPid([int]$port) {
    # (a) Windows: Get-NetTCPConnection
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        if ($conns) {
            return ($conns | Select-Object -First 1 -ExpandProperty OwningProcess)
        }
    } catch {
        # Not available (non-Windows) or no match — fall through.
    }

    # Determine platform without referencing $IsLinux/$IsMacOS directly at
    # parse time (those automatic variables don't exist under PS 5.1; a bare
    # reference is harmless — PS treats an undefined variable as $null — but
    # we guard via Test-Path so intent is explicit and Set-StrictMode-safe).
    $onLinux = (Test-Path variable:IsLinux) -and $IsLinux
    $onMacOS = (Test-Path variable:IsMacOS) -and $IsMacOS

    if ($onLinux -or $onMacOS) {
        # (b1) lsof
        try {
            $lsofOut = & lsof -t -iTCP:$port -sTCP:LISTEN 2>$null
            if ($lsofOut) {
                $first = ($lsofOut | Select-Object -First 1).ToString().Trim()
                if ($first -match '^\d+$') {
                    return [int]$first
                }
            }
        } catch { }

        # (b2) ss -ltnp
        try {
            $ssOut = & ss -ltnp 2>$null | Select-String -Pattern (":$port\s")
            foreach ($line in $ssOut) {
                if ($line.ToString() -match 'pid=(\d+)') {
                    return [int]$Matches[1]
                }
            }
        } catch { }
    }

    # (c) netstat, platform-appropriate regex.
    try {
        $netstatOut = & netstat -ano 2>$null
        if (-not $netstatOut) {
            $netstatOut = & netstat -lntp 2>$null
        }
        if ($onLinux -or $onMacOS) {
            # Linux/macOS shape: "LISTEN ... pid=1234/python" or "... 1234/python"
            $lines = $netstatOut | Select-String -Pattern (":$port\s.*LISTEN")
            foreach ($line in $lines) {
                $text = $line.ToString()
                if ($text -match 'pid=(\d+)') {
                    return [int]$Matches[1]
                }
                if ($text -match '(\d+)/\S+\s*$') {
                    return [int]$Matches[1]
                }
            }
        } else {
            # Windows shape: "TCP  127.0.0.1:8766  0.0.0.0:0  LISTENING  1234"
            $lines = $netstatOut | Select-String -Pattern (":$port\s.*LISTENING")
            foreach ($line in $lines) {
                $parts = ($line.ToString().Trim() -split '\s+')
                if ($parts.Length -ge 5) {
                    return [int]$parts[-1]
                }
            }
        }
    } catch { }

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
    Write-Info "classification: $TargetClassification"
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

# --- Step 3: update target (ONLY when classification=worktree) --------------
if ($IsLiveDashboardTarget) {
    Write-Info "target classified as worktree - updating to origin/develop..."
    git -C "$TARGET" fetch origin develop 2>&1 | ForEach-Object { Write-Info "  $_" }
    git -C "$TARGET" reset --hard origin/develop 2>&1 | ForEach-Object { Write-Info "  $_" }
} else {
    Write-Info "target classified as repo root - skipping reset, serving as-is"
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
