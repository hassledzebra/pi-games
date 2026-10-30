# Copy Pi Brawl from this Windows PC to a Raspberry Pi over SSH.
# Usage (PowerShell, from the project folder):
#   .\deploy\deploy.ps1                      # uses pi@raspberrypi.local
#   .\deploy\deploy.ps1 -Target zheng@192.168.1.50
param([string]$Target = "pi@raspberrypi.local", [string]$Dir = "pi-brawl")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $env:TEMP "pi-brawl-deploy.tar.gz"

Push-Location $root
try {
    # one archive = one password prompt; skips the venv and caches
    tar -czf $stage --exclude=__pycache__ --exclude=tests/out main.py requirements.txt README.md engine games deploy tests
    ssh $Target "mkdir -p ~/$Dir"
    scp $stage "${Target}:~/$Dir/bundle.tar.gz"
    ssh $Target "cd ~/$Dir && tar -xzf bundle.tar.gz && rm bundle.tar.gz && chmod +x deploy/*.sh"
    Write-Host "Copied to ${Target}:~/$Dir"
    Write-Host "First time on the Pi:  cd ~/$Dir && ./deploy/install_pi.sh"
} finally {
    Pop-Location
    Remove-Item $stage -ErrorAction SilentlyContinue
}
