$path = Join-Path $PSScriptRoot "tunnel.log"
if (-not (Test-Path -LiteralPath $path)) { exit 1 }
try { $raw = Get-Content -LiteralPath $path -Raw } catch { exit 1 }
$m = [regex]::Match($raw, "https://[a-z0-9\-]+\.trycloudflare\.com")
if ($m.Success) { Write-Output $m.Value; exit 0 }
exit 2