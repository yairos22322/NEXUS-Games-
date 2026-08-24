$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "NEXUS FIVE 3D ULTRA - GitHub Publisher"
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is not installed. Install Git for Windows, then run this script again."
    exit 1
}

$repoUrl = Read-Host "Paste your EMPTY GitHub repository HTTPS URL"
if ([string]::IsNullOrWhiteSpace($repoUrl)) {
    throw "Repository URL cannot be empty."
}

$insideGit = $false
try {
    git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -eq 0) { $insideGit = $true }
} catch {}

if (-not $insideGit) {
    git init
}

git branch -M main
git add .

git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Initial release - NEXUS FIVE 3D ULTRA"
    if ($LASTEXITCODE -ne 0) {
        throw "Commit failed. Configure git user.name and user.email, then retry."
    }
}

$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $origin) {
    git remote set-url origin $repoUrl
} else {
    git remote add origin $repoUrl
}

git push -u origin main
if ($LASTEXITCODE -ne 0) {
    throw "Push failed. Confirm authentication and that the remote repository is empty."
}

Write-Host ""
Write-Host "SUCCESS - Project pushed to GitHub."
