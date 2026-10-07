# Build Hands Down from this folder and install it for the current user.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Run it again after "git pull" to update: it quits a running copy and replaces it.
# Settings and the log live in your user profile, so they are kept.
# -NoStart installs without starting the app (used by CI).

param([switch]$NoStart)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$target = Join-Path $env:LOCALAPPDATA "Programs\HandsDown"

function Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Fail($message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    exit 1
}

function Find-Python {
    # The py launcher is the usual way to reach a specific version; fall back to "python".
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.12") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($candidate in $candidates) {
        try {
            $arguments = $candidate.Args + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
            $version = & $candidate.Exe @arguments 2>$null
            if ($LASTEXITCODE -eq 0 -and "$version".Trim() -eq "3.12") { return $candidate }
        } catch { }
    }
    return $null
}

Step "Checking for Python 3.12"
$python = Find-Python
if (-not $python) {
    Fail "Python 3.12 was not found. Install it with:  winget install Python.Python.3.12`nthen close and reopen PowerShell, and run this again."
}
Write-Host "Found Python 3.12"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Step "Setting up a private Python environment (first time only)"
    $arguments = $python.Args + @("-m", "venv", ".venv")
    & $python.Exe @arguments
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the .venv folder." }
}

Step "Downloading components (the first time this can take several minutes)"
& .venv\Scripts\python.exe -m pip install --disable-pip-version-check --quiet -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { Fail "Downloading components failed. Check the internet connection and run this again." }

Step "Building Hands Down (a minute or two)"
& .venv\Scripts\pyinstaller.exe --noconfirm --log-level WARN packaging\handsdown.spec
if ($LASTEXITCODE -ne 0) { Fail "The build failed. The messages above say why." }

Step "Checking the build"
$check = Start-Process "dist\HandsDown\HandsDown.exe" -ArgumentList "--self-test" -Wait -PassThru
if ($check.ExitCode -ne 0) { Fail "The build's self-test failed (exit code $($check.ExitCode))." }
Write-Host "The build works"

Step "Installing to $target"
$running = Get-Process -Name HandsDown -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Quitting the running copy"
    $running | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
Copy-Item -Recurse "dist\HandsDown" $target

if (-not $NoStart) {
    Step "Starting Hands Down"
    Start-Process (Join-Path $target "HandsDown.exe")
}

Write-Host ""
Write-Host "Done. Hands Down is installed in $target" -ForegroundColor Green
if (-not $NoStart) {
    Write-Host "Look for a thin ring in the system tray (click the ^ arrow by the clock if it is hidden)."
}
