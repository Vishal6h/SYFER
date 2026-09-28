# Both launch and setup use the same Python core. All arguments are forwarded.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
foreach ($name in @('py', 'python', 'python3')) {
    $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { continue }
    $prefix = @()
    if ($name -eq 'py') { $prefix = @('-3') }
    try {
        & $command.Source @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>$null
    } catch { continue }
    if ($LASTEXITCODE -ne 0) { continue }
    & $command.Source @prefix (Join-Path $root 'scripts/syfer_chat.py') @args
    exit $LASTEXITCODE
}
[Console]::Error.WriteLine('[SYFER] Python 3.8 or newer is required. Install Python 3 and enable its launcher or add Python to PATH, then reopen PowerShell.')
exit 1
