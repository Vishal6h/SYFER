# -Debug is accepted as an idiomatic alias for the shared --debug option.
$forward = @('--setup')
foreach ($argument in $args) {
    if ($argument -eq '-Debug') { $forward += '--debug' }
    else { $forward += $argument }
}
& (Join-Path $PSScriptRoot 'syfer.ps1') @forward
exit $LASTEXITCODE
