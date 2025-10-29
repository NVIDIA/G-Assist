# Download NVAPI Files Script
# This script downloads all required NVAPI files from the official NVIDIA GitHub repository
# Run this from the rise_demo_client directory

Write-Host "Downloading NVAPI files from official NVIDIA GitHub..." -ForegroundColor Green
Write-Host ""

$baseUrl = "https://raw.githubusercontent.com/NVIDIA/nvapi/main"

# List of all required files
$files = @(
    "nvapi.h",
    "nvapi_lite_common.h",
    "nvapi_lite_salstart.h",
    "nvapi_lite_salend.h",
    "nvapi_lite_sli.h",
    "nvapi_lite_d3dext.h",
    "nvapi_lite_stereo.h",
    "nvapi_lite_surround.h"
)

$libraryUrl = "https://raw.githubusercontent.com/NVIDIA/nvapi/main/amd64/nvapi64.lib"

# Download header files
$successCount = 0
$failCount = 0

foreach ($file in $files) {
    try {
        $url = "$baseUrl/$file"
        Write-Host "Downloading $file..." -NoNewline
        Invoke-WebRequest -Uri $url -OutFile $file -ErrorAction Stop
        Write-Host " OK" -ForegroundColor Green
        $successCount++
    }
    catch {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host "  Error: $_" -ForegroundColor Red
        $failCount++
    }
}

# Download library file
try {
    Write-Host "Downloading nvapi64.lib..." -NoNewline
    Invoke-WebRequest -Uri $libraryUrl -OutFile "nvapi64.lib" -ErrorAction Stop
    Write-Host " OK" -ForegroundColor Green
    $successCount++
}
catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    $failCount++
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Download Summary:" -ForegroundColor Cyan
Write-Host "  Success: $successCount files" -ForegroundColor Green
Write-Host "  Failed:  $failCount files" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Red" })
Write-Host "============================================" -ForegroundColor Cyan

if ($failCount -eq 0) {
    Write-Host ""
    Write-Host "All files downloaded successfully!" -ForegroundColor Green
    Write-Host "You can now build the project in Visual Studio." -ForegroundColor Green
    Write-Host ""
    Write-Host "Files downloaded:" -ForegroundColor Yellow
    Get-ChildItem -Path . -Filter "nvapi*" | Select-Object Name, @{Name="Size (KB)";Expression={[math]::Round($_.Length/1KB, 2)}} | Format-Table -AutoSize
}
else {
    Write-Host ""
    Write-Host "Some files failed to download. Please check the errors above." -ForegroundColor Red
    Write-Host "You may need to download them manually from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/NVIDIA/nvapi" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

