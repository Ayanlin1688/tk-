# auto_sync.ps1 - TK workbench auto sync to GitHub (scheduled task, silent)
$g = "C:\Program Files\Git\bin\git.exe"
$repo = "E:\桌面\TK图文工作台(1)\TK图文工作台\TK图文工作台"
$log = Join-Path $repo "sync_log.txt"

try {
    Set-Location -LiteralPath $repo
    & $g add -A 2>&1 | Out-Null
    $changed = @(& $g status -s)
    if ($changed.Count -gt 0 -and $changed) {
        & $g commit -m ("auto-sync " + (Get-Date -Format "yyyy-MM-dd HH:mm")) 2>&1 | Out-Null
        & $g push origin main 2>&1 | Out-Null
        Add-Content -LiteralPath $log -Value ("OK " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " synced " + $changed.Count + " files") -Encoding utf8
    } else {
        Add-Content -LiteralPath $log -Value ("IDLE " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " no changes") -Encoding utf8
    }
} catch {
    Add-Content -LiteralPath $log -Value ("ERR " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $_.Exception.Message) -Encoding utf8
}