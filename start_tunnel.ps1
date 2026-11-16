param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Dual-Stream Safety Hub - Cloudflare Public Tunnel      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$binDir = Join-Path $PSScriptRoot "bin"
$cloudflaredPath = Join-Path $binDir "cloudflared.exe"

# 1. Check if cloudflared is in PATH or in bin\
$cmd = Get-Command "cloudflared" -ErrorAction SilentlyContinue
if ($cmd) {
    $cloudflaredExe = $cmd.Source
} elseif (Test-Path $cloudflaredPath) {
    $cloudflaredExe = $cloudflaredPath
} else {
    Write-Host "`n==> Cloudflare Tunnel CLI not found. Downloading..." -ForegroundColor Yellow
    if (-not (Test-Path $binDir)) {
        New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    }
    $downloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $cloudflaredPath
    $cloudflaredExe = $cloudflaredPath
    Write-Host "==> Download complete!" -ForegroundColor Green
}

Write-Host "`n==> Starting tunnel forwarding to http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "==> Look for the link ending in '.trycloudflare.com' below." -ForegroundColor Yellow
Write-Host "==> Share that HTTPS link with evaluators or open it on your phone!" -ForegroundColor Yellow
Write-Host "==> Press Ctrl+C in this window to stop the tunnel when done.`n" -ForegroundColor DarkGray

& $cloudflaredExe tunnel --url "http://127.0.0.1:$Port"
