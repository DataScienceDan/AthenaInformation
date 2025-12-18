# PowerShell script to push AthenaInformation to GitHub
# Run this AFTER creating the repository on GitHub

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AthenaInformation GitHub Upload Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if repository URL is provided
$repoUrl = "https://github.com/DataScienceDan/AthenaInformation.git"

Write-Host "Repository URL: $repoUrl" -ForegroundColor Yellow
Write-Host ""

# Check current remotes
Write-Host "Current remotes:" -ForegroundColor Cyan
git remote -v
Write-Host ""

# Ask user if they want to add new remote or update origin
$choice = Read-Host "Add as new remote 'athena-info' (1) or update 'origin' (2)? [1/2]"

if ($choice -eq "1") {
    Write-Host "Adding new remote 'athena-info'..." -ForegroundColor Green
    git remote add athena-info $repoUrl
    $remoteName = "athena-info"
} else {
    Write-Host "Updating 'origin' remote..." -ForegroundColor Green
    git remote set-url origin $repoUrl
    $remoteName = "origin"
}

Write-Host ""
Write-Host "Checking git status..." -ForegroundColor Cyan
git status --short
Write-Host ""

# Ask if user wants to push
$pushChoice = Read-Host "Push to GitHub now? [y/N]"

if ($pushChoice -eq "y" -or $pushChoice -eq "Y") {
    Write-Host "Pushing to GitHub..." -ForegroundColor Green
    git push -u $remoteName main
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "Success! Code pushed to GitHub." -ForegroundColor Green
        Write-Host "Repository: https://github.com/DataScienceDan/AthenaInformation" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Red
        Write-Host "Error pushing to GitHub." -ForegroundColor Red
        Write-Host "Make sure you've created the repository on GitHub first." -ForegroundColor Yellow
        Write-Host "See setup_github_repo.md for instructions." -ForegroundColor Yellow
        Write-Host "========================================" -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "Skipping push. Run manually with:" -ForegroundColor Yellow
    Write-Host "  git push -u $remoteName main" -ForegroundColor Yellow
}

Write-Host ""

