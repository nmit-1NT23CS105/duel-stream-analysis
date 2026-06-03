param(
    [switch]$Reinstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-PythonCommand {
    $candidates = @(
        @{ Command = "py"; PrefixArgs = @("-3.11") },
        @{ Command = "python"; PrefixArgs = @() },
        @{ Command = "py"; PrefixArgs = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            $version = & $candidate.Command @($candidate.PrefixArgs + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
            if ($LASTEXITCODE -eq 0 -and $version) {
                return @{
                    Command = $candidate.Command
                    PrefixArgs = $candidate.PrefixArgs
                    Version = ($version | Select-Object -First 1).Trim()
                }
            }
        }
        catch {
        }
    }

    throw "Python was not found. Please install Python 3.11 and try again."
}

function Invoke-Python {
    param(
        [string]$Command,
        [string[]]$PrefixArgs,
        [string[]]$Args
    )

    & $Command @($PrefixArgs + $Args)
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $Command $($PrefixArgs -join ' ') $($Args -join ' ')"
    }
}

$python = Get-PythonCommand
if (-not $python.Version.StartsWith("3.11")) {
    Write-Warning "Python $($python.Version) was detected. Python 3.11 is recommended for the most reliable setup."
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$requirementsHashFile = Join-Path $PSScriptRoot ".venv\requirements.sha256"
$requirementsHash = (Get-FileHash (Join-Path $PSScriptRoot "requirements.txt") -Algorithm SHA256).Hash

if (-not (Test-Path $venvPython)) {
    Write-Step "Creating virtual environment"
    Invoke-Python -Command $python.Command -PrefixArgs $python.PrefixArgs -Args @("-m", "venv", ".venv")
}

if (
    $Reinstall -or
    -not (Test-Path $requirementsHashFile) -or
    ((Get-Content $requirementsHashFile -Raw).Trim() -ne $requirementsHash)
) {
    Write-Step "Installing project dependencies"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip."
    }

    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install requirements."
    }

    Set-Content -Path $requirementsHashFile -Value $requirementsHash -NoNewline
}
else {
    Write-Step "Dependencies already match requirements.txt"
}

if (-not (Test-Path ".env")) {
    Write-Step "Creating local environment file"
    Copy-Item ".env.example" ".env"
}

@("data", "data\uploads", "data\events", "data\ultralytics") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

Write-Step "Running quick environment check"
& $venvPython -c "import fastapi, cv2, mediapipe, ultralytics; print('Environment ready')"
if ($LASTEXITCODE -ne 0) {
    throw "Environment check failed."
}

if (-not $NoBrowser) {
    $browserJob = Start-Job -ScriptBlock {
        Start-Sleep -Seconds 4
        Start-Process "http://127.0.0.1:8000"
    }
    Receive-Job $browserJob -Wait -AutoRemoveJob | Out-Null
}

Write-Step "Starting the project"
Write-Host "Open http://127.0.0.1:8000 if the browser does not open automatically." -ForegroundColor Yellow
Write-Host "Use Recorded mode if the shared system does not have two live cameras available." -ForegroundColor Yellow
Write-Host ""

& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
