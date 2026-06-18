# Create desktop shortcuts for Holle Music executables.
# Run from PowerShell after extracting the release ZIP.

$desktop = [Environment]::GetFolderPath("Desktop")
$here = $PSScriptRoot

function Create-Shortcut($exeName, $shortcutName) {
    $exePath = Join-Path $here "$exeName.exe"
    if (-not (Test-Path $exePath)) {
        Write-Host "Not found: $exePath" -ForegroundColor Red
        return
    }

    $shortcutPath = Join-Path $desktop "$shortcutName.lnk"
    $wshell = New-Object -ComObject WScript.Shell
    $shortcut = $wshell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $exePath
    $shortcut.WorkingDirectory = $here
    $shortcut.IconLocation = "$exePath,0"
    $shortcut.Save()

    Write-Host "Created: $shortcutPath" -ForegroundColor Green
}

Create-Shortcut -exeName "hollemusic" -shortcutName "Holle Music"
Create-Shortcut -exeName "hollepet" -shortcutName "Holle 桌面助手"

Write-Host "Done. Shortcuts are on your desktop." -ForegroundColor Cyan
