#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build and deploy all G-Assist plugins
.DESCRIPTION
    This script sets up, builds, and deploys all Python-based G-Assist plugins.
    It runs setup.bat and build.bat for each plugin, then copies the built files
    to the deployment directory.
.PARAMETER PluginsRoot
    Root directory containing all plugin folders (default: current directory)
.PARAMETER DeploymentRoot
    Root deployment directory (default: C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins)
.PARAMETER SkipSetup
    Skip running setup.bat (useful if dependencies are already installed)
.PARAMETER PluginNames
    Specific plugin names to build (default: all plugins with setup.bat)
.EXAMPLE
    .\build_and_deploy_all.ps1
.EXAMPLE
    .\build_and_deploy_all.ps1 -SkipSetup
.EXAMPLE
    .\build_and_deploy_all.ps1 -PluginNames @('weather', 'stock', 'discord')
#>

param(
    [string]$PluginsRoot = $PSScriptRoot,
    [string]$DeploymentRoot = "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins",
    [switch]$SkipSetup,
    [string[]]$PluginNames = @()
)

# Color output functions
function Write-PluginSuccess { param([string]$Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-PluginInfo { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-PluginWarning { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-PluginError { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Write-PluginHeader { param([string]$Message) Write-Host "`n========================================" -ForegroundColor Magenta; Write-Host $Message -ForegroundColor Magenta; Write-Host "========================================`n" -ForegroundColor Magenta }

# Initialize counters
$script:TotalPlugins = 0
$script:SuccessCount = 0
$script:FailureCount = 0
$script:SkippedCount = 0
$script:Results = @()

function Build-Plugin {
    param(
        [string]$PluginPath,
        [string]$PluginName
    )
    
    $script:TotalPlugins++
    
    Write-PluginHeader "Processing Plugin: $PluginName"
    
    # Check if plugin has setup.bat and build.bat
    $setupBat = Join-Path $PluginPath "setup.bat"
    $buildBat = Join-Path $PluginPath "build.bat"
    
    if (-not (Test-Path $buildBat)) {
        Write-PluginWarning "No build.bat found in $PluginName - skipping (likely a C++ plugin)"
        $script:SkippedCount++
        $script:Results += [PSCustomObject]@{
            Plugin = $PluginName
            Status = "Skipped"
            Reason = "No build.bat found"
        }
        return
    }
    
    try {
        # Step 1: Setup (if not skipped)
        if (-not $SkipSetup -and (Test-Path $setupBat)) {
            Write-PluginInfo "Running setup for $PluginName..."
            Push-Location $PluginPath
            $setupOutput = & cmd /c "setup.bat" 2>&1
            Pop-Location
            
            if ($LASTEXITCODE -ne 0) {
                Write-PluginError "Setup failed for $PluginName"
                Write-Host $setupOutput
                throw "Setup failed with exit code $LASTEXITCODE"
            }
            Write-PluginSuccess "Setup completed for $PluginName"
        } elseif ($SkipSetup) {
            Write-PluginInfo "Skipping setup for $PluginName (as requested)"
        } else {
            Write-PluginWarning "No setup.bat found for $PluginName"
        }
        
        # Step 2: Build
        Write-PluginInfo "Building $PluginName..."
        Push-Location $PluginPath
        $buildOutput = & cmd /c "build.bat" 2>&1
        Pop-Location
        
        if ($LASTEXITCODE -ne 0) {
            Write-PluginError "Build failed for $PluginName"
            Write-Host $buildOutput
            throw "Build failed with exit code $LASTEXITCODE"
        }
        Write-PluginSuccess "Build completed for $PluginName"
        
        # Step 3: Deploy
        $distPath = Join-Path $PluginPath "dist\$PluginName"
        $deployPath = Join-Path $DeploymentRoot $PluginName
        
        if (-not (Test-Path $distPath)) {
            throw "Build output not found at $distPath"
        }
        
        Write-PluginInfo "Deploying $PluginName to $deployPath..."
        
        # Create deployment directory if it doesn't exist
        if (-not (Test-Path $deployPath)) {
            New-Item -ItemType Directory -Path $deployPath -Force | Out-Null
        }
        
        # Copy files with error handling for locked files
        try {
            Copy-Item "$distPath\*" $deployPath -Recurse -Force -ErrorAction Stop
            Write-PluginSuccess "Deployed $PluginName successfully"
            $script:SuccessCount++
            $script:Results += [PSCustomObject]@{
                Plugin = $PluginName
                Status = "Success"
                Reason = "Built and deployed"
            }
        } catch {
            if ($_.Exception.Message -like "*being used by another process*") {
                Write-PluginWarning "Executable locked for $PluginName - deployed manifest/config only"
                # Try to copy non-exe files
                Get-ChildItem "$distPath\*" -Exclude "*.exe" | ForEach-Object {
                    Copy-Item $_.FullName $deployPath -Force -ErrorAction SilentlyContinue
                }
                $script:SuccessCount++
                $script:Results += [PSCustomObject]@{
                    Plugin = $PluginName
                    Status = "Partial"
                    Reason = "Exe locked, manifest/config updated"
                }
            } else {
                throw
            }
        }
        
    } catch {
        $errorMsg = $_.Exception.Message
        Write-Host "✗ Failed to process $PluginName`: $errorMsg" -ForegroundColor Red
        $script:FailureCount++
        $script:Results += [PSCustomObject]@{
            Plugin = $PluginName
            Status = "Failed"
            Reason = $errorMsg
        }
    }
}

# Main execution
Write-PluginHeader "G-Assist Plugin Builder & Deployer"
Write-PluginInfo "Plugins Root: $PluginsRoot"
Write-PluginInfo "Deployment Root: $DeploymentRoot"
Write-PluginInfo "Skip Setup: $SkipSetup"

# Get list of plugins to build
if ($PluginNames.Count -eq 0) {
    # Auto-detect all plugin directories with setup.bat or build.bat
    $pluginDirs = Get-ChildItem -Path $PluginsRoot -Directory | Where-Object {
        (Test-Path (Join-Path $_.FullName "build.bat")) -or 
        (Test-Path (Join-Path $_.FullName "setup.bat"))
    }
    Write-PluginInfo "Auto-detected $($pluginDirs.Count) plugins"
} else {
    # Use specified plugin names
    $pluginDirs = $PluginNames | ForEach-Object {
        $path = Join-Path $PluginsRoot $_
        if (Test-Path $path) {
            Get-Item $path
        } else {
            Write-PluginWarning "Plugin directory not found: $path"
        }
    }
    Write-PluginInfo "Building $($pluginDirs.Count) specified plugins"
}

# Build each plugin
foreach ($pluginDir in $pluginDirs) {
    Build-Plugin -PluginPath $pluginDir.FullName -PluginName $pluginDir.Name
}

# Summary
Write-PluginHeader "Build & Deployment Summary"
Write-Host "Total Plugins Processed: $script:TotalPlugins" -ForegroundColor White
Write-PluginSuccess "Successful: $script:SuccessCount"
Write-PluginError "Failed: $script:FailureCount"
Write-PluginWarning "Skipped: $script:SkippedCount"

Write-Host "`nDetailed Results:" -ForegroundColor White
$script:Results | Format-Table -AutoSize

if ($script:FailureCount -gt 0) {
    Write-Host "`nSome plugins failed to build. Check the output above for details." -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nAll plugins processed successfully! 🎉" -ForegroundColor Green
    exit 0
}

