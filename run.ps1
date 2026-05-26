# FinPilot launcher — PowerShell convenience wrapper around run.py.
#
#   .\run.ps1                 set up and run the whole app
#   .\run.ps1 --refresh       regenerate signals (live) before serving
#   .\run.ps1 --offline ...   pass any run.py flag straight through
#
# All the real work lives in run.py (cross-platform, standard library only).
# This wrapper only locates a Python interpreter and hands off to it, so the
# project also runs with a plain double-click / `.\run.ps1` on Windows.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prefer the `py` launcher (ships with the python.org installer), else `python`.
$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" }
          elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" }
          else { $null }

if ($null -eq $python) {
    Write-Error "No Python found on PATH. Install Python 3.10+ from python.org."
    exit 1
}

& $python (Join-Path $root "run.py") @args
exit $LASTEXITCODE
