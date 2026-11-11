# Builds dist\Google Tasks Importer.exe from gui.py.
# If credentials.json is in this folder it is baked into the exe; otherwise
# the app looks for it in %APPDATA%\Google Tasks Importer at runtime.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$arguments = @(
    "-m", "PyInstaller", "gui.py",
    "--name", "Google Tasks Importer",
    "--onefile", "--windowed", "--noconfirm", "--clean",
    "--collect-data", "customtkinter",
    "--add-data", "assets;assets"
)
if (Test-Path "credentials.json") {
    Write-Host "Bundling credentials.json into the exe."
    $arguments += @("--add-data", "credentials.json;.")
}

& $python @arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Built: dist\Google Tasks Importer.exe"
