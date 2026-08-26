$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
& g++ -std=c++11 -O0 -Wall -Wextra `
    -I "$root\firmware\esp32\include" `
    -o "$PSScriptRoot\test_logic.exe" `
    "$PSScriptRoot\test_logic.cpp"
if ($LASTEXITCODE -ne 0) { Write-Error "compile failed"; exit 1 }
& "$PSScriptRoot\test_logic.exe"
exit $LASTEXITCODE
