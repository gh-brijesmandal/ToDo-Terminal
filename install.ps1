# install.ps1 - installs `todo` as a global command on Windows
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Ok   { param($msg) Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "  [->]  $msg" -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host "  [!]   $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  [X]   $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Terminal Todo - Windows installer" -ForegroundColor White
Write-Host "  ----------------------------------"
Write-Host ""

# -- Locate todo.py -----------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SrcPy     = Join-Path $ScriptDir "todo.py"

if (-not (Test-Path $SrcPy)) {
    Write-Fail "todo.py not found at $SrcPy"
}
Write-Ok "todo.py found"

# -- Check Python -------------------------------------------------------------
$PythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 6)) {
                $PythonCmd = $candidate
                Write-Ok "Python $major.$minor found ($candidate)"
                break
            }
        }
    } catch { }
}

if (-not $PythonCmd) {
    Write-Warn "Python 3.6+ not found."
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  Tick 'Add Python to PATH' during install." -ForegroundColor Yellow
    Write-Fail "Aborting. Install Python first then re-run."
}

# -- Install windows-curses ---------------------------------------------------
Write-Info "Installing windows-curses..."
try {
    & $PythonCmd -m pip install --quiet windows-curses
    Write-Ok "windows-curses installed"
} catch {
    Write-Warn "pip install failed. Run manually: pip install windows-curses"
}

# -- Create directories -------------------------------------------------------
$BinDir  = Join-Path $env:USERPROFILE ".local\bin"
$DataDir = Join-Path $env:USERPROFILE ".local\share\terminal-todo"

New-Item -ItemType Directory -Force -Path $BinDir  | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# -- Copy todo.py -------------------------------------------------------------
$DestPy = Join-Path $BinDir "todo.py"
Copy-Item $SrcPy $DestPy -Force
Write-Ok "copied todo.py -> $DestPy"

# -- Write todo.bat wrapper ---------------------------------------------------
$BatPath = Join-Path $BinDir "todo.bat"
$line1 = "@echo off"
$line2 = $PythonCmd + ' "%~dp0todo.py" %*'
Set-Content -Path $BatPath -Value $line1 -Encoding ASCII
Add-Content -Path $BatPath -Value $line2 -Encoding ASCII
Write-Ok "created todo.bat -> $BatPath"

# -- Add to user PATH if needed -----------------------------------------------
$CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($null -eq $CurrentPath) { $CurrentPath = "" }

if ($CurrentPath -notlike "*$BinDir*") {
    Write-Info "Adding $BinDir to user PATH..."
    $NewPath = $BinDir + ";" + $CurrentPath
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
    Write-Ok "PATH updated"
    Write-Warn "Open a new terminal window for PATH to take effect."
} else {
    Write-Ok "$BinDir already in PATH"
}

# -- Done ---------------------------------------------------------------------
Write-Host ""
Write-Host "  All done!" -ForegroundColor Green
Write-Host "  ----------------------------------"
Write-Host ""
Write-Host "  Open a NEW terminal window, then:" -ForegroundColor White
Write-Host ""
Write-Host "    todo              open the TUI app" -ForegroundColor Cyan
Write-Host "    todo list         print tasks inline" -ForegroundColor Cyan
Write-Host "    todo help         usage reference" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tip: Windows Terminal gives best colour support." -ForegroundColor DarkGray
Write-Host "  https://aka.ms/terminal" -ForegroundColor DarkGray
Write-Host ""
