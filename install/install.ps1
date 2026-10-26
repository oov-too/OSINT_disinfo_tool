# The ledger bundle's install entry point on Windows: runs install\install.py with Python 3 (3.11 or later). Nothing is fetched.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue; if ($py) { & py -3 (Join-Path $here 'install.py') @args; exit $LASTEXITCODE } }
if (-not $py) { Write-Error 'Python 3.11 or later is needed (python3 or the py launcher); install it from the institution''s mirror.'; exit 2 }
& python3 (Join-Path $here 'install.py') @args
exit $LASTEXITCODE
