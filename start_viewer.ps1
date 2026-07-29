$ErrorActionPreference = "Stop"

$viewerDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting VTK Geometry Viewer..."
Write-Host "Directory: $viewerDir"
Write-Host "URL: http://127.0.0.1:8765"
Write-Host ""
Write-Host "Open the URL in a browser, then choose:"
Write-Host "E:\SAM\Temp\VTK\N_new0702_0.vtk"
Write-Host ""
Write-Host "If dependencies are not installed, run:"
Write-Host "npm install"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server."

Set-Location -LiteralPath $viewerDir
npm run dev
