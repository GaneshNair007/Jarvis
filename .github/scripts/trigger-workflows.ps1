# GitHub Actions Workflow Trigger Script
# Usage: .\trigger-workflows.ps1

Write-Host "🚀 JARVIS Workflow Trigger Helper" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Check if GitHub CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "❌ GitHub CLI (gh) is not installed!" -ForegroundColor Red
    Write-Host "📥 Install from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

# Check if user is authenticated
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not authenticated with GitHub!" -ForegroundColor Red
    Write-Host "🔑 Run: gh auth login" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ GitHub CLI is ready!" -ForegroundColor Green
Write-Host ""

# Menu
Write-Host "Available workflows:" -ForegroundColor Cyan
Write-Host "1. 🏆 Achievement Hunter (Quickdraw practice)" -ForegroundColor Yellow
Write-Host "2. 📈 Activity & Stats (Update immediately)" -ForegroundColor Yellow
Write-Host "3. 🚀 Create Release (version required)" -ForegroundColor Yellow
Write-Host "4. 📚 Generate Documentation" -ForegroundColor Yellow
Write-Host "5. ⚡ Run Performance Benchmarks" -ForegroundColor Yellow
Write-Host "6. 🔄 Trigger All Workflows" -ForegroundColor Yellow
Write-Host "7. 📊 View Workflow Status" -ForegroundColor Yellow
Write-Host "0. Exit" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Select option (0-7)"

switch ($choice) {
    "1" {
        Write-Host "🏆 Triggering Achievement Hunter..." -ForegroundColor Cyan
        gh workflow run achievements.yml
        Write-Host "✅ Workflow triggered! This will create a Quickdraw practice issue." -ForegroundColor Green
    }
    "2" {
        Write-Host "📈 Triggering Activity update..." -ForegroundColor Cyan
        gh workflow run activity.yml
        Write-Host "✅ Activity stats will be updated!" -ForegroundColor Green
    }
    "3" {
        $version = Read-Host "Enter version (e.g., v1.0.0)"
        Write-Host "🚀 Creating release $version..." -ForegroundColor Cyan
        gh workflow run release.yml -f version=$version
        Write-Host "✅ Release workflow triggered!" -ForegroundColor Green
    }
    "4" {
        Write-Host "📚 Generating documentation..." -ForegroundColor Cyan
        gh workflow run docs.yml
        Write-Host "✅ Documentation workflow triggered!" -ForegroundColor Green
    }
    "5" {
        Write-Host "⚡ Running benchmarks..." -ForegroundColor Cyan
        gh workflow run performance.yml
        Write-Host "✅ Performance benchmarks started!" -ForegroundColor Green
    }
    "6" {
        Write-Host "🔄 Triggering all workflows..." -ForegroundColor Cyan
        gh workflow run achievements.yml
        gh workflow run activity.yml
        gh workflow run docs.yml
        gh workflow run performance.yml
        Write-Host "✅ All workflows triggered!" -ForegroundColor Green
    }
    "7" {
        Write-Host "📊 Recent workflow runs:" -ForegroundColor Cyan
        gh run list --limit 10
    }
    "0" {
        Write-Host "👋 Goodbye!" -ForegroundColor Cyan
        exit 0
    }
    default {
        Write-Host "❌ Invalid option!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "💡 Tip: Check workflow status at:" -ForegroundColor Yellow
Write-Host "   https://github.com/GaneshNair007/Jarvis/actions" -ForegroundColor Cyan
Write-Host ""
Write-Host "🏆 Badge progress: https://github.com/GaneshNair007?tab=achievements" -ForegroundColor Yellow
